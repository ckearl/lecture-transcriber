import os
import sys
import json
import time
import argparse
import logging
import wave
from pathlib import Path
from typing import Dict, List

import pyfiglet
from tqdm import tqdm
from colorama import init, Fore, Back, Style

from db_supabase.upload import LectureUploader
from db_supabase.read import LectureReader
from gdrive.read import loop as gdrive_read, loop_with_metadata as gdrive_read_with_metadata
from gdrive.upload import upload as gdrive_upload
from gdrive.download import download_file_to_temp
from local_files.read import read as local_read
from local_files.read import (
    parse_date_from_filename,
    format_time_string_with_am_pm,
    get_day_of_week_from_date,
    truncate_recording_endtime_to_nearest_quarter,
    CLASS_TIME_MAPPINGS
)

from transcribe.transcribe import TranscriptionProcessor
from text_insights.process import TextProcessor

# Initialize colorama for colored output
init(autoreset=True)

# Configure logging to hide INFO messages
logging.basicConfig(level=logging.WARNING)

SUPABASE_URL = os.getenv('SUPABASE_URL')
# Use SERVICE_KEY for admin operations to bypass RLS policies
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_ANON_KEY')


def get_audio_info(file_path: Path) -> Dict:
    """Get audio file information including duration and size."""
    try:
        # Get file size
        file_size = file_path.stat().st_size
        size_mb = file_size / (1024 * 1024)

        # Get duration from WAV file
        duration = 0
        try:
            with wave.open(str(file_path), 'rb') as wav_file:
                frames = wav_file.getnframes()
                sample_rate = wav_file.getframerate()
                duration = frames / sample_rate
        except:
            duration = 0

        return {
            'size_mb': round(size_mb, 1),
            'duration_minutes': round(duration / 60, 1),
            'duration_seconds': int(duration)
        }
    except:
        return {'size_mb': 0, 'duration_minutes': 0, 'duration_seconds': 0}


def format_duration(seconds: int) -> str:
    """Format duration in MM:SS format."""
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes:02d}:{secs:02d}"


def animate_dots(message: str, duration: float = 2.0, color: str = Fore.CYAN):
    """Animate dots after a message."""
    for _ in range(int(duration * 2)):
        for dots in ["", ".", "..", "..."]:
            print(f"\r{color}{message}{dots}   ", end="", flush=True)
            time.sleep(0.25)
    print()


def print_banner():
    """Print cute banner with ASCII art."""
    print(Fore.MAGENTA + Style.BRIGHT)
    text = "hi my love <3"
    ascii_art = pyfiglet.figlet_format(text, font="slant")
    print(ascii_art)

    print(Style.RESET_ALL)

    animate_dots("Initializing", 1.5, Fore.GREEN)


def confirm_file_processing(file_info: Dict, skip_confirmations: bool = False) -> tuple:
    """Confirm file processing with user and allow filename editing."""
    if skip_confirmations:
        return True, file_info['gdrive_filename']

    print(f"\n{Fore.YELLOW}📋 File Details:")
    print(f"   📅 Date: {file_info['date']}")
    print(f"   📚 Class: {file_info['class']}")
    print(f"   📖 Title: {file_info['title']}")
    print(f"   📁 Filename: {Fore.GREEN}{file_info['gdrive_filename']}")

    # Only show size/duration if available (USB files have this, Google Drive files don't yet)
    if 'size_mb' in file_info:
        print(f"   💾 Size: {file_info['size_mb']} MB")
    if 'duration_seconds' in file_info:
        print(f"   ⏱️  Duration: {format_duration(file_info['duration_seconds'])}")

    while True:
        response = input(
            f"\n{Fore.CYAN}Continue with this file? (y/n/e to edit filename): {Style.RESET_ALL}").lower().strip()

        if response == 'y':
            return True, file_info['gdrive_filename']
        elif response == 'n':
            print(f"{Fore.YELLOW}⏭️  Skipping this file...")
            return False, ""
        elif response == 'e':
            new_filename = input(
                f"{Fore.GREEN}Enter new filename (without .mp3): {Style.RESET_ALL}").strip()
            if new_filename:
                if not new_filename.endswith('.mp3'):
                    new_filename += '.mp3'
                print(f"{Fore.GREEN}✅ Updated filename: {new_filename}")
                return True, new_filename

        print(f"{Fore.RED}Please enter 'y', 'n', or 'e'")


def show_processing_summary(files_to_process: List[Dict], skip_confirmations: bool = False):
    """Show summary of files to be processed."""
    if not files_to_process:
        print(f"\n{Fore.GREEN}🎉 All files are already processed! Nothing to do.")
        return

    print(f"\n{Fore.CYAN}📊 Processing Summary:")
    print(f"   Files to process: {Fore.YELLOW}{len(files_to_process)}")

    total_size = sum(f.get('size_mb', 0) for f in files_to_process)
    total_duration = sum(f.get('duration_seconds', 0) for f in files_to_process)

    print(f"   Total size: {Fore.YELLOW}{total_size:.1f} MB")
    print(f"   Total duration: {Fore.YELLOW}{format_duration(total_duration)}")

    if not skip_confirmations:
        response = input(
            f"\n{Fore.GREEN}Ready to start processing? (y/n): {Style.RESET_ALL}").lower().strip()
        if response != 'y':
            print(f"{Fore.YELLOW}👋 Goodbye!")
            sys.exit(0)


def parse_gdrive_filename_for_metadata(filename: str, class_name: str) -> Dict:
    """Parse Google Drive filename to extract metadata.

    Expected format: YYYY-MM-DD_Lecture_Title.mp3
    """
    try:
        # Remove .mp3 extension
        name_without_ext = filename.replace('.mp3', '').replace('.wav', '')

        # Split by underscore to get date and title parts
        parts = name_without_ext.split('_')

        if len(parts) >= 1:
            date_str = parts[0]  # YYYY-MM-DD
            title_parts = parts[1:] if len(parts) > 1 else [class_name, 'Lecture']
            lecture_title = ' '.join(title_parts)

            # Load professor from metadata
            try:
                metadata_path = Path.home() / 'senah' / 'lecture-transcriber' / \
                    'lecture_metadata' / class_name / 'data.json'
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                professor = metadata.get('professor', 'Professor')
                # Try to get exact title from metadata
                exact_title = metadata.get('lecture_titles', {}).get(date_str)
                if exact_title:
                    lecture_title = exact_title
            except:
                professor = 'Professor'

            return {
                'date': date_str,
                'class': class_name,
                'title': lecture_title,
                'professor': professor
            }
    except Exception as e:
        print(f"{Fore.YELLOW}⚠️  Could not parse filename: {filename}")

    return None


def show_gdrive_file_menu(gdrive_files_with_metadata: List[Dict], existing_transcriptions: List[str]) -> List[Dict]:
    """Show menu of Google Drive files not in Supabase and let user select."""

    # Filter files that aren't already in Supabase
    unprocessed_files = []

    for file_info in gdrive_files_with_metadata:
        metadata = parse_gdrive_filename_for_metadata(file_info['name'], file_info['class'])
        if metadata:
            lecture_identifier = f"{metadata['date']}: {metadata['class']}"
            if lecture_identifier not in existing_transcriptions:
                unprocessed_files.append({
                    **file_info,
                    **metadata
                })

    if not unprocessed_files:
        print(f"\n{Fore.GREEN}✅ All Google Drive files are already transcribed!")
        return []

    print(f"\n{Fore.CYAN}📂 Found {len(unprocessed_files)} Google Drive files not yet transcribed:")
    print(f"{Fore.CYAN}{'='*60}")

    for i, file_info in enumerate(unprocessed_files, 1):
        print(f"{Fore.YELLOW}{i}. {Fore.WHITE}{file_info['date']} - {file_info['class']}")
        print(f"   {Fore.CYAN}Title: {file_info['title']}")
        print(f"   {Fore.GREEN}File: {file_info['name']}")
        print()

    print(f"{Fore.CYAN}{'='*60}")

    while True:
        selection = input(f"\n{Fore.CYAN}Enter file numbers to transcribe (comma-separated, 'all', or 'none'): {Style.RESET_ALL}").strip().lower()

        if selection == 'none':
            return []
        elif selection == 'all':
            return unprocessed_files
        else:
            try:
                indices = [int(x.strip()) - 1 for x in selection.split(',')]
                selected_files = [unprocessed_files[i] for i in indices if 0 <= i < len(unprocessed_files)]
                if selected_files:
                    return selected_files
                else:
                    print(f"{Fore.RED}Invalid selection. Please try again.")
            except (ValueError, IndexError):
                print(f"{Fore.RED}Invalid input. Please enter numbers separated by commas.")


def main():
    parser = argparse.ArgumentParser(description="Process lecture recordings")
    parser.add_argument('-y', '--yes', action='store_true',
                        help='Skip all confirmations')
    args = parser.parse_args()

    # Initialize processors with suppressed logging
    print_banner()

    with tqdm(total=2, desc="Initializing", bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt}', colour='green') as pbar:
        processor = TranscriptionProcessor(SUPABASE_URL, SUPABASE_KEY)
        pbar.update(1)
        text_processor = TextProcessor(SUPABASE_URL, SUPABASE_KEY)
        pbar.update(1)

    # Step 1: Check existing transcriptions
    print(f"\n{Fore.BLUE}🔍 Checking database for existing transcriptions...")
    try:
        reader = LectureReader(SUPABASE_URL, SUPABASE_KEY)
        sb_lecture_list = reader.fetch_lecture_list()
        curated_sb_lecture_list = []

        if sb_lecture_list is not None:
            for lecture in sb_lecture_list:
                curated_sb_lecture_list.append(
                    f"{lecture['date']}: {lecture['class_number']}")
            print(
                f"{Fore.GREEN}✅ Found {len(curated_sb_lecture_list)} existing transcriptions")
        else:
            print(f"{Fore.YELLOW}⚠️  No existing transcriptions found")
    except Exception:
        curated_sb_lecture_list = []
        print(f"{Fore.YELLOW}⚠️  Could not connect to database")

    # Step 2: Check if USB device is plugged in
    audio_recording_dir = Path('/Volumes/USB-DISK/RECORD')
    usb_plugged_in = audio_recording_dir.exists()

    if usb_plugged_in:
        print(f"\n{Fore.GREEN}✅ USB recording device detected!")
        print(f"{Fore.BLUE}📁 Scanning local audio files...")
    else:
        print(f"\n{Fore.YELLOW}📱 USB recording device not detected")
        print(f"{Fore.CYAN}💡 Will check Google Drive for files to transcribe...")

    # Step 3: Check Google Drive (for both modes)
    print(f"\n{Fore.BLUE}☁️  Checking Google Drive...")
    gdrive_files_with_metadata = []
    try:
        if usb_plugged_in:
            gdrive_files = gdrive_read()
            print(f"{Fore.GREEN}✅ Found {len(gdrive_files)} files in Google Drive")
        else:
            # Need detailed metadata for download mode
            gdrive_files_with_metadata = gdrive_read_with_metadata()
            print(f"{Fore.GREEN}✅ Found {len(gdrive_files_with_metadata)} files in Google Drive")
            gdrive_files = [f['name'] for f in gdrive_files_with_metadata]
    except Exception as e:
        gdrive_files = []
        print(f"{Fore.YELLOW}⚠️  Could not connect to Google Drive: {e}")

    valid_files = []

    # Step 4: Process based on mode (USB vs Google Drive)
    if usb_plugged_in:
        # USB MODE: Scan local files
        audio_files = [f for f in audio_recording_dir.iterdir(
        ) if f.is_file() and not f.name.startswith('.')]

        print(f"{Fore.GREEN}📂 Found {len(audio_files)} files")

        # Process each file and collect valid ones
        for file_path in audio_files:
            try:
                date_str, time_str = parse_date_from_filename(file_path.name)
                day_of_week = get_day_of_week_from_date(date_str)
                hour, minute = map(int, time_str.split(':')[0:2])
                truncated_end_time = truncate_recording_endtime_to_nearest_quarter(
                    hour, minute)

                class_time_key = f"{day_of_week}: {truncated_end_time} {'AM' if hour < 12 else 'PM'}"
                if class_time_key[5] == '0':
                    class_time_key = f"{day_of_week}: {class_time_key[6:]}"

                class_name = CLASS_TIME_MAPPINGS.get(class_time_key)
                if not class_name:
                    continue

                # Load metadata
                try:
                    metadata_path = Path.home() / 'senah' / 'lecture-transcriber' / \
                        'lecture_metadata' / class_name / 'data.json'
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                    lecture_title = metadata.get('lecture_titles', {}).get(
                        date_str, f"{class_name} Lecture")
                    professor = metadata.get('professor', 'Professor')
                except:
                    lecture_title = f"{class_name} Lecture"
                    professor = 'Professor'

                # Check if already processed
                lecture_identifier = f"{date_str}: {class_name}"
                if lecture_identifier in curated_sb_lecture_list:
                    continue

                # Get audio info
                audio_info = get_audio_info(file_path)

                file_info = {
                    'file_path': file_path,
                    'date': date_str,
                    'class': class_name,
                    'title': lecture_title,
                    'professor': professor,
                    'gdrive_filename': f"{date_str}_{lecture_title.replace(' ', '_')}.mp3",
                    'metadata': {
                        'title': lecture_title,
                        'class': class_name,
                        'professor': professor,
                        'date': date_str
                    },
                    **audio_info
                }

                valid_files.append(file_info)

            except (ValueError, Exception):
                continue

    else:
        # GOOGLE DRIVE MODE: Show menu and let user select files
        if not gdrive_files_with_metadata:
            print(f"\n{Fore.RED}❌ No Google Drive files available")
            return

        selected_files = show_gdrive_file_menu(gdrive_files_with_metadata, curated_sb_lecture_list)

        if not selected_files:
            print(f"\n{Fore.YELLOW}👋 No files selected. Goodbye!")
            return

        # Prepare selected files for processing (they'll be downloaded later)
        for file_info in selected_files:
            valid_files.append({
                'gdrive_file_id': file_info['id'],
                'gdrive_filename': file_info['name'],
                'date': file_info['date'],
                'class': file_info['class'],
                'title': file_info['title'],
                'professor': file_info['professor'],
                'metadata': {
                    'title': file_info['title'],
                    'class': file_info['class'],
                    'professor': file_info['professor'],
                    'date': file_info['date']
                },
                'from_gdrive': True  # Flag to indicate this needs downloading
            })

    # Show processing summary
    show_processing_summary(valid_files, args.yes)

    if not valid_files:
        print(
            f"\n{Fore.GREEN}🎉 All done! Check your Next.js app to view transcriptions.")
        return

    # Process each file
    print(f"\n{Fore.MAGENTA}🚀 Starting processing...")

    for i, file_info in enumerate(valid_files, 1):
        print(f"\n{Fore.CYAN}{Style.BRIGHT}{'='*60}")
        print(
            f"📝 Processing file {i}/{len(valid_files)}: {file_info['class']}")
        print(f"{'='*60}{Style.RESET_ALL}")

        # Confirm file processing
        should_process, final_filename = confirm_file_processing(
            file_info, args.yes)
        if not should_process:
            continue

        try:
            # Handle Google Drive download if needed
            audio_file_path = None
            if file_info.get('from_gdrive'):
                # Download from Google Drive
                print(f"\n{Fore.BLUE}📥 Downloading from Google Drive...")
                with tqdm(total=1, desc="Downloading", colour='blue') as pbar:
                    audio_file_path = download_file_to_temp(
                        file_info['gdrive_file_id'],
                        file_info['gdrive_filename']
                    )
                    pbar.update(1)

                if not audio_file_path:
                    print(f"{Fore.RED}❌ Download failed")
                    continue

                audio_file_path = Path(audio_file_path)
                print(f"{Fore.GREEN}✅ Downloaded successfully")
            else:
                # Use local USB file
                audio_file_path = file_info['file_path']

                # Upload to Google Drive
                print(f"\n{Fore.BLUE}☁️  Uploading to Google Drive...")
                with tqdm(total=1, desc="Uploading", colour='blue') as pbar:
                    gdrive_upload(
                        audio_file_path=str(file_info['file_path']),
                        class_name=file_info['class'],
                        file_name=final_filename
                    )
                    pbar.update(1)
                print(f"{Fore.GREEN}✅ Uploaded successfully")

            # Transcribe audio
            print(f"\n{Fore.BLUE}🎙️  Transcribing audio...")
            with tqdm(total=1, desc="Transcribing", colour='yellow') as pbar:
                transcription_result = processor.run(
                    audio_file_path, file_info['metadata'])
                pbar.update(1)

            lecture_uuid = transcription_result.get('lecture_uuid')
            if not lecture_uuid:
                print(f"{Fore.RED}❌ Transcription failed")
                continue

            print(f"{Fore.GREEN}✅ Transcription completed")

            # Generate insights
            print(f"\n{Fore.BLUE}🧠 Generating study insights...")
            with tqdm(total=4, desc="AI Processing", colour='magenta') as pbar:
                context = {
                    'class': file_info['class'],
                    'professor': file_info['professor'],
                    'title': file_info['title'],
                    'date': file_info['date']
                }

                insights_result = text_processor.run(
                    lecture_uuid,
                    transcription_result['text'],
                    context
                )
                pbar.update(4)

            results = insights_result.get('results', {})
            print(f"{Fore.GREEN}✅ AI insights generated:")
            print(f"   📋 {len(results.get('main_ideas', []))} main concepts")
            print(
                f"   📝 {len(results.get('summary', '').split())} word summary")
            print(f"   🔑 {len(results.get('keywords', []))} key terms")
            print(
                f"   ❓ {len(results.get('questions_to_review', []))} study questions")

        except Exception as e:
            print(f"{Fore.RED}❌ Processing failed: {str(e)}")
            # Cleanup downloaded file if it exists
            if file_info.get('from_gdrive') and audio_file_path and Path(audio_file_path).exists():
                try:
                    Path(audio_file_path).unlink()
                    print(f"{Fore.YELLOW}🗑️  Cleaned up temporary download")
                except:
                    pass
            continue

        # Cleanup downloaded file after successful processing
        if file_info.get('from_gdrive') and audio_file_path and Path(audio_file_path).exists():
            try:
                Path(audio_file_path).unlink()
                print(f"{Fore.GREEN}🗑️  Cleaned up temporary download")
            except:
                pass

    # Final celebration
    print(f"\n{Fore.GREEN}{Style.BRIGHT}{'='*60}")
    print("🎉 ALL PROCESSING COMPLETE! 🎉")
    print("='*60}")
    print(f"{Fore.CYAN}✨ Your lectures are now ready for studying!")
    print(f"💻 Visit your Next.js app to explore the transcriptions")
    print(f"📚 Happy studying, superstar! 📚{Style.RESET_ALL}")


if __name__ == '__main__':
    main()

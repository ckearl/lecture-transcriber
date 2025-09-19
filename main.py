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
from gdrive.read import loop as gdrive_read
from gdrive.upload import upload as gdrive_upload
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
SUPABASE_KEY = os.getenv('SUPABASE_ANON_KEY')


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
    print(f"   💾 Size: {file_info['size_mb']} MB")
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

    total_size = sum(f['size_mb'] for f in files_to_process)
    total_duration = sum(f['duration_seconds'] for f in files_to_process)

    print(f"   Total size: {Fore.YELLOW}{total_size:.1f} MB")
    print(f"   Total duration: {Fore.YELLOW}{format_duration(total_duration)}")

    if not skip_confirmations:
        response = input(
            f"\n{Fore.GREEN}Ready to start processing? (y/n): {Style.RESET_ALL}").lower().strip()
        if response != 'y':
            print(f"{Fore.YELLOW}👋 Goodbye!")
            sys.exit(0)


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

    # Step 2: Check Google Drive
    print(f"\n{Fore.BLUE}☁️  Checking Google Drive...")
    try:
        gdrive_files = gdrive_read()
        print(f"{Fore.GREEN}✅ Found {len(gdrive_files)} files in Google Drive")
    except Exception:
        gdrive_files = []
        print(f"{Fore.YELLOW}⚠️  Could not connect to Google Drive")

    # Step 3: Scan local files
    print(f"\n{Fore.BLUE}📁 Scanning local audio files...")
    audio_recording_dir = Path(os.path.expanduser(
        '~')) / 'projects' / 'lecture-transcriber' / 'audio' / 'senahs_recorder'

    if not audio_recording_dir.exists():
        print(f"{Fore.RED}❌ Audio directory not found: {audio_recording_dir}")
        return

    audio_files = [f for f in audio_recording_dir.iterdir(
    ) if f.is_file() and not f.name.startswith('.')]
    valid_files = []

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
                    file_info['file_path'], file_info['metadata'])
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
            continue

    # Final celebration
    print(f"\n{Fore.GREEN}{Style.BRIGHT}{'='*60}")
    print("🎉 ALL PROCESSING COMPLETE! 🎉")
    print("='*60}")
    print(f"{Fore.CYAN}✨ Your lectures are now ready for studying!")
    print(f"💻 Visit your Next.js app to explore the transcriptions")
    print(f"📚 Happy studying, superstar! 📚{Style.RESET_ALL}")


if __name__ == '__main__':
    main()

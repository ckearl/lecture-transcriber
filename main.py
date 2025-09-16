import os
import pyfiglet
import json
import time
import sys
from pathlib import Path

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

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_ANON_KEY')


def animate_ellipsis(duration_seconds=3, interval_seconds=0.5):
    """
    Animates an ellipsis in the console for a given duration.

    Args:
        duration_seconds (int): The total duration of the animation in seconds.
        interval_seconds (float): The time delay between each frame of the animation.
    """
    start_time = time.time()
    while time.time() - start_time < duration_seconds:
        for i in range(4):  # Cycle through "", ".", "..", "..."
            # '   ' to clear previous longer text
            sys.stdout.write('\rLoading' + '.' * i + '   ')
            sys.stdout.flush()
            time.sleep(interval_seconds)


def print_intro():
    text = "Hi my love <3"

    ascii_art = pyfiglet.figlet_format(text, font="larry3d", width=999)
    print(ascii_art)

    time.sleep(1)

    animate_ellipsis(duration_seconds=2, interval_seconds=0.3)


def read_in_supabase():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("Please set SUPABASE_URL and SUPABASE_ANON_KEY environment variables.")
        return

    reader = LectureReader(SUPABASE_URL, SUPABASE_KEY)

    sb_lecture_list = reader.fetch_lecture_list()
    curated_sb_lecture_list = []

    if sb_lecture_list is not None:
        print("✅ Successfully fetched lecture list:")
        for lecture in sb_lecture_list:
            curated_sb_lecture_list.append(
                f"{lecture['date']}: {lecture['class_number']}")

    return curated_sb_lecture_list


def load_lecture_metadata(class_name: str, date_str: str) -> dict:
    """Load lecture metadata from the JSON file."""
    try:
        metadata_path = os.path.join(
            os.path.expanduser('~'),
            'senah',
            'lecture-transcriber',
            'lecture_metadata',
            class_name,
            'data.json'
        )

        with open(metadata_path, 'r') as f:
            metadata = json.load(f)

        lecture_title = metadata.get('lecture_titles', {}).get(
            date_str, f"{class_name} Lecture")
        professor = metadata.get('professor', 'Professor')

        return {
            'title': lecture_title,
            'class': class_name,
            'professor': professor,
            'date': date_str
        }
    except Exception as e:
        print(f"Warning: Could not load metadata for {class_name}: {e}")
        return {
            'title': f"{class_name} Lecture",
            'class': class_name,
            'professor': 'Professor',
            'date': date_str
        }


def main():
    # Initialize processors
    processor = TranscriptionProcessor(SUPABASE_URL, SUPABASE_KEY)
    text_processor = TextProcessor(SUPABASE_URL, SUPABASE_KEY)

    print_intro()

    # 1. Read in supabase to get list of recorded audio files already transcribed
    print("\n🔍 Checking existing transcriptions in database...")
    curated_sb_lecture_list = read_in_supabase()

    # 2. Read in the recorded audio files from the device
    print("\n📁 Reading local audio files...")
    local_lecture_list = local_read()

    # 3. Compare recordings and determine what needs to be uploaded
    lectures_to_upload = [
        lecture for lecture in local_lecture_list
        if lecture not in curated_sb_lecture_list
    ]

    print(
        f"\n📝 Lectures to process: {', '.join(lectures_to_upload) if lectures_to_upload else 'None'}")

    # 4. Check what's already in Google Drive
    # print("\n☁️ Checking Google Drive...")
    gdrive_files = gdrive_read()
    print(f"Found {len(gdrive_files)} files in Google Drive")

    # 5. Process each audio file
    audio_recording_dir = os.path.join(
        os.path.expanduser('~'),
        'projects',
        'lecture-transcriber',
        'audio',
        'senahs_recorder'
    )

    if not os.path.exists(audio_recording_dir):
        print(f"❌ Audio recording directory not found: {audio_recording_dir}")
        return

    contents = os.listdir(audio_recording_dir)
    audio_files = [f for f in contents if os.path.isfile(
        os.path.join(audio_recording_dir, f))]

    print(f'\n🎵 Found {len(audio_files)} audio files in {audio_recording_dir}')

    for file in audio_files:
        try:
            print(f"\n🔄 Processing file: {file}")

            # Parse file info
            date_str, time_str = parse_date_from_filename(file)
            day_of_week = get_day_of_week_from_date(date_str)
            formatted_time = format_time_string_with_am_pm(time_str)
            hour, minute = map(int, time_str.split(':')[0:2])
            truncated_end_time = truncate_recording_endtime_to_nearest_quarter(
                hour, minute)

            class_time_key = f"{day_of_week}: {truncated_end_time} {'AM' if hour < 12 else 'PM'}"
            if class_time_key[5] == '0':
                class_time_key = f"{day_of_week}: {class_time_key[6:]}"

            class_name = CLASS_TIME_MAPPINGS.get(class_time_key, None)

            if not class_name:
                print(
                    f"⚠️ Skipping {file}: No class mapping found for {class_time_key}")
                continue

            print(
                f"📅 Date: {date_str} | 🕐 Time: {class_time_key} | 📚 Class: {class_name}")

            # Load metadata
            lecture_metadata = load_lecture_metadata(class_name, date_str)

            # Check if already processed
            lecture_identifier = f"{date_str}: {class_name}"
            if lecture_identifier in curated_sb_lecture_list:
                print(f"✅ Already processed: {lecture_identifier}")
                continue

            # Prepare file paths
            audio_file_path = Path(os.path.join(audio_recording_dir, file))
            gdrive_file_name = f"{date_str}_{lecture_metadata['title'].replace(' ', '_')}.mp3"

            # Upload to Google Drive (if not already there)
            print(f"☁️ Uploading to Google Drive...")
            try:
                gdrive_upload(
                    audio_file_path=str(audio_file_path),
                    class_name=class_name,
                    file_name=gdrive_file_name
                )
                print(f"✅ Uploaded to Google Drive: {gdrive_file_name}")
            except Exception as e:
                print(f"⚠️ Google Drive upload failed: {e}")
                # Continue with transcription even if upload fails

            # Transcribe the audio
            print(f"🎙️ Starting transcription...")
            try:
                transcription_result = processor.run(
                    audio_file_path, lecture_metadata)
                lecture_uuid = transcription_result.get('lecture_uuid')

                if not lecture_uuid:
                    print(f"❌ Transcription failed - no lecture UUID returned")
                    continue

                print(
                    f"✅ Transcription completed. Lecture UUID: {lecture_uuid}")

                # Generate text insights
                print(f"🧠 Generating text insights...")
                try:
                    context = {
                        'class': lecture_metadata['class'],
                        'professor': lecture_metadata['professor'],
                        'title': lecture_metadata['title'],
                        'date': lecture_metadata['date']
                    }

                    insights_result = text_processor.run(
                        lecture_uuid,
                        transcription_result['text'],
                        context
                    )

                    print(f"✅ Text insights completed:")
                    results = insights_result.get('results', {})
                    print(
                        f"   📋 Main ideas: {len(results.get('main_ideas', []))}")
                    print(
                        f"   📝 Summary: {len(results.get('summary', '').split())} words")
                    print(f"   🔑 Keywords: {len(results.get('keywords', []))}")
                    print(
                        f"   ❓ Questions: {len(results.get('questions_to_review', []))}")

                except Exception as e:
                    print(f"❌ Text insights failed: {e}")
                    # Continue even if insights fail - transcription is still saved

            except Exception as e:
                print(f"❌ Transcription failed: {e}")
                continue

        except ValueError as ve:
            print(f"⚠️ Skipping file {file}: {ve}")
        except Exception as e:
            print(f"❌ Error processing {file}: {e}")

    print(f"\n🎉 Processing complete!")


if __name__ == '__main__':
    main()

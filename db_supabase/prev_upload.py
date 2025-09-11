import os
import glob
from upload import LectureUploader

# Initialize uploader
uploader = LectureUploader(
     os.getenv('SUPABASE_URL'),
     os.getenv('SUPABASE_ANON_KEY')
     )

 # Fix the path - use os.path.expanduser() to expand ~
json_files = glob.glob(os.path.expanduser(
      '~/projects/lecture-transcriber/transcriptions/*/*.json'))

  # Debug: Print what files were found
print(f"Found {len(json_files)} JSON files:")
for file in json_files:
    print(f"  - {file}")

    # Upload each file
for json_file in json_files:
    try:
        lecture_id = uploader.upload_lecture_from_json(json_file)
        print(f"✓ Uploaded {os.path.basename(json_file)}: {lecture_id}")
    except Exception as e:
        print(f"✗ Failed to upload {os.path.basename(json_file)}: {e}")

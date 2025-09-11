import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from supabase import create_client, Client
import os


class LectureUploader:
    def __init__(self, supabase_url: str, supabase_key: str):
        """Initialize Supabase client"""
        self.supabase: Client = create_client(supabase_url, supabase_key)

    def upload_lecture_from_json(self, json_file_path: str) -> str:
        """
        Upload a lecture from JSON file to Supabase
        Returns the lecture_id of the created lecture
        """
        try:
            # Load JSON data
            with open(json_file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)

            return self.upload_lecture_from_dict(data)

        except Exception as e:
            print(f"Error uploading lecture: {str(e)}")
            raise

    def upload_lecture_from_dict(self, data: Dict[str, Any]) -> str:
        """
        Upload a lecture from dictionary to Supabase
        Returns the lecture_id of the created lecture
        """
        lecture_id = str(uuid.uuid4())

        try:
            # 1. Insert lecture metadata
            self._insert_lecture_metadata(lecture_id, data)

            # 2. Insert speakers
            self._insert_speakers(lecture_id, data.get('speakers', []))

            # 3. Insert transcript segments
            self._insert_transcript_segments(
                lecture_id, data.get('timestamps', []))

            # 4. Insert full text
            self._insert_full_text(lecture_id, data.get('text', ''))

            # 5. Insert insights
            self._insert_insights(lecture_id, data)

            print(
                f"Successfully uploaded lecture: {data.get('title', 'Unknown')} (ID: {lecture_id})")
            return lecture_id

        except Exception as e:
            # Attempt cleanup on failure
            self._cleanup_failed_upload(lecture_id)
            print(f"Error uploading lecture: {str(e)}")
            raise

    def _insert_lecture_metadata(self, lecture_id: str, data: Dict[str, Any]) -> None:
        """Insert lecture metadata"""
        # Parse duration from timestamps if not provided
        duration_seconds = 0
        if data.get('timestamps'):
            last_timestamp = max(data['timestamps'],
                                 key=lambda x: x.get('end', 0))
            duration_seconds = int(last_timestamp.get('end', 0))

        lecture_data = {
            'id': lecture_id,
            'title': data.get('title', 'Untitled Lecture'),
            'professor': data.get('professor', 'Unknown'),
            'date': data.get('date', datetime.now().strftime('%Y-%m-%d')),
            'duration_seconds': duration_seconds,
            'class_number': data.get('class', 'Unknown'),
            'language': 'en-US'  # Default, could be extracted from data
        }

        result = self.supabase.table('lectures').insert(lecture_data).execute()
        if not result.data:
            raise Exception("Failed to insert lecture metadata")

    def _insert_speakers(self, lecture_id: str, speakers_data: list) -> None:
        """Insert speakers"""
        if not speakers_data:
            return

        speakers_to_insert = []
        for i, speaker in enumerate(speakers_data):
            speakers_to_insert.append({
                'lecture_id': lecture_id,
                'speaker_name': speaker.get('name', f'Speaker {i+1}'),
                'speaker_order': i + 1
            })

        if speakers_to_insert:
            result = self.supabase.table('speakers').insert(
                speakers_to_insert).execute()
            if not result.data:
                raise Exception("Failed to insert speakers")

    def _insert_transcript_segments(self, lecture_id: str, timestamps_data: list) -> None:
        """Insert transcript segments"""
        if not timestamps_data:
            return

        segments_to_insert = []
        for i, segment in enumerate(timestamps_data):
            segments_to_insert.append({
                'lecture_id': lecture_id,
                'start_time': float(segment.get('start', 0)),
                'end_time': float(segment.get('end', 0)),
                'text': segment.get('text', ''),
                'speaker_name': segment.get('speaker'),  # Optional field
                'segment_order': i + 1
            })

        # Insert in batches of 500 to avoid request size limits
        batch_size = 500
        for i in range(0, len(segments_to_insert), batch_size):
            batch = segments_to_insert[i:i + batch_size]
            result = self.supabase.table(
                'transcript_segments').insert(batch).execute()
            if not result.data:
                raise Exception(
                    f"Failed to insert transcript segments batch {i//batch_size + 1}")
            print(
                f"Inserted batch {i//batch_size + 1}/{(len(segments_to_insert) + batch_size - 1)//batch_size}")

    def _insert_full_text(self, lecture_id: str, text: str) -> None:
        """Insert full text"""
        if not text:
            return

        text_data = {
            'lecture_id': lecture_id,
            'text': text
        }

        result = self.supabase.table(
            'lecture_texts').insert(text_data).execute()
        if not result.data:
            raise Exception("Failed to insert full text")

    def _insert_insights(self, lecture_id: str, data: Dict[str, Any]) -> None:
        """Insert AI insights"""
        insights_data = {
            'lecture_id': lecture_id,
            'summary': data.get('summary', ''),
            'key_terms': data.get('keywords', []),
            'main_ideas': data.get('main_ideas', []),
            'review_questions': data.get('questions_to_review', [])
        }

        # Only insert if we have at least some insights
        if any([insights_data['summary'], insights_data['key_terms'],
                insights_data['main_ideas'], insights_data['review_questions']]):
            result = self.supabase.table(
                'text_insights').insert(insights_data).execute()
            if not result.data:
                raise Exception("Failed to insert insights")

    def _cleanup_failed_upload(self, lecture_id: str) -> None:
        """Clean up partially uploaded data if upload fails"""
        try:
            # Delete in reverse order of dependencies
            self.supabase.table('text_insights').delete().eq(
                'lecture_id', lecture_id).execute()
            self.supabase.table('lecture_texts').delete().eq(
                'lecture_id', lecture_id).execute()
            self.supabase.table('transcript_segments').delete().eq(
                'lecture_id', lecture_id).execute()
            self.supabase.table('speakers').delete().eq(
                'lecture_id', lecture_id).execute()
            self.supabase.table('lectures').delete().eq(
                'id', lecture_id).execute()
            print(f"Cleaned up failed upload for lecture_id: {lecture_id}")
        except Exception as cleanup_error:
            print(f"Error during cleanup: {str(cleanup_error)}")

# Usage example


def upload_lecture(file_path: Optional[str] = None):
    # Initialize with your Supabase credentials
    SUPABASE_URL = os.getenv('SUPABASE_URL')  # or your actual URL
    SUPABASE_KEY = os.getenv('SUPABASE_ANON_KEY')  # or your actual key

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("Please set SUPABASE_URL and SUPABASE_ANON_KEY environment variables")
        return

    uploader = LectureUploader(SUPABASE_URL, SUPABASE_KEY)

    # Upload a single JSON file
    try:
        lecture_id = uploader.upload_lecture_from_json(
            'path/to/your/lecture.json')
        print(f"Lecture uploaded successfully with ID: {lecture_id}")
    except Exception as e:
        print(f"Upload failed: {e}")

# Batch upload function


def batch_upload_lectures(json_files: list, supabase_url: str, supabase_key: str):
    """Upload multiple lecture JSON files"""
    uploader = LectureUploader(supabase_url, supabase_key)
    results = []

    for json_file in json_files:
        try:
            lecture_id = uploader.upload_lecture_from_json(json_file)
            results.append(
                {'file': json_file, 'lecture_id': lecture_id, 'status': 'success'})
        except Exception as e:
            results.append(
                {'file': json_file, 'error': str(e), 'status': 'failed'})

    return results


if __name__ == "__main__":
    upload_lecture()

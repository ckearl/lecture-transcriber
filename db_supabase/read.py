import os
from typing import List, Optional, Dict, Any
from .db_models import LectureMetadata, Speaker, TimestampSegment, TextBody, TextInsights, CompleteLecture

from supabase import create_client, Client

# --- Lecture Reader Class ---

class LectureReader:
    def __init__(self, supabase_url: str, supabase_key: str):
        """Initialize Supabase client."""
        self.supabase: Client = create_client(supabase_url, supabase_key)
        
    def fetch_lecture_list(self) -> Optional[List[Dict[str, Any]]]:
        """
        Fetches a summarized list of all lectures, including their ID, 
        title, class number, and date.
        """
        try:
            result = self.supabase.table('lectures').select(
                'id, title, date, class_number'
            ).order('date', desc=True).execute()

            return result.data if result.data else []

        except Exception as e:
            print(f"❌ Error fetching lecture list: {e}")
            return None

    def fetch_lecture(self, lecture_id: str) -> CompleteLecture:
        """
        Fetches all data for a given lecture_id from Supabase and returns
        a complete, validated Pydantic object.
        """
        try:
            # 1. Fetch data from each table concurrently (more efficient for network I/O)
            # In this simple case, we'll do it sequentially for clarity.
            metadata = self._fetch_lecture_metadata(lecture_id)
            speakers = self._fetch_speakers(lecture_id)
            segments = self._fetch_transcript_segments(lecture_id)
            full_text = self._fetch_full_text(lecture_id)
            insights = self._fetch_insights(lecture_id)

            # 2. Assemble the final Pydantic model
            complete_lecture = CompleteLecture(
                metadata=metadata,
                speakers=speakers,
                segments=segments,
                full_text=full_text,
                insights=insights
            )

            return complete_lecture

        except Exception as e:
            print(f"Error fetching lecture with ID '{lecture_id}': {str(e)}")
            raise

    def _fetch_lecture_metadata(self, lecture_id: str) -> LectureMetadata:
        """Fetch metadata from the 'lectures' table."""
        result = self.supabase.table('lectures').select(
            "*").eq('id', lecture_id).execute()
        if not result.data:
            raise ValueError(f"Lecture with id '{lecture_id}' not found.")
        return LectureMetadata(**result.data[0])

    def _fetch_speakers(self, lecture_id: str) -> List[Speaker]:
        """Fetch speakers from the 'speakers' table, ordered correctly."""
        result = self.supabase.table('speakers').select("*").eq(
            'lecture_id', lecture_id).order('speaker_order').execute()
        # A lecture might not have speakers, so returning an empty list is valid.
        return [Speaker(**s) for s in result.data]

    def _fetch_transcript_segments(self, lecture_id: str) -> List[TimestampSegment]:
        """Fetch transcript segments from 'transcript_segments', ordered chronologically."""
        result = self.supabase.table('transcript_segments').select("*").eq(
            'lecture_id', lecture_id).order('segment_order').execute()
        if not result.data:
            print(
                f"Warning: No transcript segments found for lecture '{lecture_id}'.")
        return [TimestampSegment(**s) for s in result.data]

    def _fetch_full_text(self, lecture_id: str) -> TextBody:
        """Fetch the full text from the 'lecture_texts' table."""
        result = self.supabase.table('lecture_texts').select(
            "*").eq('lecture_id', lecture_id).execute()
        if not result.data:
            raise ValueError(
                f"Full text not found for lecture '{lecture_id}'.")
        return TextBody(**result.data[0])

    def _fetch_insights(self, lecture_id: str) -> TextInsights:
        """Fetch AI insights from the 'text_insights' table."""
        result = self.supabase.table('text_insights').select(
            "*").eq('lecture_id', lecture_id).execute()
        if not result.data:
            raise ValueError(f"Insights not found for lecture '{lecture_id}'.")
        return TextInsights(**result.data[0])
    


# --- Usage Example ---

def main():
    """Example of how to use the LectureReader."""
    # Initialize with your Supabase credentials from environment variables
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_ANON_KEY')

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("Please set SUPABASE_URL and SUPABASE_ANON_KEY environment variables.")
        return

    reader = LectureReader(SUPABASE_URL, SUPABASE_KEY)

    # --- Replace this with a real lecture ID from your database ---
    LECTURE_ID_TO_FETCH = 'f47ac10b-58cc-4372-a567-0e02b2c3d479'  # Example UUID

    try:
        print(f"Attempting to fetch lecture with ID: {LECTURE_ID_TO_FETCH}")
        complete_lecture = reader.fetch_lecture(LECTURE_ID_TO_FETCH)

        print("\n✅ Successfully fetched and validated lecture data!")
        print("-------------------------------------------------")
        print(f"Title: {complete_lecture.metadata.title}")
        print(f"Professor: {complete_lecture.metadata.professor}")
        print(f"Date: {complete_lecture.metadata.date}")
        print(f"Number of Speakers: {len(complete_lecture.speakers)}")
        print(
            f"Number of Transcript Segments: {len(complete_lecture.segments)}")
        # Print first 100 chars
        print(f"Summary: {complete_lecture.insights.summary[:100]}...")
        print("-------------------------------------------------")

        # You can now work with the structured Pydantic object
        # For example, to access the text of the first segment:
        if complete_lecture.segments:
            print(
                f"\nFirst segment text: '{complete_lecture.segments[0].text}'")

    except Exception as e:
        print(f"\n❌ Failed to fetch lecture: {e}")


if __name__ == "__main__":
    main()

import os
import json
import asyncio
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import logging
import uuid

import whisper
from supabase import create_client, Client

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TranscriptionProcessor:
    def __init__(self, supabase_url: str = None, supabase_key: str = None):
        """Initialize Whisper model, Supabase client, and tracking dictionaries."""
        self.model = whisper.load_model("base")
        self.status_tracker: Dict[str, str] = {}
        self.progress_tracker: Dict[str, str] = {}
        self.transcriptions_dir = Path("transcriptions")
        self.transcriptions_dir.mkdir(exist_ok=True)

        # Initialize Supabase client
        self.supabase_url = supabase_url or os.getenv('SUPABASE_URL')
        self.supabase_key = supabase_key or os.getenv('SUPABASE_ANON_KEY')

        if self.supabase_url and self.supabase_key:
            self.supabase: Client = create_client(
                self.supabase_url, self.supabase_key)
            logger.info("Supabase client initialized successfully")
        else:
            logger.error("Supabase credentials not found")
            self.supabase = None

        logger.info("Whisper model loaded successfully")

    def get_status(self, transcription_uuid: str) -> str:
        """Get the current status of a transcription."""
        return self.status_tracker.get(transcription_uuid, "not_found")

    def get_progress(self, transcription_uuid: str) -> str:
        """Get the current progress of a transcription."""
        return self.progress_tracker.get(transcription_uuid, "No progress available")

    def update_status(self, transcription_uuid: str, status: str):
        """Update transcription status."""
        self.status_tracker[transcription_uuid] = status
        logger.info(f"Status updated for {transcription_uuid}: {status}")

    def update_progress(self, transcription_uuid: str, progress: str):
        """Update transcription progress."""
        self.progress_tracker[transcription_uuid] = progress
        logger.info(f"Progress updated for {transcription_uuid}: {progress}")

    def create_class_directory(self, class_name: str) -> Path:
        """Create directory for class if it doesn't exist."""
        class_dir = self.transcriptions_dir / class_name
        class_dir.mkdir(exist_ok=True)
        return class_dir

    def generate_filename(self, date: str) -> str:
        """Generate filename based on date: YYYY_MM_DD.json"""
        # Convert YYYY-MM-DD to YYYY_MM_DD
        date_formatted = date.replace("-", "_")
        return f"{date_formatted}.json"

    def save_transcription_json(self, transcription_data: Dict[str, Any], class_name: str, title: str, date: str):
        """Save transcription data to JSON file."""
        class_dir = self.create_class_directory(class_name)
        filename = self.generate_filename(date)
        filepath = class_dir / filename

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(transcription_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Transcription saved to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save transcription: {e}")
            raise

    def save_to_supabase(self, transcription_data: Dict[str, Any]) -> str:
        """Save transcription data to Supabase and return the lecture UUID."""
        if not self.supabase:
            raise Exception("Supabase client not initialized")

        try:
            lecture_uuid = str(uuid.uuid4())

            # Calculate duration and ensure it's an integer
            duration_seconds = sum([
                segment["end"] - segment["start"]
                for segment in transcription_data["timestamps"]
            ])
            # Convert to integer (round to nearest second)
            duration_seconds = int(round(duration_seconds))

            # 1. Insert into lectures table
            lecture_data = {
                "id": lecture_uuid,
                "title": transcription_data["title"],
                "professor": transcription_data["professor"],
                "date": transcription_data["date"],
                "duration_seconds": duration_seconds,
                "class_number": transcription_data["class"],
                "language": "en-US"
            }

            result = self.supabase.table(
                "lectures").insert(lecture_data).execute()
            logger.info(f"Inserted lecture record: {lecture_uuid}")

            # 2. Insert transcript segments
            segments_data = []
            for i, segment in enumerate(transcription_data["timestamps"]):
                segments_data.append({
                    "lecture_id": lecture_uuid,
                    "start_time": segment["start"],
                    "end_time": segment["end"],
                    "text": segment["text"],
                    "speaker_name": None,  # Will be populated by speaker diarization later
                    "segment_order": i
                })

            if segments_data:
                self.supabase.table("transcript_segments").insert(
                    segments_data).execute()
                logger.info(
                    f"Inserted {len(segments_data)} transcript segments")

            # 3. Insert full text body
            text_data = {
                "lecture_id": lecture_uuid,
                "text": transcription_data["text"]
            }

            self.supabase.table("lecture_texts").insert(text_data).execute()
            logger.info(f"Inserted full lecture text")

            return lecture_uuid

        except Exception as e:
            logger.error(f"Failed to save to Supabase: {e}")
            raise Exception(f"Supabase save failed: {str(e)}")

    def process_whisper_segments(self, result: Dict[str, Any]) -> tuple:
        """Process Whisper result into timestamps and full text."""
        timestamps = []
        full_text_parts = []

        for segment in result.get("segments", []):
            start_time = round(segment["start"], 2)
            end_time = round(segment["end"], 2)
            text = segment["text"].strip()

            # Skip segments with invalid time ranges or empty text
            if end_time <= start_time or not text:
                continue

            timestamp_entry = {
                "start": start_time,
                "end": end_time,
                "text": text
            }
            timestamps.append(timestamp_entry)
            full_text_parts.append(text)

        full_text = " ".join(full_text_parts)
        return timestamps, full_text

    def create_transcription_data(self, metadata: Dict[str, Any], timestamps: list, full_text: str, transcription_uuid: str = None) -> Dict[str, Any]:
        """Create the complete transcription data structure."""
        if not transcription_uuid:
            transcription_uuid = str(uuid.uuid4())

        return {
            "title": metadata["title"],
            "transcription_uuid": transcription_uuid,
            "date": metadata["date"],
            "class": metadata["class"],
            "professor": metadata["professor"],
            "speakers": [
                # TODO: This will be populated by speaker diarization
                # {
                #     "name": "Speaker 1",
                #     "timestamps": [
                #         {"start": 0.0, "end": 10.0, "text": "Speaker 1 says this..."}
                #     ]
                # }
            ],
            "timestamps": timestamps,
            "main_ideas": ["TODO"],  # TODO: Populate with Google Gemini
            "summary": "TODO",       # TODO: Populate with Google Gemini
            "keywords": ["TODO"],    # TODO: Populate with Google Gemini
            # TODO: Populate with Google Gemini
            "questions_to_review": ["TODO"],
            "text": full_text
        }

    def cleanup_temp_file(self, temp_path: Path):
        """Remove temporary audio file after processing."""
        try:
            if temp_path.exists():
                temp_path.unlink()
                logger.info(f"Cleaned up temporary file: {temp_path}")

                # TODO: Upload to S3 before cleanup
                # await self.upload_to_s3(temp_path)

        except Exception as e:
            logger.warning(f"Failed to cleanup temp file {temp_path}: {e}")

    def transcribe_audio(self, audio_path: Path, transcription_uuid: str) -> Dict[str, Any]:
        """Transcribe audio file using Whisper with progress tracking."""
        try:
            self.update_progress(transcription_uuid, "Loading audio file...")

            # Custom progress callback for Whisper
            def progress_callback(progress_info):
                if isinstance(progress_info, dict):
                    if 'progress' in progress_info:
                        progress_pct = int(progress_info['progress'] * 100)
                        self.update_progress(
                            transcription_uuid, f"Transcribing: {progress_pct}%")
                    elif 'message' in progress_info:
                        self.update_progress(
                            transcription_uuid, progress_info['message'])
                else:
                    self.update_progress(
                        transcription_uuid, f"Processing: {str(progress_info)}")

            self.update_progress(transcription_uuid,
                                 "Starting transcription with Whisper...")

            # Transcribe with Whisper (forced to English)
            result = self.model.transcribe(
                str(audio_path),
                language="english",
                verbose=True,
                word_timestamps=True
            )

            self.update_progress(
                transcription_uuid, "Transcription completed, processing results...")

            return result

        except Exception as e:
            logger.error(f"Whisper transcription failed: {e}")
            raise Exception(f"Transcription failed: {str(e)}")

    async def process_transcription(self, audio_path: Path, metadata: Dict[str, Any], sync: bool = True) -> Dict[str, Any]:
        """
        Main transcription processing function.
        Handles both sync and async processing.
        """
        transcription_uuid = str(uuid.uuid4())

        try:
            self.update_status(transcription_uuid, "processing")
            self.update_progress(transcription_uuid,
                                 "Initializing transcription...")

            if sync:
                # Process synchronously
                result = await asyncio.get_event_loop().run_in_executor(
                    None, self.transcribe_audio, audio_path, transcription_uuid
                )
            else:
                # Process in background thread
                def transcribe_in_thread():
                    return self.transcribe_audio(audio_path, transcription_uuid)

                result = await asyncio.get_event_loop().run_in_executor(
                    None, transcribe_in_thread
                )

            # Process results
            self.update_progress(transcription_uuid,
                                 "Processing transcription segments...")
            timestamps, full_text = self.process_whisper_segments(result)

            # Create transcription data
            transcription_data = self.create_transcription_data(
                metadata, timestamps, full_text, transcription_uuid)

            # Save to JSON (local backup)
            # self.update_progress(transcription_uuid,
            #                      "Saving transcription locally...")
            # self.save_transcription_json(
            #     transcription_data,
            #     metadata["class"],
            #     metadata["title"],
            #     metadata["date"]
            # )

            # Save to Supabase
            self.update_progress(transcription_uuid, "Saving to database...")
            lecture_uuid = self.save_to_supabase(transcription_data)

            # Update final status
            self.update_status(transcription_uuid, "completed")
            self.update_progress(transcription_uuid,
                                 "Transcription completed successfully")

            # Don't cleanup temp file here - let main.py handle it
            # self.cleanup_temp_file(temp_path)

            logger.info(
                f"Transcription completed successfully: {transcription_uuid}")

            # Return both UUIDs for text processing
            transcription_data["lecture_uuid"] = lecture_uuid
            return transcription_data

        except Exception as e:
            self.update_status(transcription_uuid, "failed")
            self.update_progress(transcription_uuid,
                                 f"Transcription failed: {str(e)}")

            # Don't cleanup on failure either - let main.py handle it
            # self.cleanup_temp_file(temp_path)

            logger.error(f"Transcription failed for {transcription_uuid}: {e}")
            raise Exception(f"Transcription processing failed: {str(e)}")

    def run(self, audio_path: Path, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sync wrapper for main.py so you can call one method directly.
        """
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If inside a running event loop, create a new one in a thread
            return asyncio.run(self.process_transcription(audio_path, metadata, sync=True))
        else:
            return loop.run_until_complete(self.process_transcription(audio_path, metadata, sync=True))

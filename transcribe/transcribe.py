import os
import json
import asyncio
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import logging

import whisper

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TranscriptionProcessor:
    def __init__(self):
        """Initialize Whisper model and tracking dictionaries."""
        self.model = whisper.load_model("base")
        self.status_tracker: Dict[str, str] = {}
        self.progress_tracker: Dict[str, str] = {}
        self.transcriptions_dir = Path("transcriptions")
        self.transcriptions_dir.mkdir(exist_ok=True)

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

    def process_whisper_segments(self, result: Dict[str, Any]) -> tuple:
        """Process Whisper result into timestamps and full text."""
        timestamps = []
        full_text_parts = []

        for segment in result.get("segments", []):
            timestamp_entry = {
                "start": round(segment["start"], 2),
                "end": round(segment["end"], 2),
                "text": segment["text"].strip()
            }
            timestamps.append(timestamp_entry)
            full_text_parts.append(segment["text"].strip())

        full_text = " ".join(full_text_parts)
        return timestamps, full_text

    def create_transcription_data(self, metadata: Dict[str, Any], timestamps: list, full_text: str) -> Dict[str, Any]:
        """Create the complete transcription data structure."""
        return {
            "title": metadata["title"],
            "transcription_uuid": metadata["transcription_uuid"],
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

    async def process_transcription(self, temp_path: Path, metadata: Dict[str, Any], sync: bool = True) -> Dict[str, Any]:
        """
        Main transcription processing function.
        Handles both sync and async processing.
        """
        transcription_uuid = metadata["transcription_uuid"]

        try:
            self.update_status(transcription_uuid, "processing")
            self.update_progress(transcription_uuid,
                                 "Initializing transcription...")

            if sync:
                # Process synchronously
                result = await asyncio.get_event_loop().run_in_executor(
                    None, self.transcribe_audio, temp_path, transcription_uuid
                )
            else:
                # Process in background thread
                def transcribe_in_thread():
                    return self.transcribe_audio(temp_path, transcription_uuid)

                result = await asyncio.get_event_loop().run_in_executor(
                    None, transcribe_in_thread
                )

            # Process results
            self.update_progress(transcription_uuid,
                                 "Processing transcription segments...")
            timestamps, full_text = self.process_whisper_segments(result)

            # Create transcription data
            transcription_data = self.create_transcription_data(
                metadata, timestamps, full_text)

            # Save to JSON
            self.update_progress(transcription_uuid, "Saving transcription...")
            self.save_transcription_json(
                transcription_data,
                metadata["class"],
                metadata["title"],
                metadata["date"]
            )

            # Update final status
            self.update_status(transcription_uuid, "completed")
            self.update_progress(transcription_uuid,
                                 "Transcription completed successfully")

            # Cleanup temp file
            self.cleanup_temp_file(temp_path)

            logger.info(
                f"Transcription completed successfully: {transcription_uuid}")
            return transcription_data

        except Exception as e:
            self.update_status(transcription_uuid, "failed")
            self.update_progress(transcription_uuid,
                                 f"Transcription failed: {str(e)}")

            # Cleanup on failure
            self.cleanup_temp_file(temp_path)

            logger.error(f"Transcription failed for {transcription_uuid}: {e}")
            raise Exception(f"Transcription processing failed: {str(e)}")

    # TODO: S3 Upload functionality
    async def upload_to_s3(self, file_path: Path) -> str:
        """
        TODO: Upload audio file to S3 bucket
        
        This function will:
        1. Connect to AWS S3 using boto3
        2. Upload the audio file to designated bucket
        3. Return the S3 URL/key for future reference
        4. Handle proper error handling and retry logic
        
        Args:
            file_path: Path to the audio file to upload
            
        Returns:
            str: S3 URL or key of uploaded file
        """
        # TODO: Implement S3 upload
        # import boto3
        # s3_client = boto3.client('s3')
        # bucket_name = os.getenv('S3_BUCKET_NAME')
        # s3_key = f"audio_files/{transcription_uuid}/{file_path.name}"
        # s3_client.upload_file(str(file_path), bucket_name, s3_key)
        # return f"s3://{bucket_name}/{s3_key}"

        logger.info(f"TODO: Upload {file_path} to S3")
        return "s3://placeholder-bucket/placeholder-key"

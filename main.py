import os
import json
import uuid
from datetime import datetime
from typing import List, Optional
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import aiofiles

from transcribe import TranscriptionProcessor
from speaker_diarization import SpeakerDiarizer
from text_processing import TextProcessor

app = FastAPI(title="Lecture Transcription API", version="1.0.0")

# Global instances
transcription_processor = TranscriptionProcessor()
speaker_diarizer = SpeakerDiarizer()
text_processor = TextProcessor()

# Supported audio formats
SUPPORTED_FORMATS = {'.wav', '.mp3', '.m4a', '.flac'}
MAX_SYNC_FILE_SIZE = 50 * 1024 * 1024  # 50MB

# Ensure transcriptions directory exists
TRANSCRIPTIONS_DIR = Path("transcriptions")
TRANSCRIPTIONS_DIR.mkdir(exist_ok=True)


class TranscriptionUploadRequest(BaseModel):
    title: str
    class_name: str
    professor: str
    date: Optional[str] = None


class TranscriptionStatusResponse(BaseModel):
    status: str  # uploading|processing|completed|failed


class TranscriptionProgressResponse(BaseModel):
    progress: str  # Progress description from Whisper


class TranscriptionListItem(BaseModel):
    transcription_uuid: str
    title: str
    date: str
    class_name: str
    professor: str
    status: str


class TranscriptionUploadResponse(BaseModel):
    transcription_uuid: str
    message: str
    processing_type: str  # sync|async


def validate_audio_file(file: UploadFile) -> None:
    """Validate uploaded audio file format and size."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in SUPPORTED_FORMATS:
        supported = ", ".join(SUPPORTED_FORMATS)
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format: {file_ext}. Supported formats: {supported}"
        )


def generate_transcription_uuid() -> str:
    """Generate a short UUID for transcription tracking."""
    return str(uuid.uuid4())


async def save_temp_audio_file(file: UploadFile, transcription_uuid: str) -> Path:
    """Save uploaded audio file temporarily for processing."""
    file_ext = Path(file.filename).suffix.lower()
    temp_path = Path(f"temp_{transcription_uuid}{file_ext}")

    async with aiofiles.open(temp_path, 'wb') as temp_file:
        content = await file.read()
        await temp_file.write(content)

    return temp_path


@app.post("/transcribe", response_model=TranscriptionUploadResponse)
async def transcribe_audio(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(...),
    class_name: str = Form(...),
    professor: str = Form(...),
    date: Optional[str] = Form(None)
):
    """
    Upload audio file for transcription.
    Files ≤50MB are processed synchronously, >50MB asynchronously.
    """
    validate_audio_file(file)

    transcription_uuid = generate_transcription_uuid()

    # Use today's date if not provided
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    # Check file size
    file_content = await file.read()
    file_size = len(file_content)
    await file.seek(0)  # Reset file position

    # Create transcription metadata
    metadata = {
        "title": title,
        "transcription_uuid": transcription_uuid,
        "date": date,
        "class": class_name,
        "professor": professor,
        "file_size": file_size,
        "original_filename": file.filename
    }

    try:
        if file_size <= MAX_SYNC_FILE_SIZE:
            # Process synchronously for small files
            temp_path = await save_temp_audio_file(file, transcription_uuid)
            result = await transcription_processor.process_transcription(
                temp_path, metadata, sync=True
            )

            return TranscriptionUploadResponse(
                transcription_uuid=transcription_uuid,
                message="Transcription completed successfully",
                processing_type="sync"
            )
        else:
            # Process asynchronously for large files
            temp_path = await save_temp_audio_file(file, transcription_uuid)
            background_tasks.add_task(
                transcription_processor.process_transcription,
                temp_path, metadata, sync=False
            )

            return TranscriptionUploadResponse(
                transcription_uuid=transcription_uuid,
                message="Large file uploaded, processing started in background",
                processing_type="async"
            )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Transcription failed: {str(e)}")


@app.get("/transcribe/status/{transcription_uuid}", response_model=TranscriptionStatusResponse)
async def get_transcription_status(transcription_uuid: str):
    """Get the current status of a transcription."""
    try:
        status = transcription_processor.get_status(transcription_uuid)
        return TranscriptionStatusResponse(status=status)
    except Exception as e:
        raise HTTPException(
            status_code=404, detail=f"Transcription not found: {str(e)}")


@app.get("/transcribe/progress/{transcription_uuid}", response_model=TranscriptionProgressResponse)
async def get_transcription_progress(transcription_uuid: str):
    """Get the current progress of a transcription."""
    try:
        progress = transcription_processor.get_progress(transcription_uuid)
        return TranscriptionProgressResponse(progress=progress)
    except Exception as e:
        raise HTTPException(
            status_code=404, detail=f"Transcription not found: {str(e)}")


@app.get("/transcription", response_model=List[TranscriptionListItem])
async def list_transcriptions():
    """List all available transcriptions."""
    transcriptions = []

    try:
        for class_dir in TRANSCRIPTIONS_DIR.iterdir():
            if class_dir.is_dir():
                for json_file in class_dir.glob("*.json"):
                    try:
                        with open(json_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)

                        transcriptions.append(TranscriptionListItem(
                            transcription_uuid=data["transcription_uuid"],
                            title=data["title"],
                            date=data["date"],
                            class_name=data["class"],
                            professor=data["professor"],
                            status="completed"
                        ))
                    except (json.JSONDecodeError, KeyError) as e:
                        # Skip malformed files
                        continue

        return transcriptions
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list transcriptions: {str(e)}")


@app.get("/transcription/{transcription_uuid}")
async def get_transcription(transcription_uuid: str):
    """Get a specific transcription by UUID."""
    try:
        # Search through all class directories and their JSON files
        for class_dir in TRANSCRIPTIONS_DIR.iterdir():
            if not class_dir.is_dir():
                continue

            for json_file in class_dir.glob("*.json"):
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    # Check if this file contains our target UUID
                    if data.get("transcription_uuid") == transcription_uuid:
                        return data

                except (json.JSONDecodeError, KeyError) as e:
                    # Log malformed files but continue searching
                    print(f"Warning: Skipping malformed file {json_file}: {e}")
                    continue
                except Exception as e:
                    # Log other file reading errors but continue
                    print(f"Warning: Error reading file {json_file}: {e}")
                    continue

        # UUID not found in any file
        raise HTTPException(
            status_code=404, detail=f"Transcription with UUID {transcription_uuid} not found")

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Catch any other unexpected errors
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve transcription: {str(e)}")

# TODO: Text Processing Routes


@app.post("/process_text/{transcription_uuid}")
async def trigger_text_processing(transcription_uuid: str):
    """Trigger text processing for a completed transcription (TODO: Implement with Google Gemini)."""
    # TODO: Implement with Google Gemini API
    # This will generate main_ideas, summary, keywords, and questions_to_review
    try:
        result = await text_processor.process_text(transcription_uuid)
        return {"message": "Text processing started", "uuid": transcription_uuid}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Text processing failed: {str(e)}")


@app.get("/process_text/{transcription_uuid}")
async def get_processed_text(transcription_uuid: str):
    """Get processed text results (TODO: Implement)."""
    # TODO: Return processed text results from Google Gemini
    try:
        result = text_processor.get_processed_results(transcription_uuid)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=404, detail=f"Processed text not found: {str(e)}")

# TODO: Speaker Diarization Routes


@app.post("/diarize/{transcription_uuid}")
async def trigger_speaker_diarization(transcription_uuid: str):
    """Trigger speaker diarization for a transcription (TODO: Implement with pyannote.audio)."""
    # TODO: Implement with pyannote.audio (Hugging Face)
    try:
        result = await speaker_diarizer.diarize_speakers(transcription_uuid)
        return {"message": "Speaker diarization started", "uuid": transcription_uuid}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Speaker diarization failed: {str(e)}")


@app.get("/diarize/{transcription_uuid}")
async def get_diarization_results(transcription_uuid: str):
    """Get speaker diarization results (TODO: Implement)."""
    # TODO: Return speaker diarization results from pyannote.audio
    try:
        result = speaker_diarizer.get_diarization_results(transcription_uuid)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=404, detail=f"Diarization results not found: {str(e)}")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "message": "Lecture Transcription API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

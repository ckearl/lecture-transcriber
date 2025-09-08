from datetime import datetime
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Form
from fastapi.responses import Response, JSONResponse
from pathlib import Path
from pydantic import BaseModel
from typing import List, Optional
import aiofiles
import asyncio
import json
import os
import uuid

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

@app.post("/process_text/{transcription_uuid}")
async def trigger_text_processing(transcription_uuid: str):
    """Trigger text processing for a completed transcription."""
    try:
        result = await text_processor.process_text(transcription_uuid)
        return {"message": "Text processing started", "uuid": transcription_uuid}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Text processing failed: {str(e)}")

@app.get("/process_text/{transcription_uuid}")
async def get_processed_text(transcription_uuid: str):
    """Get processed text results."""
    try:
        result = text_processor.get_processed_results(transcription_uuid)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=404, detail=f"Processed text not found: {str(e)}")


# WIP
@app.post("/diarize/{transcription_uuid}")
async def trigger_speaker_diarization(
    transcription_uuid: str,
    audio_file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None
):
    """
    Trigger speaker diarization for a transcription with audio file upload.
    Accepts both the transcription UUID (to locate existing JSON) and audio file (for processing).
    """
    try:
        # Validate audio file
        validate_audio_file(audio_file)

        # Check if transcription exists
        transcription_data = None
        json_file_path = None

        # Search for existing transcription
        for class_dir in TRANSCRIPTIONS_DIR.iterdir():
            if class_dir.is_dir():
                for json_file in class_dir.glob("*.json"):
                    try:
                        with open(json_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        if data.get("transcription_uuid") == transcription_uuid:
                            transcription_data = data
                            json_file_path = json_file
                            break
                    except (json.JSONDecodeError, KeyError):
                        continue
                if transcription_data:
                    break

        if not transcription_data:
            raise HTTPException(
                status_code=404,
                detail=f"Transcription with UUID {transcription_uuid} not found"
            )

        # Check if diarization is already in progress
        current_status = speaker_diarizer.get_diarization_status(
            transcription_uuid)
        if current_status in ["starting", "preprocessing", "diarizing", "mapping_speakers"]:
            return {
                "message": f"Diarization already in progress for {transcription_uuid}",
                "status": current_status,
                "transcription_uuid": transcription_uuid
            }

        # Read audio file content
        audio_content = await audio_file.read()

        # Check file size for processing decision
        file_size = len(audio_content)

        if file_size <= MAX_SYNC_FILE_SIZE:
            # Process synchronously for smaller files
            result = await speaker_diarizer.diarize_speakers(
                transcription_uuid, audio_content, audio_file.filename
            )
            return result
        else:
            # Process asynchronously for larger files
            if background_tasks:
                background_tasks.add_task(
                    speaker_diarizer.diarize_speakers,
                    transcription_uuid, audio_content, audio_file.filename
                )
            else:
                # If no background_tasks available, process anyway but warn
                asyncio.create_task(
                    speaker_diarizer.diarize_speakers(
                        transcription_uuid, audio_content, audio_file.filename
                    )
                )

            return {
                "message": f"Large file received, diarization started in background",
                "status": "starting",
                "transcription_uuid": transcription_uuid,
                "file_size_mb": round(file_size / (1024 * 1024), 2)
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Speaker diarization failed: {str(e)}")

# WIP
@app.get("/diarize/{transcription_uuid}")
async def get_diarization_results(transcription_uuid: str):
    """Get speaker diarization results and status."""
    try:
        # Get current status
        status = speaker_diarizer.get_diarization_status(transcription_uuid)

        # Get results if available
        results = speaker_diarizer.get_diarization_results(transcription_uuid)

        response_data = {
            "transcription_uuid": transcription_uuid,
            "status": status
        }

        if results:
            response_data.update(results)

        # If completed, also get statistics
        if status == "completed" and results:
            stats = speaker_diarizer.get_speaker_statistics(transcription_uuid)
            if stats:
                response_data["detailed_statistics"] = stats

        return response_data

    except Exception as e:
        raise HTTPException(
            status_code=404, detail=f"Diarization results not found: {str(e)}")

# WIP
@app.get("/diarize/{transcription_uuid}/status")
async def get_diarization_status_only(transcription_uuid: str):
    """Get only the current diarization status (lightweight endpoint)."""
    try:
        status = speaker_diarizer.get_diarization_status(transcription_uuid)
        return {
            "transcription_uuid": transcription_uuid,
            "status": status
        }
    except Exception as e:
        raise HTTPException(
            status_code=404, detail=f"Status not found: {str(e)}")

# WIP
@app.get("/diarize/{transcription_uuid}/statistics")
async def get_speaker_statistics(transcription_uuid: str):
    """Get detailed speaker statistics for a completed diarization."""
    try:
        stats = speaker_diarizer.get_speaker_statistics(transcription_uuid)
        if not stats:
            raise HTTPException(
                status_code=404,
                detail="Statistics not available - diarization may not be completed"
            )
        return stats
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get statistics: {str(e)}")

# WIP
@app.get("/diarize/{transcription_uuid}/export/{format}")
async def export_diarization_results(transcription_uuid: str, format: str):
    """
    Export diarization results in various formats.
    Supported formats: json, csv, txt
    """
    try:
        if format.lower() not in ["json", "csv", "txt"]:
            raise HTTPException(
                status_code=400,
                detail="Unsupported format. Use: json, csv, or txt"
            )

        exported_data = speaker_diarizer.export_diarization_results(
            transcription_uuid, format
        )

        if not exported_data:
            raise HTTPException(
                status_code=404,
                detail="Export data not available - diarization may not be completed"
            )

        # Set appropriate content type and filename
        media_types = {
            "json": "application/json",
            "csv": "text/csv",
            "txt": "text/plain"
        }

        filename = f"diarization_{transcription_uuid}.{format.lower()}"

        return Response(
            content=exported_data,
            media_type=media_types[format.lower()],
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Export failed: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "message": "Lecture Transcription API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

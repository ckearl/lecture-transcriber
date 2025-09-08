# Example API calls

Here are example curl commands to test your FastAPI transcription backend with the audio files in your `/audio` folder:

## **1. Upload and Transcribe Audio Files**

Replace `sample_lecture.mp3` with your actual audio filename:

```bash
# Basic transcription upload
curl -X POST "http://localhost:8000/transcribe" \
  -F "file=@audio/partials/econ159_07_092607_split_005.mp3" \
  -F "title=Game Theory" \
  -F "class_name=Econ 159" \
  -F "professor=Dr. Johnson"

curl -X POST "http://localhost:8000/transcribe" \
  -F "file=@audio/partials/econ159_07_092607_split_008.mp3" \
  -F "title=Markets, Supply, and Demand" \
  -F "class_name=Econ 159" \
  -F "professor=Dr. Johnson"

# Upload with specific date
curl -X POST "http://localhost:8000/transcribe" \
  -F "file=@audio/partials/econ159_07_092607_split_010.mp3" \
  -F "title=Impacts of Tariffs on Intl. Markets" \
  -F "class_name=Econ 260" \
  -F "professor=Prof. Lewis"
  -F "date=2024-01-20"

```

```json
{
  "transcription_uuid": "123e4567-e89b-12d3-a456-426614174000",
  "message": "Transcription completed successfully",
  "processing_type": "sync"
}
```

## **2. Check Transcription Status**

Use the UUID returned from the upload:

```bash
# Check if transcription is complete
curl "http://localhost:8000/transcribe/status/{uuid}"
```

Response will be:
```json
{
  "status": "completed"
}
```

Possible status values: `uploading`, `processing`, `completed`, `failed`

## **3. Monitor Progress (During Processing)**

```bash
# Get detailed progress information
curl "http://localhost:8000/transcribe/progress/{uuid}"
```

Response examples:
```json
{
  "progress": "Loading audio file..."
}
```
```json
{
  "progress": "Transcribing: 45%"
}
```
```json
{
  "progress": "Transcription completed successfully"
}
```

## **4. List All Transcriptions**

```bash
# Get list of all completed transcriptions
curl "http://localhost:8000/transcription"
```

Response:
```json
[
  {
    "transcription_uuid": "123e4567-e89b-12d3-a456-426614174000",
    "title": "Introduction to Financial Markets",
    "date": "2024-01-20",
    "class_name": "Finance",
    "professor": "Dr. Johnson",
    "status": "completed"
  },
  {
    "transcription_uuid": "456e7890-e89b-12d3-a456-426614174001",
    "title": "Consumer Behavior Analysis", 
    "date": "2024-01-20",
    "class_name": "Marketing",
    "professor": "Prof. Davis",
    "status": "completed"
  }
]
```

## **5. Get Full Transcription Content**

```bash
# Retrieve complete transcription data
curl "http://localhost:8000/transcription/{uuid}"
```

This returns the complete JSON structure with timestamps, text, and placeholder fields for future AI features.

## **6. Health Check**

```bash
# Verify API is running
curl "http://localhost:8000/health"
```

## **7. Testing Large vs Small Files**

For files larger than 50MB, you'll get async processing:

```bash
curl -X POST "http://localhost:8000/transcribe" \
  -F "file=@audio/long_lecture.wav" \
  -F "title=Advanced Corporate Strategy" \
  -F "class_name=Strategy" \
  -F "professor=Dr. Martinez"
```

Response for large files:
```json
{
  "transcription_uuid": "789e0123-e89b-12d3-a456-426614174002",
  "message": "Large file uploaded, processing started in background", 
  "processing_type": "async"
}
```

## **8. Process Text**

Process text for `main_ideas`, `summary`, `keywords`, `questions_to_review`:

```bash
curl -X POST "http://localhost:8000/process_text/{uuid}"
```

GET results of text processing:

```bash
curl "http://localhost:8000/process_text/{uuid}"
```

## **9. Diarize Audio**

```bash
curl -X POST "http://localhost:8000/diarize/e59fceef-3a95-410e-b5b4-09687fcbd981" \
  -F "audio_file=@/partials/econ159_07_092607_split_005.mp3"
```

```bash
curl -X POST "http://localhost:8000/diarize/93637449-90a8-48b8-9704-a637b559b5eb" \
  -F "audio_file=@/partials/econ159_07_092607_split_010.mp3"
```

## Complete Testing Workflow**

Here's a complete test sequence:

```bash
# 1. Upload audio
RESPONSE=$(curl -s -X POST "http://localhost:8000/transcribe" \
  -F "file=@audio/sample_lecture.mp3" \
  -F "title=Test Lecture" \
  -F "class_name=TestClass" \
  -F "professor=Test Professor")

# Extract UUID (you'll need to parse JSON or copy manually)
UUID="paste-uuid-here"

# 2. Check status immediately
curl "http://localhost:8000/transcribe/status/$UUID"

# 3. Monitor progress (repeat as needed)
curl "http://localhost:8000/transcribe/progress/$UUID"

# 4. Get completed transcription
curl "http://localhost:8000/transcription/$UUID"

# 5. List all transcriptions
curl "http://localhost:8000/transcription"
```

## **Tips:**

- **For JSON Pretty Printing**: Add `| jq` to any curl command if you have jq installed
- **Save UUIDs**: Copy the transcription_uuid from upload responses for status checking
- **File Paths**: Make sure your audio files are actually in the `/audio` directory
- **Supported Formats**: Test with .wav, .mp3, .m4a, or .flac files
- **Processing Time**: Expect ~1-2 minutes per hour of audio with the Whisper "base" model

Try these commands with your actual audio files to test the full transcription workflow!
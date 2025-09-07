# Example API calls

Here are example curl commands to test your FastAPI transcription backend with the audio files in your `/audio` folder:

## **1. Upload and Transcribe Audio Files**

Replace `sample_lecture.mp3` with your actual audio filename:

```bash
# Basic transcription upload
curl -X POST "http://localhost:8000/transcribe" \
  -F "file=@audio/sample_lecture.mp3" \
  -F "title=Introduction to Financial Markets" \
  -F "class_name=Finance" \
  -F "professor=Dr. Johnson"

# Upload with specific date
curl -X POST "http://localhost:8000/transcribe" \
  -F "file=@audio/marketing_lecture.wav" \
  -F "title=Consumer Behavior Analysis" \
  -F "class_name=Marketing" \
  -F "professor=Prof. Davis" \
  -F "date=2024-01-20"

# Upload operations lecture
curl -X POST "http://localhost:8000/transcribe" \
  -F "file=@audio/operations_class.m4a" \
  -F "title=Supply Chain Management" \
  -F "class_name=Operations" \
  -F "professor=Dr. Wilson"
```

Each upload will return a response like:
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
curl "http://localhost:8000/transcribe/status/123e4567-e89b-12d3-a456-426614174000"
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
curl "http://localhost:8000/transcribe/progress/123e4567-e89b-12d3-a456-426614174000"
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
curl "http://localhost:8000/transcription/123e4567-e89b-12d3-a456-426614174000"
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

## **8. Complete Testing Workflow**

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
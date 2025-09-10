# Lecture Transcription API

A FastAPI-based application for transcribing MBA lecture recordings with automated text analysis and speaker identification. Built to provide Otter.ai-like functionality for academic use.

## Features

- **Audio Transcription**: Uses OpenAI Whisper for accurate speech-to-text conversion
- **AI Text Analysis**: Google Gemini-powered extraction of main ideas, summaries, keywords, and study questions
- **Speaker Diarization**: Identifies and separates different speakers in recordings using pyannote.audio
- **Multiple Audio Formats**: Supports WAV, MP3, M4A, and FLAC files
- **Sync/Async Processing**: Small files (≤50MB) processed synchronously, larger files processed in background

## Installation

### Prerequisites

```bash
# Python 3.8+
pip install fastapi uvicorn whisper google-generativeai pyannote.audio torch torchaudio aiofiles
```

### Environment Variables

```bash
GOOGLE_GEMINI_API_KEY=your_gemini_api_key
HUGGINGFACE_API_KEY=your_huggingface_token  # Required for speaker diarization
```

### Running the Application

```bash
python main.py
# or
uvicorn main:app --host 0.0.0.0 --port 8000
```

## API Endpoints

### Core Transcription

- `POST /transcribe` - Upload audio file for transcription
- `GET /transcribe/status/{uuid}` - Get transcription status
- `GET /transcribe/progress/{uuid}` - Get processing progress
- `GET /transcription` - List all transcriptions
- `GET /transcription/{uuid}` - Get specific transcription data

### Text Processing

- `POST /process_text/{uuid}` - Trigger AI text analysis
- `GET /process_text/{uuid}` - Get processed text results

### Speaker Diarization (WIP)

- `POST /diarize/{uuid}` - Upload audio for speaker identification
- `GET /diarize/{uuid}` - Get diarization results
- `GET /diarize/{uuid}/statistics` - Get detailed speaker statistics
- `GET /diarize/{uuid}/export/{format}` - Export results (json/csv/txt)

### Health Check

- `GET /health` - Application status

## Data Format

### Transcription Upload

```
POST /transcribe
Content-Type: multipart/form-data

title: string (required) - Lecture title
class_name: string (required) - Course name
professor: string (required) - Professor name
date: string (optional) - YYYY-MM-DD format, defaults to today
file: audio file (required) - WAV/MP3/M4A/FLAC
```

### Transcription Output Structure

```json
{
  "title": "Game Theory",
  "transcription_uuid": "e59fceef-3a95-410e-b5b4-09687fcbd981",
  "date": "2025-09-07",
  "class": "Econ 159",
  "professor": "Dr. Johnson",
  "speakers": [
    {
      "name": "Dr. Johnson",
      "role": "Professor",
      "timestamps": [
        {
          "start": 0.0,
          "end": 5.24,
          "text": "So another thing to remark here..."
        }
      ]
    }
  ],
  "timestamps": [
    {
      "start": 0.0,
      "end": 5.24,
      "text": "So another thing to remark here..."
    }
  ],
  "main_ideas": [
    "Different strategy sets lead to radically different market outcomes",
    "Game theory model predictions are highly sensitive to initial assumptions"
  ],
  "summary": "This Econ 159 lecture addresses fundamental challenges...",
  "keywords": [
    "Strategy set",
    "Bertrand model",
    "Perfect competition",
    "Game theory"
  ],
  "questions_to_review": [
    "What is the primary concern regarding strategy set sensitivity?",
    "How does the Bertrand model predict market outcomes?"
  ],
  "text": "Full transcription text..."
}
```

## Application Logic

### 1. Audio Processing Pipeline

1. **Upload Validation**: Checks file format and size
2. **Temporary Storage**: Saves audio file for processing
3. **Whisper Transcription**: Converts speech to text with timestamps
4. **JSON Generation**: Creates structured output with metadata
5. **File Cleanup**: Removes temporary files

### 2. Text Analysis Pipeline

1. **Text Chunking**: Splits long transcriptions for API processing
2. **Gemini Processing**: Generates main ideas, summary, keywords, questions
3. **JSON Update**: Merges AI analysis with existing transcription
4. **Quality Control**: Ensures minimum content requirements

### 3. Speaker Diarization Pipeline

1. **Audio Preprocessing**: Converts to optimal format (16kHz mono)
2. **Pyannote Processing**: Identifies speaker segments
3. **Timestamp Mapping**: Aligns speakers with transcription text
4. **Name Assignment**: Labels speakers based on speaking patterns
5. **JSON Integration**: Updates transcription with speaker data

## File Structure

```
project/
├── main.py                 # FastAPI application and routes
├── transcribe.py          # Whisper transcription processor
├── text_processing.py     # Google Gemini text analysis
├── speaker_diarization.py # Pyannote speaker identification
└── transcriptions/        # Output directory
    └── {class_name}/      # Organized by course
        └── YYYY_MM_DD.json # Daily lecture files
```

## Processing Status Values

- `uploading` - File being uploaded
- `processing` - Audio being transcribed
- `completed` - Transcription finished
- `failed` - Processing error occurred
- `starting` - Text/speaker processing initiated
- `generating_*` - Specific AI processing steps

## Error Handling

The application includes comprehensive error handling for:

- Unsupported file formats
- API key validation
- Processing failures
- Large file handling
- Malformed JSON recovery

## Limitations

- Maximum sync file size: 50MB
- Supported formats: WAV, MP3, M4A, FLAC
- Speaker diarization requires Hugging Face authentication
- Gemini API has rate limiting and token limits
- Processing time scales with audio duration

## Development Status

- ✅ Audio transcription (Whisper)
- ✅ Text processing (Gemini)
- 🚧 Speaker diarization (functional, needs refinement)
- 📋 Future: S3 storage, advanced speaker naming, batch processing

## License

MIT

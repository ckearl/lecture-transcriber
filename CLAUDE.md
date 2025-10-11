# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a lecture transcription and analysis system that:
1. Automatically processes audio recordings from MBA classes
2. Transcribes them using OpenAI Whisper
3. Generates AI-powered study materials using Google Gemini
4. Uploads to Google Drive and stores in Supabase

The system is designed for a personal use case with a fixed class schedule and specific directory structure.

## Development Commands

### Running the Application

```bash
# Run main processing pipeline
python main.py

# Skip all confirmations (useful for automated processing)
python main.py -y
# or
python main.py --yes
```

The main script will:
- Check Supabase for existing transcriptions
- Scan Google Drive for previously uploaded files
- Process local audio files from `~/projects/lecture-transcriber/audio/senahs_recorder`
- Upload to Google Drive, transcribe, and generate insights

### Environment Setup

Required environment variables in `.env`:
- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_ANON_KEY` - Supabase anonymous key
- `SUPABASE_SERVICE_KEY` - Supabase service role key (for admin operations)
- `GOOGLE_GEMINI_API_KEY` - Google Gemini API key for text insights

### Dependencies

This project uses:
- `whisper` - OpenAI Whisper for transcription
- `google-generativeai` - Google Gemini for AI insights
- `supabase` - Supabase Python client
- `google-auth` + `google-api-python-client` - Google Drive API
- `pydantic` - Data validation
- `pyfiglet`, `tqdm`, `colorama` - CLI UI enhancements

## Architecture Overview

### Core Processing Pipeline (main.py)

The application follows a strict sequential pipeline:

1. **Discovery Phase**: Checks existing data in Supabase and Google Drive
2. **Local Scan**: Finds unprocessed audio files in the local directory
3. **File Processing Loop**: For each unprocessed file:
   - Upload to Google Drive (via `gdrive/upload.py`)
   - Transcribe audio (via `transcribe/transcribe.py`)
   - Generate AI insights (via `text_insights/process.py`)

### Module Structure

#### transcribe/transcribe.py - TranscriptionProcessor

Handles Whisper-based audio transcription:
- Loads Whisper "base" model on initialization
- Processes audio files to generate timestamped transcripts
- Saves transcription to Supabase in three tables:
  - `lectures` - metadata (title, professor, date, duration, class_number)
  - `transcript_segments` - timestamped text segments
  - `lecture_texts` - full transcript text
- Returns `lecture_uuid` for downstream processing

Key method: `run(audio_path, metadata)` - synchronous wrapper for main.py

#### text_insights/process.py - TextProcessor

Generates study materials using Google Gemini 2.5 Flash:
- **Main Ideas**: 6-8 key concepts from the lecture
- **Summary**: 150-250 word comprehensive summary
- **Keywords**: 12-15 important business/academic terms
- **Review Questions**: 10-12 exam prep questions

Processing details:
- Chunks long transcripts (>30k chars) to fit API limits
- Uses temperature=0.3 for consistent academic analysis
- Saves insights to `text_insights` table in Supabase
- Includes retry logic and graceful fallbacks

Key method: `run(lecture_uuid, transcription_text, context)` - synchronous wrapper

#### db_supabase/

- `upload.py` - LectureUploader class for manual JSON-to-Supabase uploads
- `read.py` - LectureReader class for querying existing lectures
- `db_models.py` - Pydantic models for all database tables

#### local_files/read.py

Parses audio filenames to extract metadata:
- Filename format: `YYYYMMDDHHMMSS.WAV`
- Maps class times to course names via `CLASS_TIME_MAPPINGS`
- Uses end-time truncation to handle recordings that end mid-quarter-hour

#### gdrive/

- `read.py` - Lists files in Google Drive folders per class
- `upload.py` - Uploads audio files to appropriate class folders
- Uses `folder_ids.json` for class-to-folder mapping (gitignored)

### Database Schema (Supabase)

Tables:
- `lectures` - Core lecture metadata
- `transcript_segments` - Individual timestamped segments
- `lecture_texts` - Full transcript text
- `text_insights` - AI-generated study materials (summary, key_terms, main_ideas, review_questions)
- `speakers` - Speaker information (currently unused, prepared for future diarization)

### Audio File Processing Flow

1. Audio files are discovered in `/Volumes/USB-DISK/RECORD`
2. Filename is parsed to extract date and time
3. Time is mapped to class name using day-of-week + time lookup
4. Metadata is loaded from `lecture_metadata/{class_name}/data.json`
5. File is checked against existing database entries to avoid reprocessing

### Class Schedule Mapping

The system uses `CLASS_TIME_MAPPINGS` in `local_files/read.py` to map recording times to courses:
- Mon 8:00 AM = MBA 505 Leadership
- Mon 9:30 AM = MBA 530 Operations Management
- Mon 12:30 PM = MBA 550 Marketing Management
- (and so on for the full weekly schedule)

This mapping is critical - if a recording doesn't match a scheduled class time, it will be skipped.

### Async/Sync Handling

Both `TranscriptionProcessor` and `TextProcessor` use an async-first design but provide sync wrappers:
- Internal methods are async for potential future concurrency
- `run()` methods detect if event loop is running and handle appropriately
- Currently called synchronously from main.py's sequential pipeline

## Important Implementation Details

### Transcription Segment Validation

When saving transcript segments (transcribe/transcribe.py:160-173):
- Skips segments where `end_time <= start_time`
- Skips segments with empty text
- This prevents database constraint violations

### Gemini Prompt Engineering

Text insights prompts (text_insights/process.py:229-367) are specifically tuned for MBA content:
- Emphasizes business frameworks, models, and strategic concepts
- Requests concise, exam-focused outputs
- Explicitly instructs to avoid introductory/concluding fluff
- Uses different chunking strategies per insight type

### User Confirmation Flow

main.py provides interactive confirmations unless `-y` flag is used:
- Shows file details (date, class, size, duration)
- Allows filename editing before upload
- Can skip individual files
- Shows processing summary before starting

### Error Handling

- LectureUploader has cleanup logic to delete partial uploads on failure
- TextProcessor has retry logic (3 attempts with exponential backoff)
- Both processors provide graceful fallbacks with informative error messages

## Metadata Structure

Each class has a `lecture_metadata/{class_name}/data.json` file containing:
```json
{
  "professor": "Professor Name",
  "lecture_titles": {
    "YYYY-MM-DD": "Specific Lecture Title",
    ...
  }
}
```

This metadata is merged with transcription data and passed to AI processors for context-aware insights.

## Common Workflows

### Adding a New Class

1. Add mapping to `CLASS_TIME_MAPPINGS` in `local_files/read.py`
2. Create folder in `lecture_metadata/{class_name}/`
3. Add `data.json` with professor and lecture titles
4. Add folder ID to `gdrive/folder_ids.json`

### Reprocessing a Lecture

The system automatically skips lectures already in Supabase. To reprocess:
1. Delete the lecture from Supabase (will cascade to all related tables)
2. Run `python main.py` - the file will be detected as unprocessed

### Testing Individual Components

Each processor can be instantiated and tested independently:

```python
from transcribe.transcribe import TranscriptionProcessor
processor = TranscriptionProcessor(SUPABASE_URL, SUPABASE_KEY)
result = processor.run(audio_path, metadata)

from text_insights.process import TextProcessor
text_processor = TextProcessor(SUPABASE_URL, SUPABASE_KEY)
insights = text_processor.run(lecture_uuid, transcription_text, context)
```

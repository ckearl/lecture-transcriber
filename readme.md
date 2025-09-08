# MBA Lecture Transcription API

A FastAPI backend application designed for MBA students to upload lecture audio files, transcribe them using OpenAI Whisper, and enhance them with AI-powered analysis. Built specifically for academic use with features like speaker identification, intelligent summarization, and study question generation.

## 🎯 Project Overview

This backend API serves as a comprehensive lecture processing system similar to Otter.ai, tailored for MBA coursework. Students can upload lecture recordings and receive:

- **Accurate Transcriptions** - Using OpenAI Whisper for high-quality speech-to-text
- **Speaker Identification** - Distinguishing between professors and students (TODO)
- **Intelligent Summaries** - Key points and main ideas extraction
- **Study Materials** - Auto-generated review questions and keywords

## 🏗️ Architecture

```
/app
├── main.py                    # FastAPI routes and request handling
├── transcribe.py              # Whisper transcription processing
├── speaker_diarization.py     # Speaker identification (TODO)
├── text_processing.py         # AI text analysis
└── /transcriptions           # JSON storage organized by class
    ├── /Finance
    ├── /Marketing
    └── /Operations
```

## ✨ Features

### Current Implementation

- ✅ **Audio Upload & Validation** - Supports .wav, .mp3, .m4a, .flac formats
- ✅ **Smart Processing** - Sync processing for files ≤50MB, async for larger files
- ✅ **Real-time Progress Tracking** - Monitor transcription progress with descriptive updates
- ✅ **Class-based Organization** - Automatic folder creation and organization by course
- ✅ **Comprehensive Status API** - Track processing status from upload to completion
- ✅ **Robust Error Handling** - Clear error messages and graceful failure handling

### Planned Features (TODO)

- 🔄 **Speaker Diarization** - Using pyannote.audio to identify different speakers
- 🔄 **AI-Powered Analysis** - Google Gemini integration for content analysis
- 🔄 **Cloud Storage** - S3 integration for audio file storage
- 🔄 **Study Materials Generation** - Auto-generated summaries, keywords, and review questions

## 🚀 Quick Start

### Prerequisites

- Python 3.8-3.11
- FFmpeg (for audio processing)
- 4GB+ RAM (for Whisper model)

### Installation

1. **Clone and Setup**

```bash
git clone https://github.com/ckearl/lecture-transcriber.git
cd lecture-transcriber
pip install -r requirements.txt
```

2. **Install Dependencies**

```bash
pip install fastapi uvicorn pydantic openai-whisper aiofiles python-multipart
```

3. **Set Environment Variables** (for future AI features)

```bash
export HUGGINGFACE_API_KEY=your_hf_token
export GOOGLE_GEMINI_API_KEY=your_gemini_key
```

4. **Run the API**

```bash
python main.py
# or
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## 📋 API Endpoints

### Core Transcription

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/transcribe` | POST | Upload audio file for transcription |
| `/transcribe/status/{uuid}` | GET | Get transcription status |
| `/transcribe/progress/{uuid}` | GET | Get detailed progress information |
| `/transcription` | GET | List all transcriptions |
| `/transcription/{uuid}` | GET | Get specific transcription |
| `/process_text/{uuid}` | POST | Trigger AI text analysis |
| `/process_text/{uuid}` | GET | Get AI analysis results |

### Future AI Features (WIP)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/diarize/{uuid}` | POST | Trigger speaker identification |
| `/diarize/{uuid}` | GET | Get speaker diarization results |
| `/diarize/{uuid}/status` | GET | Get speaker diarization status |
| `/diarize/{uuid}/statistics` | GET | Get statistics on the speaker diarization |
| `/diarize/{uuid}/export/{format}` | GET | Export the speaker diarization in a specified format |

### Utility

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | API health check |

## 🔧 Usage Examples

### Upload a Lecture

```bash
curl -X POST "http://localhost:8000/transcribe" \
  -F "file=@lecture.mp3" \
  -F "title=Introduction to Corporate Finance" \
  -F "class_name=Finance" \
  -F "professor=Dr. Smith" \
  -F "date=2024-01-15"
```

### Check Progress

```bash
curl "http://localhost:8000/transcribe/progress/{transcription_uuid}"
```

### Get Transcription

```bash
curl "http://localhost:8000/transcription/{transcription_uuid}"
```

## 📊 Data Structure

### Transcription JSON Format

```json
{
  "title": "Introduction to Corporate Finance",
  "transcription_uuid": "123e4567-e89b-12d3-a456-426614174000",
  "date": "2024-01-15",
  "class": "Finance",
  "professor": "Dr. Smith",
  "speakers": [
    {
      "name": "Dr. Smith",
      "timestamps": [
        {
          "start": 0.0,
          "end": 10.5,
          "text": "Today we'll discuss the fundamentals of corporate finance..."
        }
      ]
    }
  ],
  "timestamps": [
    {
      "start": 0.0,
      "end": 10.5,
      "text": "Today we'll discuss the fundamentals of corporate finance..."
    }
  ],
  "main_ideas": ["Time value of money", "Capital budgeting", "Risk assessment"],
  "summary": "This lecture covered the core principles of corporate finance...",
  "keywords": ["NPV", "IRR", "WACC", "Capital Structure"],
  "questions_to_review": [
    "What is the difference between NPV and IRR?",
    "How does capital structure affect firm value?"
  ],
  "text": "Full transcription text here..."
}
```

## 🔄 Processing Flow

1. **Upload** - Audio file uploaded with metadata
2. **Validation** - File format and size validation
3. **Processing Decision** - Sync (≤50MB) or async (>50MB) processing
4. **Transcription** - Whisper processes audio with progress updates
5. **Storage** - Results saved as JSON in class-specific folders
6. **Enhancement** - Future AI processing for summaries and analysis

## 🛠️ Technical Specifications

### File Handling

- **Supported Formats**: .wav, .mp3, .m4a, .flac
- **Size Limits**: No hard limit, smart processing based on file size
- **Processing**:
  - Files ≤50MB: Synchronous processing
  - Files >50MB: Background processing with status tracking

### Audio Processing

- **Model**: OpenAI Whisper "base" model
- **Features**: Word-level timestamps, high accuracy
- **Languages**: Multi-language support (Whisper default)

### Storage

- **Local Storage**: JSON files in `/transcriptions/{class_name}/`
- **File Naming**: `YYYY_MM_DD.json` format
- **Future**: S3 integration planned for audio files

## 🔮 Future Enhancements

### Phase 1 - AI Integration (TODO)

- **Speaker Diarization**: Implement pyannote.audio for speaker identification
- **Text Analysis**: Google Gemini integration for intelligent content analysis
- **Cloud Storage**: S3 integration for audio file management

### Phase 2 - Advanced Features

- **Search Functionality**: Full-text search across transcriptions
- **Note-taking Integration**: Allow manual notes and highlights
- **Export Options**: PDF, Word, and other format exports
- **Mobile API**: Enhanced endpoints for mobile app integration

### Phase 3 - Intelligence

- **Smart Scheduling**: Integration with calendar systems
- **Automatic Tagging**: AI-powered content categorization
- **Study Planning**: Personalized study schedule generation
- **Knowledge Graphs**: Connection mapping between lectures

## 🤝 Contributing

This project is designed for educational use. Key areas for contribution:

1. **AI Integration** - Implementing TODO sections for Gemini and pyannote.audio
2. **Frontend Development** - Web interface for easier file uploads
3. **Mobile Integration** - API enhancements for mobile applications
4. **Testing** - Comprehensive test suite development

## 📁 Project Structure Details

### Core Files

- **`main.py`** - FastAPI application with all routes and request handling
- **`transcribe.py`** - Whisper integration with progress tracking and file management
- **`speaker_diarization.py`** - Placeholder structure for pyannote.audio integration
- **`text_processing.py`** - Placeholder structure for Google Gemini text analysis

### Configuration

- Environment variables for API keys
- Logging configuration for debugging and monitoring
- File validation and error handling

## 🎓 Built for MBA Students

This project was specifically designed with MBA students in mind:

- **Class Organization** - Automatic organization by course (Finance, Marketing, Operations, etc.)
- **Professor Identification** - Metadata tracking for different instructors
- **Study-Focused Output** - Generated content optimized for exam preparation
- **Large File Handling** - Efficient processing of long lectures (75+ minutes)
- **Academic Calendar Integration** - Date-based organization and retrieval

## 🔐 Security & Privacy

- **Local Processing** - Audio files processed locally with Whisper
- **Secure Storage** - Local JSON storage with organized file structure  
- **API Keys** - Environment variable management for external services
- **Future Encryption** - Planned encryption for sensitive lecture content

---

**Status**: Backend implementation complete, AI integrations pending
**Version**: 1.0.0
**License**: Educational Use
**Maintained by**: [Your Name]

For questions or contributions, please refer to the TODO sections in the code for implementation guidance.

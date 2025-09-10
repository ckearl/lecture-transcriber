# Docker Deployment Guide

## Prerequisites

1. **Install Docker**: Ensure Docker is installed and running on your system
2. **API Keys**: Have your environment variables ready:
   - `GOOGLE_GEMINI_API_KEY`
   - `HUGGINGFACE_API_KEY`

## Files to Add

Create these files in your project root:

### 1. requirements.txt

Already provided above - contains all Python dependencies.

### 2. .dockerignore

```
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
.env
.venv
venv/
.git
.gitignore
README.md
Dockerfile
.dockerignore
transcriptions/
temp_*
*.log
.pytest_cache
```

### 3. docker-compose.yml (Optional)

```yaml
version: '3.8'

services:
  lecture-transcription:
    build: .
    ports:
      - "8000:8000"
    environment:
      - GOOGLE_GEMINI_API_KEY=${GOOGLE_GEMINI_API_KEY}
      - HUGGINGFACE_API_KEY=${HUGGINGFACE_API_KEY}
    volumes:
      - ./transcriptions:/app/transcriptions
      - ./temp:/app/temp
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

## Deployment Steps

### Option 1: Direct Docker Build

1. **Build the image**:

```bash
docker build -t lecture-transcription-api .
```

2. **Run the container**:

```bash
docker run -d \
  --name lecture-transcription \
  -p 8000:8000 \
  -e GOOGLE_GEMINI_API_KEY="your_gemini_key" \
  -e HUGGINGFACE_API_KEY="your_hf_token" \
  -v $(pwd)/transcriptions:/app/transcriptions \
  --restart unless-stopped \
  lecture-transcription-api
```

### Option 2: Docker Compose (Recommended)

1. **Create .env file**:

```bash
GOOGLE_GEMINI_API_KEY=your_gemini_api_key_here
HUGGINGFACE_API_KEY=your_huggingface_token_here
```

2. **Start services**:

```bash
docker-compose up -d
```

3. **View logs**:

```bash
docker-compose logs -f
```

4. **Stop services**:

```bash
docker-compose down
```

## Google Cloud Run Deployment

For production deployment to Google Cloud Run with Secret Manager:

### 1. Update Dockerfile for Cloud Run

```dockerfile
# Replace the CMD line with:
CMD ["sh", "-c", "python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

### 2. Deploy Command

```bash
# Build and deploy (secrets are configured in GCP Console)
gcloud run deploy lecture-transcription-api \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 8Gi \
  --cpu 4 \
  --timeout 3600 \
  --set-secrets="GOOGLE_GEMINI_API_KEY=gemini-api-key:latest,HUGGINGFACE_API_KEY=huggingface-token:latest"
```

### 3. Environment Configuration

The secrets are automatically injected by Cloud Run - no need to handle them in your application code. The API keys will be available as environment variables within the container.

## Important Considerations

### Resource Requirements

- **Memory**: At least 4GB RAM (8GB recommended for speaker diarization)
- **CPU**: Multi-core recommended for ML processing
- **Storage**: Sufficient space for audio files and models (~2GB for models)

### Security

- The Dockerfile creates a non-root user for security
- Mount volumes with appropriate permissions
- Keep API keys secure using environment variables or Docker secrets

### Performance Optimization

1. **GPU Support** (if available):

```dockerfile
# Replace the PyTorch installation line with:
RUN pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118
```

2. **Model Caching**:

```bash
# Pre-download models to avoid startup delays
docker run --rm -v model-cache:/root/.cache lecture-transcription-api python -c "import whisper; whisper.load_model('base')"
```

### Production Considerations

1. **Reverse Proxy**: Use nginx or similar for SSL/TLS termination
2. **File Storage**: Consider mounting external storage for transcriptions
3. **Monitoring**: Add logging and monitoring solutions
4. **Scaling**: Use container orchestration (Kubernetes) for multiple instances

## Testing the Deployment

1. **Health check**:

```bash
curl http://localhost:8000/health
```

2. **Upload test file**:

```bash
curl -X POST "http://localhost:8000/transcribe" \
  -H "Content-Type: multipart/form-data" \
  -F "title=Test Lecture" \
  -F "class_name=Test Class" \
  -F "professor=Test Professor" \
  -F "file=@test_audio.wav"
```

## Troubleshooting

### Common Issues

1. **Out of Memory**: Increase Docker memory limits or use smaller Whisper models
2. **API Key Errors**: Verify environment variables are properly set
3. **Permission Issues**: Ensure mounted volumes have correct permissions
4. **Model Download Failures**: Check internet connectivity and disk space

### Debugging Commands

```bash
# View container logs
docker logs lecture-transcription

# Access container shell
docker exec -it lecture-transcription /bin/bash

# Check running processes
docker exec lecture-transcription ps aux

# Monitor resource usage
docker stats lecture-transcription
```

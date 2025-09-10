# Use Python 3.10 slim image as a more modern and secure base
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Combine system dependency installation into a single RUN command
# This reduces the number of layers in the Docker image.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    build-essential \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install PyTorch for CPU FIRST, then the rest of the requirements.
# This ensures the correct, smaller PyTorch version is used by all other packages.
RUN pip install --no-cache-dir torch torchaudio --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY . .

# Create a directory for transcriptions if your app writes to disk
RUN mkdir -p /app/transcriptions

# Create a non-root user for better security
RUN useradd --create-home --shell /bin/bash appuser
# Change ownership of the app directory
RUN chown -R appuser:appuser /app
# Switch to the non-root user
USER appuser

# Set WORKDIR again for the new user context if needed, though chown should suffice
WORKDIR /app

# Expose the port the app runs on
EXPOSE 8000

# Health check (optional but good practice)
# Ensure your FastAPI app has a "/health" endpoint that returns a 200 OK
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
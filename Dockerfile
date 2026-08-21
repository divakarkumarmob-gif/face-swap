# ==============================================================================
# SOTA Face Swap & Neural Portrait Studio - Docker Deployment Container
# Suitable for HuggingFace Spaces (Docker), Render, RunPod, and Local Docker.
# ==============================================================================

FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PORT=7860

WORKDIR /app

# Install system dependencies (OpenGL, FFmpeg, build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application codebase
COPY . .

# Download initial models and sample assets
RUN python backend/engine/model_downloader.py || true
RUN python backend/generate_samples.py || true

# Expose Web Port (Default HuggingFace 7860)
EXPOSE 7860

# Run FastAPI production web server
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "7860"]

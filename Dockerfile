# Flood Prediction World Model - Docker Image
# Based on ComfyUI-like architecture with web-based frontend and backend computation

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV APP_HOME=/app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libgl1-mesa-glx \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY config/ ./config/
COPY scripts/ ./scripts/

# Create necessary directories
RUN mkdir -p /app/data/terrain \
    /app/data/observations \
    /app/logs \
    /app/output

# Set environment paths
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app:$PYTHONPATH"

# Expose ports for web interface and backend
EXPOSE 8000
EXPOSE 8080

# Create health check script
RUN echo 'import sys, urllib.request; exec("try:\n    with urllib.request.urlopen(\\'http://localhost:8000/health\\', timeout=5) as r: sys.exit(0 if r.status == 200 else 1)\nexcept: sys.exit(1)")' > /app/healthcheck.py

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python /app/healthcheck.py

# Create non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Default command to start the application
CMD ["python", "-m", "uvicorn", "src.server:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

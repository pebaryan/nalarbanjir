# ─── Nalarbanjir API — Python backend ────────────────────────────────────
# Multi-stage:
#   builder  — installs deps into /install
#   runtime  — minimal runtime image

# ── Stage 1: dependency builder ───────────────────────────────────────────
FROM python:3.13-slim AS builder

WORKDIR /install

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --prefix=/install --no-cache-dir -r requirements.txt


# ── Stage 2: runtime ──────────────────────────────────────────────────────
FROM python:3.13-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app

# Copy pre-built packages
COPY --from=builder /install /usr/local

# Application source
COPY src/     ./src/
COPY config/  ./config/

# Runtime directories
RUN mkdir -p logs data/primary data/archive ml/checkpoints

# Non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; r=urllib.request.urlopen('http://localhost:8000/api/health',timeout=5); sys.exit(0 if r.status==200 else 1)"

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

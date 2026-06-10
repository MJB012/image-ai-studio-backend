# syntax=docker/dockerfile:1.7
# ----- Image AI Studio Backend -----
# FastAPI + MongoDB (motor). Runs uvicorn on :8000.

FROM python:3.12-slim

# Sensible Python defaults for containers
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install Python deps first so this layer is cached when only app code changes.
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy application source
COPY app ./app

# Run as an unprivileged user (security best practice)
RUN useradd --create-home --shell /bin/bash appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# ASGI server. Scale workers in compose via WEB_CONCURRENCY or by overriding CMD.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

#!/usr/bin/env bash
# Entrypoint for the Hugging Face Space: migrate -> celery worker -> uvicorn.
set -e

echo "[start] applying database migrations..."
alembic upgrade head || echo "[start] WARNING: alembic upgrade failed — check POSTGRES_URL (continuing)"

echo "[start] launching Celery worker (solo pool)..."
celery -A backend.workers.celery_app worker --loglevel=info -P solo &

echo "[start] launching Uvicorn on :7860..."
exec uvicorn main:app --host 0.0.0.0 --port 7860

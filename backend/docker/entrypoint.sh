#!/bin/sh
set -eu

echo "Running Alembic migrations..."
alembic upgrade head

echo "Starting FastAPI (uvicorn) on 0.0.0.0:${API_PORT:-8000}..."
exec uvicorn app.main:app \
    --host "${API_HOST:-0.0.0.0}" \
    --port "${API_PORT:-8000}" \
    --proxy-headers \
    --forwarded-allow-ips="*"

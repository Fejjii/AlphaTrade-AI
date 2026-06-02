#!/bin/sh
set -eu

echo "Running Alembic migrations..."
alembic upgrade head

# Render and other PaaS set PORT; local/Docker use API_PORT.
LISTEN_PORT="${PORT:-${API_PORT:-8000}}"

echo "Starting FastAPI (uvicorn) on 0.0.0.0:${LISTEN_PORT}..."
exec uvicorn app.main:app \
    --host "${API_HOST:-0.0.0.0}" \
    --port "${LISTEN_PORT}" \
    --proxy-headers \
    --forwarded-allow-ips="*"

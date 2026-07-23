#!/bin/sh
set -eu

echo "Running Alembic migrations..."
alembic upgrade head

# Render and other PaaS set PORT; local/Docker use API_PORT.
LISTEN_PORT="${PORT:-${API_PORT:-8000}}"

# AT-018: never trust proxy headers from arbitrary peers ("*" was spoofable).
# Default is uvicorn's own loopback default; client IP resolution for rate
# limiting is handled in-app via TRUSTED_PROXY_HOPS (see app/security/rate_limit.py).
FORWARDED_ALLOW_IPS="${FORWARDED_ALLOW_IPS:-127.0.0.1}"

echo "Starting FastAPI (uvicorn) on 0.0.0.0:${LISTEN_PORT}..."
exec uvicorn app.main:app \
    --host "${API_HOST:-0.0.0.0}" \
    --port "${LISTEN_PORT}" \
    --proxy-headers \
    --forwarded-allow-ips="${FORWARDED_ALLOW_IPS}"

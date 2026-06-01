#!/usr/bin/env bash
# Local development server (no Docker). Requires Postgres on DATABASE_URL.
set -euo pipefail

cd "$(dirname "$0")/.."

export PYTHONPATH=src
export LOG_JSON="${LOG_JSON:-false}"

exec uv run uvicorn app.main:app \
  --reload \
  --host "${API_HOST:-127.0.0.1}" \
  --port "${API_PORT:-8000}"

#!/usr/bin/env bash
# Start backend for Playwright E2E with SQLite (no Docker required).
set -euo pipefail

cd "$(dirname "$0")/.."

export DATABASE_URL="${DATABASE_URL:-sqlite+pysqlite:///./.e2e-alphatrade.db}"
export JWT_SECRET="${JWT_SECRET:-e2e-test-secret-at-least-32-characters-long}"
export PYTHONPATH=src
export RATE_LIMIT_USE_REDIS=false
export MARKET_DATA_CACHE_USE_REDIS=false
export PROVIDER_MODE=mock
export MARKET_DATA_PROVIDER=mock
export JOURNAL_RAG_SYNC_ENABLED=true
export LOG_JSON=false

rm -f .e2e-alphatrade.db
uv run python scripts/init_e2e_db.py
exec uv run uvicorn app.main:app --port 8000 --host 127.0.0.1

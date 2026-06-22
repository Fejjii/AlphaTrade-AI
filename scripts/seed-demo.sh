#!/usr/bin/env bash
# Seed synthetic paper-only demo data on local or staging backend.
# Usage:
#   ./scripts/seed-demo.sh
#   DEMO_SEED_PASSWORD='...' BACKEND_URL=https://alphatrade-api-staging.onrender.com ./scripts/seed-demo.sh --api
#
# CLI mode (requires DATABASE_URL / local backend env):
#   cd backend && uv run python scripts/seed_demo.py
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MODE="${1:-cli}"

if [[ "$MODE" == "--api" ]]; then
  BACKEND_URL="${BACKEND_URL:-https://alphatrade-api-staging.onrender.com}"
  DEMO_EMAIL="${DEMO_EMAIL:-demo@alphatrade.ai}"
  if [[ -z "${DEMO_SEED_PASSWORD:-}" ]]; then
    echo "Set DEMO_SEED_PASSWORD for API seed mode." >&2
    exit 1
  fi
  if [[ -z "${DEMO_OWNER_TOKEN:-}" ]]; then
    echo "Logging in as demo owner to obtain token..."
    LOGIN_JSON="$(curl -fsS -X POST "${BACKEND_URL}/auth/login" \
      -H 'Content-Type: application/json' \
      -d "{\"email\":\"${DEMO_EMAIL}\",\"password\":\"${DEMO_SEED_PASSWORD}\"}")"
    DEMO_OWNER_TOKEN="$(python3 - <<'PY' "$LOGIN_JSON"
import json, sys
print(json.loads(sys.argv[1])["tokens"]["access_token"])
PY
)"
  fi
  curl -fsS -X POST "${BACKEND_URL}/demo/seed" \
    -H "Authorization: Bearer ${DEMO_OWNER_TOKEN}" \
    -H 'Content-Type: application/json' | python3 -m json.tool
  echo "Demo seed via API OK."
  exit 0
fi

cd backend
uv run python scripts/seed_demo.py

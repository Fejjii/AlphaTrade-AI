#!/usr/bin/env bash
# Seed synthetic paper-only demo data on local or staging backend.
# Usage:
#   ./scripts/seed-demo.sh
#   DEMO_SEED_PASSWORD='...' BACKEND_URL=https://alphatrade-api-staging.onrender.com ./scripts/seed-demo.sh --api
#   DEMO_SEED_USE_SERVER_PASSWORD=true ./scripts/seed-demo.sh --api   # Render has DEMO_SEED_PASSWORD
#
# API mode: any owner token (DEMO_OWNER_TOKEN) or auto-register bootstrap owner.
# Password: DEMO_SEED_PASSWORD in request body when set locally; otherwise server env.
# Never prints passwords.
#
# CLI mode (requires DATABASE_URL / local backend env):
#   cd backend && uv run python scripts/seed_demo.py
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MODE="${1:-cli}"

if [[ "$MODE" == "--api" ]]; then
  BACKEND_URL="${BACKEND_URL:-https://alphatrade-api-staging.onrender.com}"
  BACKEND_URL="${BACKEND_URL%/}"
  DEMO_EMAIL="${DEMO_EMAIL:-demo@alphatrade.ai}"
  DEMO_SEED_USE_SERVER_PASSWORD="${DEMO_SEED_USE_SERVER_PASSWORD:-false}"

  if [[ -z "${DEMO_SEED_PASSWORD:-}" && "$DEMO_SEED_USE_SERVER_PASSWORD" != "true" ]]; then
    echo "Set DEMO_SEED_PASSWORD or DEMO_SEED_USE_SERVER_PASSWORD=true for API seed mode." >&2
    exit 1
  fi

  obtain_owner_token() {
    if [[ -n "${DEMO_OWNER_TOKEN:-}" ]]; then
      return 0
    fi
    if [[ -n "${DEMO_SEED_PASSWORD:-}" ]]; then
      LOGIN_JSON="$(curl -fsS -X POST "${BACKEND_URL}/auth/login" \
        -H 'Content-Type: application/json' \
        -d "{\"email\":\"${DEMO_EMAIL}\",\"password\":\"${DEMO_SEED_PASSWORD}\"}" 2>/dev/null || true)"
      if [[ -n "$LOGIN_JSON" ]]; then
        DEMO_OWNER_TOKEN="$(python3 - <<'PY' "$LOGIN_JSON"
import json, sys
try:
    print(json.loads(sys.argv[1])["tokens"]["access_token"])
except (KeyError, json.JSONDecodeError):
    pass
PY
)"
      fi
      if [[ -n "${DEMO_OWNER_TOKEN:-}" ]]; then
        return 0
      fi
    fi
    BOOT_EMAIL="demo-seed-bootstrap-$(date +%s)@example.com"
    BOOT_PASS="SecurePass-DemoSeedBootstrap-1"
    REG_JSON="$(curl -fsS -X POST "${BACKEND_URL}/auth/register" \
      -H 'Content-Type: application/json' \
      -d "{\"email\":\"${BOOT_EMAIL}\",\"password\":\"${BOOT_PASS}\",\"organization_name\":\"Demo Seed Bootstrap\"}")"
    DEMO_OWNER_TOKEN="$(python3 - <<'PY' "$REG_JSON"
import json, sys
print(json.loads(sys.argv[1])["tokens"]["access_token"])
PY
)"
  }

  obtain_owner_token

  if [[ -n "${DEMO_SEED_PASSWORD:-}" ]]; then
    SEED_BODY="$(python3 - <<'PY'
import json, os
print(json.dumps({"password": os.environ["DEMO_SEED_PASSWORD"]}))
PY
)"
  else
    SEED_BODY='{}'
  fi

  curl -fsS -X POST "${BACKEND_URL}/demo/seed" \
    -H "Authorization: Bearer ${DEMO_OWNER_TOKEN}" \
    -H 'Content-Type: application/json' \
    -d "$SEED_BODY" | python3 -m json.tool
  echo "Demo seed via API OK."
  exit 0
fi

cd backend
uv run python scripts/seed_demo.py

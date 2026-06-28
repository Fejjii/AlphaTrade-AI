#!/usr/bin/env bash
# Read-only staging preview for automatic Telegram delivery (Slice 71).
#
# Usage:
#   DRY_RUN=true PREVIEW_LIMIT=5 STAGING_DEMO_PASSWORD='...' \
#     BACKEND_URL=https://alphatrade-api-staging.onrender.com \
#     ./scripts/preview-telegram-delivery-staging.sh
#
# Never sends Telegram. Never calls deliver-telegram. Never loops alerts for send.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BACKEND_URL="${BACKEND_URL:-https://alphatrade-api-staging.onrender.com}"
BACKEND_URL="${BACKEND_URL%/}"
DRY_RUN="${DRY_RUN:-false}"
PREVIEW_LIMIT="${PREVIEW_LIMIT:-5}"
DEMO_EMAIL="${STAGING_DEMO_EMAIL:-demo@alphatrade.ai}"
DEMO_PASSWORD="${STAGING_DEMO_PASSWORD:-}"

if [[ "$DRY_RUN" != "true" ]]; then
  echo "FAIL: DRY_RUN=true is required (preview is read-only)." >&2
  exit 1
fi

if [[ -z "$PREVIEW_LIMIT" ]] || ! [[ "$PREVIEW_LIMIT" =~ ^[0-9]+$ ]] || [[ "$PREVIEW_LIMIT" -lt 1 ]]; then
  echo "FAIL: set explicit PREVIEW_LIMIT (1-25)." >&2
  exit 1
fi

if [[ "$PREVIEW_LIMIT" -gt 25 ]]; then
  echo "FAIL: PREVIEW_LIMIT must be <= 25." >&2
  exit 1
fi

if [[ -z "$DEMO_PASSWORD" ]]; then
  echo "FAIL: STAGING_DEMO_PASSWORD required." >&2
  exit 1
fi

assert_no_secrets() {
  python3 - <<'PY' "$1"
import json, re, sys
raw = sys.argv[1]
forbidden = [
    r"TELEGRAM_BOT_TOKEN",
    r"TELEGRAM_CHAT_ID",
    r"bot[0-9]{8,}:[A-Za-z0-9_-]{20,}",
    r"postgresql\+psycopg://",
    r"rediss?://",
]
for pattern in forbidden:
    assert re.search(pattern, raw, re.IGNORECASE) is None, pattern
PY
}

echo "Telegram delivery preview — BACKEND_URL=${BACKEND_URL} PREVIEW_LIMIT=${PREVIEW_LIMIT}"
echo "Guardrails: preview only · DRY_RUN=true · no deliver-telegram calls"

login_json="$(curl -fsS -X POST "${BACKEND_URL}/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"${DEMO_EMAIL}\",\"password\":\"${DEMO_PASSWORD}\"}")"
assert_no_secrets "$login_json"
TOKEN="$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['tokens']['access_token'])" "$login_json")"

preview_json="$(curl -fsS -X POST "${BACKEND_URL}/alerts/delivery/preview" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H 'Content-Type: application/json' \
  -d "{\"channel\":\"telegram\",\"limit\":${PREVIEW_LIMIT},\"severity_min\":\"info\"}")"
assert_no_secrets "$preview_json"

python3 - <<'PY' "$preview_json"
import json, sys
body = json.loads(sys.argv[1])
print(f"  eligible_count={body.get('eligible_count')}")
print(f"  skipped_count={body.get('skipped_count')}")
print(f"  already_delivered_count={body.get('already_delivered_count')}")
for item in body.get("items") or []:
    print(f"  - {item.get('alert_id')} status={item.get('status')} reason={item.get('reason')}")
print("  OK: preview read-only")
PY

echo "Preview staging validation passed."

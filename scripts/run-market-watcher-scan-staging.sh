#!/usr/bin/env bash
# Read-only staging validation for Slice 72 market watcher scanner.
#
# Usage:
#   DRY_RUN=true CONFIRM=RUN_READ_ONLY_SCAN STAGING_DEMO_PASSWORD='...' \
#     BACKEND_URL=https://alphatrade-api-staging.onrender.com \
#     ./scripts/run-market-watcher-scan-staging.sh
#
# Never sends Telegram. Never places orders. Never enables worker automation.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BACKEND_URL="${BACKEND_URL:-https://alphatrade-api-staging.onrender.com}"
BACKEND_URL="${BACKEND_URL%/}"
DRY_RUN="${DRY_RUN:-true}"
CONFIRM="${CONFIRM:-}"
DEMO_EMAIL="${STAGING_DEMO_EMAIL:-demo@alphatrade.ai}"
DEMO_PASSWORD="${STAGING_DEMO_PASSWORD:-}"
PREVIEW_SYMBOLS="${SCAN_SYMBOLS:-BTCUSDT,ETHUSDT,SOLUSDT}"
PREVIEW_TIMEFRAMES="${SCAN_TIMEFRAMES:-15m,1h}"

if [[ "$DRY_RUN" != "true" ]]; then
  echo "FAIL: DRY_RUN=true is required for staging validation." >&2
  exit 1
fi

if [[ "$CONFIRM" != "RUN_READ_ONLY_SCAN" ]]; then
  cat >&2 <<'EOF'
FAIL: CONFIRM=RUN_READ_ONLY_SCAN is required.

Guardrail: explicit confirmation env var before any scan request.
Example:
  DRY_RUN=true CONFIRM=RUN_READ_ONLY_SCAN STAGING_DEMO_PASSWORD='...' \
    ./scripts/run-market-watcher-scan-staging.sh
EOF
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

echo "Market watcher scan staging — BACKEND_URL=${BACKEND_URL} DRY_RUN=${DRY_RUN}"
echo "Guardrails: dry-run only · no Telegram · no orders · explicit CONFIRM"

echo "1/5 — /health (paper-only)"
health_json="$(curl -fsS "${BACKEND_URL}/health")"
python3 - <<'PY' "$health_json"
import json, sys
p = json.loads(sys.argv[1])
assert p.get("execution_mode") == "paper", p
assert p.get("real_trading_enabled") is False, p
print("  OK: paper-only")
PY
assert_no_secrets "$health_json"

echo "2/5 — owner login"
login_json="$(curl -fsS -X POST "${BACKEND_URL}/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"${DEMO_EMAIL}\",\"password\":\"${DEMO_PASSWORD}\"}")"
assert_no_secrets "$login_json"
TOKEN="$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['tokens']['access_token'])" "$login_json")"

echo "3/5 — GET /market-watcher/summary"
summary_json="$(curl -fsS -H "Authorization: Bearer ${TOKEN}" "${BACKEND_URL}/market-watcher/summary")"
python3 - <<'PY' "$summary_json"
import json, sys
p = json.loads(sys.argv[1])
assert p.get("paper_only") is True, p
assert p.get("manual_scan_available") is True, p
assert p.get("worker_enabled") is False, p
print(f"  OK: readiness={p.get('readiness')} manual_scan_available={p.get('manual_scan_available')}")
PY
assert_no_secrets "$summary_json"

symbols_json="$(python3 - <<PY
import json
print(json.dumps([s.strip() for s in "${PREVIEW_SYMBOLS}".split(",") if s.strip()]))
PY
)"
timeframes_json="$(python3 - <<PY
import json
print(json.dumps([t.strip() for t in "${PREVIEW_TIMEFRAMES}".split(",") if t.strip()]))
PY
)"

echo "4/5 — POST /market-watcher/scan (dry-run preview)"
scan_json="$(curl -fsS -X POST "${BACKEND_URL}/market-watcher/scan" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H 'Content-Type: application/json' \
  -d "{\"confirm\":\"${CONFIRM}\",\"symbols\":${symbols_json},\"timeframes\":${timeframes_json},\"dry_run\":true}")"
assert_no_secrets "$scan_json"
python3 - <<'PY' "$scan_json"
import json, sys
p = json.loads(sys.argv[1])
assert p.get("dry_run") is True, p
assert p.get("status") in ("ok", "degraded"), p
assert p.get("alerts_created", 0) == 0, p
print(f"  OK: candidates={len(p.get('candidates') or [])} status={p.get('status')}")
for item in p.get("candidates") or []:
    print(f"  - {item.get('symbol')} {item.get('timeframe')} {item.get('condition')}")
PY

echo "5/5 — safety re-check"
python3 - <<'PY' "$health_json"
import json, sys
p = json.loads(sys.argv[1])
assert p.get("real_trading_enabled") is False
print("  OK: no trading enabled")
PY

echo "Market watcher scan staging validation passed."

#!/usr/bin/env bash
# Staging validation for Slice 72/73 market watcher scanner.
#
# Dry-run (default — preview only, no alerts):
#   DRY_RUN=true CONFIRM=RUN_READ_ONLY_SCAN STAGING_DEMO_PASSWORD='...' \
#     BACKEND_URL=https://alphatrade-api-staging.onrender.com \
#     ./scripts/run-market-watcher-scan-staging.sh
#
# Non-dry-run (in-app alerts only — requires second confirmation):
#   DRY_RUN=false CONFIRM=RUN_READ_ONLY_SCAN \
#     CREATE_IN_APP_ALERTS_CONFIRM=CREATE_IN_APP_ALERTS_ONLY \
#     STAGING_DEMO_PASSWORD='...' \
#     BACKEND_URL=https://alphatrade-api-staging.onrender.com \
#     ./scripts/run-market-watcher-scan-staging.sh
#
# Never sends Telegram. Never places orders. Never enables worker automation.
#
# STAGING_DEMO_PASSWORD must match Render DEMO_SEED_PASSWORD (or your demo login secret).
# Provide it from Render dashboard / local secret manager — never commit it to the repo.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BACKEND_URL="${BACKEND_URL:-https://alphatrade-api-staging.onrender.com}"
BACKEND_URL="${BACKEND_URL%/}"
DRY_RUN="${DRY_RUN:-true}"
CONFIRM="${CONFIRM:-}"
CREATE_IN_APP_ALERTS_CONFIRM="${CREATE_IN_APP_ALERTS_CONFIRM:-}"
DEMO_EMAIL="${STAGING_DEMO_EMAIL:-demo@alphatrade.ai}"
DEMO_PASSWORD="${STAGING_DEMO_PASSWORD:-}"
PREVIEW_SYMBOLS="${SCAN_SYMBOLS:-BTCUSDT,ETHUSDT,SOLUSDT}"
PREVIEW_TIMEFRAMES="${SCAN_TIMEFRAMES:-15m,1h}"

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

if [[ "$DRY_RUN" != "true" && "$DRY_RUN" != "false" ]]; then
  echo "FAIL: DRY_RUN must be true or false." >&2
  exit 1
fi

if [[ "$DRY_RUN" == "false" ]]; then
  if [[ "$CREATE_IN_APP_ALERTS_CONFIRM" != "CREATE_IN_APP_ALERTS_ONLY" ]]; then
    cat >&2 <<'EOF'
FAIL: CREATE_IN_APP_ALERTS_CONFIRM=CREATE_IN_APP_ALERTS_ONLY is required for non-dry-run.

Non-dry-run creates in-app alerts only. No Telegram. No orders. No worker automation.
Example:
  DRY_RUN=false CONFIRM=RUN_READ_ONLY_SCAN CREATE_IN_APP_ALERTS_CONFIRM=CREATE_IN_APP_ALERTS_ONLY \
    STAGING_DEMO_PASSWORD='...' ./scripts/run-market-watcher-scan-staging.sh
EOF
    exit 1
  fi
  echo "WARNING: non-dry-run mode — will create in-app alerts only (no Telegram, no orders)." >&2
fi

if [[ -z "$DEMO_PASSWORD" ]]; then
  echo "FAIL: STAGING_DEMO_PASSWORD required (use Render DEMO_SEED_PASSWORD; do not commit)." >&2
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

DRY_RUN_JSON="$(python3 -c "print('true' if '${DRY_RUN}' == 'true' else 'false')")"
MODE_LABEL="dry-run preview"
if [[ "$DRY_RUN_JSON" == "false" ]]; then
  MODE_LABEL="in-app alert creation"
fi

echo "Market watcher scan staging — BACKEND_URL=${BACKEND_URL} DRY_RUN=${DRY_RUN}"
echo "Guardrails: ${MODE_LABEL} · no Telegram · no orders · explicit CONFIRM"

echo "1/6 — /health (paper-only)"
health_json="$(curl -fsS "${BACKEND_URL}/health")"
python3 - <<'PY' "$health_json"
import json, sys
p = json.loads(sys.argv[1])
assert p.get("execution_mode") == "paper", p
assert p.get("real_trading_enabled") is False, p
print("  OK: paper-only")
PY
assert_no_secrets "$health_json"

echo "2/6 — owner login"
login_json="$(curl -fsS -X POST "${BACKEND_URL}/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"${DEMO_EMAIL}\",\"password\":\"${DEMO_PASSWORD}\"}")"
assert_no_secrets "$login_json"
TOKEN="$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['tokens']['access_token'])" "$login_json")"

echo "3/6 — GET /market-watcher/summary"
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

scan_body="$(python3 - <<PY
import json
body = {
    "confirm": "${CONFIRM}",
    "symbols": json.loads('''${symbols_json}'''),
    "timeframes": json.loads('''${timeframes_json}'''),
    "dry_run": ${DRY_RUN_JSON},
}
if not ${DRY_RUN_JSON}:
    body["create_in_app_alerts_confirm"] = "${CREATE_IN_APP_ALERTS_CONFIRM}"
print(json.dumps(body))
PY
)"

echo "4/6 — POST /market-watcher/scan (${MODE_LABEL})"
scan_json="$(curl -fsS -X POST "${BACKEND_URL}/market-watcher/scan" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H 'Content-Type: application/json' \
  -d "${scan_body}")"
assert_no_secrets "$scan_json"
python3 - <<'PY' "$scan_json" "$DRY_RUN_JSON"
import json, sys
p = json.loads(sys.argv[1])
dry_run = sys.argv[2] == "true"
assert p.get("dry_run") is dry_run, p
assert p.get("status") in ("ok", "degraded"), p
if dry_run:
    assert p.get("alerts_created", 0) == 0, p
print(f"  OK: candidates={len(p.get('candidates') or [])} status={p.get('status')} alerts_created={p.get('alerts_created', 0)} deduped={p.get('alerts_deduped', 0)}")
for item in p.get("candidates") or []:
    print(f"  - {item.get('symbol')} {item.get('timeframe')} {item.get('condition')} deduped={item.get('deduped')}")
PY

if [[ "$DRY_RUN_JSON" == "false" ]]; then
  echo "5/6 — verify created alerts are in-app only"
  alerts_json="$(curl -fsS -H "Authorization: Bearer ${TOKEN}" "${BACKEND_URL}/alerts?limit=25")"
  assert_no_secrets "$alerts_json"
  python3 - <<'PY' "$alerts_json" "$scan_json"
import json, sys
alerts = json.loads(sys.argv[1])
scan = json.loads(sys.argv[2])
created_ids = {
    c.get("created_alert_id")
    for c in scan.get("candidates") or []
    if c.get("created_alert_id")
}
items = alerts.get("items") or []
for alert_id in created_ids:
    match = next((a for a in items if a.get("id") == alert_id), None)
    assert match is not None, f"missing alert {alert_id}"
    assert match.get("delivery_channel") == "in_app", match
    assert match.get("metadata", {}).get("source") == "market_watcher", match
print(f"  OK: verified {len(created_ids)} in-app alert(s)")
PY
else
  echo "5/6 — dry-run skip alert verification"
  python3 - <<'PY' "$scan_json"
import json, sys
p = json.loads(sys.argv[1])
assert p.get("alerts_created", 0) == 0, p
print("  OK: dry-run created no alerts")
PY
fi

echo "6/6 — safety re-check"
python3 - <<'PY' "$health_json"
import json, sys
p = json.loads(sys.argv[1])
assert p.get("real_trading_enabled") is False
print("  OK: no trading enabled")
PY

echo "Market watcher scan staging validation passed."

#!/usr/bin/env bash
# Slice 46 notifications smoke (paper only, no real Telegram/webhook required).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BASE_URL="${BASE_URL:-http://localhost:8000}"
BASE_URL="${BASE_URL%/}"

EMAIL="${SMOKE_EMAIL:-notifications-smoke-$(date +%s)@example.com}"
PASSWORD="${SMOKE_PASSWORD:-secure-password-1}"

auth_header() {
  printf 'Authorization: Bearer %s' "$TOKEN"
}

echo "Notifications smoke — BASE_URL=${BASE_URL}"

echo "1/7 — health (paper mode, real trading disabled)"
health_json="$(curl -fsS "${BASE_URL}/health")"
python3 - <<'PY' "$health_json"
import json, sys
p = json.loads(sys.argv[1])
assert p.get("execution_mode") == "paper", p
assert p.get("real_trading_enabled") is False, p
print("  OK")
PY

echo "2/7 — register"
register_json="$(curl -fsS -X POST "${BASE_URL}/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${EMAIL}\",\"password\":\"${PASSWORD}\",\"organization_name\":\"Notifications Smoke\"}")"
TOKEN="$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['tokens']['access_token'])" "$register_json")"

echo "3/7 — GET notification preferences"
prefs_json="$(curl -fsS "${BASE_URL}/notifications/preferences" -H "$(auth_header)")"
python3 - <<'PY' "$prefs_json"
import json, sys
p = json.loads(sys.argv[1])
assert p.get("in_app_enabled") is True, p
assert p.get("webhook_enabled") is False, p
assert p.get("telegram_enabled") is False, p
print("  OK")
PY

echo "4/7 — PATCH notification preferences (safe values)"
patch_json="$(curl -fsS -X PATCH "${BASE_URL}/notifications/preferences" \
  -H "$(auth_header)" \
  -H "Content-Type: application/json" \
  -d '{"min_severity":"warning","webhook_enabled":false,"telegram_enabled":false}')"
python3 - <<'PY' "$patch_json"
import json, sys
p = json.loads(sys.argv[1])
assert p.get("min_severity") == "warning", p
print("  OK")
PY

echo "5/7 — alerts delivery status"
status_json="$(curl -fsS "${BASE_URL}/alerts/delivery-status" -H "$(auth_header)")"
python3 - <<'PY' "$status_json"
import json, sys
p = json.loads(sys.argv[1])
assert p.get("paper_only") is True, p
# External delivery disabled without secrets is expected
print(f"  effective_external_enabled={p.get('effective_external_enabled')}")
print("  OK")
PY

echo "6/7 — test notification endpoint"
test_json="$(curl -fsS -X POST "${BASE_URL}/notifications/test" -H "$(auth_header)")"
python3 - <<'PY' "$test_json"
import json, sys
p = json.loads(sys.argv[1])
assert p.get("paper_only") is True, p
assert "TEST" in p.get("test_label", ""), p
print("  OK")
PY

echo "7/7 — deliver pending (owner only; may process zero)"
pending_json="$(curl -fsS -X POST "${BASE_URL}/alerts/deliver-pending" -H "$(auth_header)")"
python3 - <<'PY' "$pending_json"
import json, sys
p = json.loads(sys.argv[1])
assert "processed" in p, p
print(f"  processed={p.get('processed')}")
print("  OK")
PY

echo "Notifications smoke passed."

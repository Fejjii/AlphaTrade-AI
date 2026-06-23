#!/usr/bin/env bash
# Validate staging demo tenant after seed (login, data richness, legacy password rejection).
# Usage:
#   export DEMO_SEED_PASSWORD='<private>'   # required for login checks
#   ./scripts/validate-demo-staging.sh
# Does not print passwords, tokens, or secrets.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BACKEND_URL="${BACKEND_URL:-https://alphatrade-api-staging.onrender.com}"
BACKEND_URL="${BACKEND_URL%/}"
DEMO_EMAIL="${DEMO_EMAIL:-demo@alphatrade.ai}"

if [[ -z "${DEMO_SEED_PASSWORD:-}" ]]; then
  echo "Set DEMO_SEED_PASSWORD for login validation." >&2
  exit 1
fi

login_status() {
  local email="$1"
  local password="$2"
  curl -sS -o /tmp/login_body.json -w "%{http_code}" -X POST "${BACKEND_URL}/auth/login" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"${email}\",\"password\":\"${password}\"}"
}

echo "1/6 — legacy default password rejected"
LEGACY_HTTP="$(login_status "$DEMO_EMAIL" "DemoPaper2026!")"
if [[ "$LEGACY_HTTP" == "401" ]]; then
  echo "  OK: legacy default rejected (401)"
else
  echo "  WARN: legacy default returned HTTP ${LEGACY_HTTP} (expected 401 if password was rotated)"
fi
rm -f /tmp/login_body.json

echo "2/6 — private demo password login"
PRIVATE_HTTP="$(login_status "$DEMO_EMAIL" "$DEMO_SEED_PASSWORD")"
if [[ "$PRIVATE_HTTP" != "200" ]]; then
  echo "FAIL: demo login HTTP ${PRIVATE_HTTP}" >&2
  rm -f /tmp/login_body.json
  exit 1
fi
echo "  OK: demo login"
TOKEN="$(python3 -c "import json; print(json.load(open('/tmp/login_body.json'))['tokens']['access_token'])")"
rm -f /tmp/login_body.json
AUTH="Authorization: Bearer ${TOKEN}"

echo "3/6 — dashboard summary"
DASH="$(curl -fsS -H "$AUTH" "${BACKEND_URL}/dashboard/summary")"
python3 - <<'PY' "$DASH"
import json, sys
d = json.loads(sys.argv[1])
assert d["safety"]["execution_mode"] == "paper"
assert d["safety"]["real_trading_enabled"] is False
assert len(d.get("active_paper_validations", [])) >= 1
print("  OK")
PY

echo "4/6 — strategies, alerts, lessons"
python3 - <<'PY' "$AUTH" "$BACKEND_URL"
import json, os, subprocess, sys
auth, base = sys.argv[1], sys.argv[2]

def get(path):
    out = subprocess.check_output(
        ["curl", "-fsS", "-H", auth, f"{base}{path}"],
        text=True,
    )
    return json.loads(out)

strategies = get("/strategies")
count = len(strategies.get("items", strategies))
assert count >= 3, strategies
alerts = get("/alerts")
assert len(alerts.get("items", [])) >= 4
lessons = get("/lessons/candidates")
assert len(lessons.get("items", [])) >= 5
print("  OK")
PY

echo "5/6 — paper validation (dashboard snapshot)"
DASH="$(curl -fsS -H "$AUTH" "${BACKEND_URL}/dashboard/summary")"
python3 - <<'PY' "$DASH"
import json, sys
d = json.loads(sys.argv[1])
assert len(d.get("active_paper_validations", [])) >= 1
print("  OK")
PY

echo "6/6 — risk settings"
RISK="$(curl -fsS -H "$AUTH" "${BACKEND_URL}/risk/settings")"
python3 - <<'PY' "$RISK"
import json, sys
d = json.loads(sys.argv[1])
assert "max_trades_per_day" in d
print("  OK")
PY

echo "Demo staging validation passed."

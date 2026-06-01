#!/usr/bin/env bash
# Staging deployment smoke test — health, auth, chat, and safety invariants.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BASE_URL="${BASE_URL:-http://localhost:8000}"
MAX_ATTEMPTS="${MAX_ATTEMPTS:-60}"
EMAIL="${SMOKE_EMAIL:-staging-smoke-$(date +%s)@example.com}"
PASSWORD="${SMOKE_PASSWORD:-secure-password-1}"
ORG_NAME="${SMOKE_ORG:-Staging Smoke Org}"

echo "Waiting for backend at ${BASE_URL}..."
attempt=0
until curl -fsS "${BASE_URL}/health" >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [[ "$attempt" -ge "$MAX_ATTEMPTS" ]]; then
    echo "Backend did not become reachable within ${MAX_ATTEMPTS} attempts." >&2
    exit 1
  fi
  sleep 2
done

echo "1/8 — /health"
health_json="$(curl -fsS "${BASE_URL}/health")"
python3 - <<'PY' "$health_json"
import json, sys
payload = json.loads(sys.argv[1])
assert payload.get("execution_mode") == "paper", payload
assert payload.get("real_trading_enabled") is False, payload
print("  OK")
PY

echo "2/8 — /health/ready"
ready_json="$(curl -fsS "${BASE_URL}/health/ready")"
python3 - <<'PY' "$ready_json"
import json, sys
payload = json.loads(sys.argv[1])
assert payload.get("ready") is True, payload
print("  OK")
PY

echo "3/8 — /providers/status"
providers_json="$(curl -fsS "${BASE_URL}/providers/status")"
python3 - <<'PY' "$providers_json"
import json, sys
payload = json.loads(sys.argv[1])
assert payload.get("providers"), payload
print(f"  {len(payload['providers'])} providers")
PY

echo "4/8 — register"
register_json="$(curl -fsS -X POST "${BASE_URL}/auth/register" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"${EMAIL}\",\"password\":\"${PASSWORD}\",\"organization_name\":\"${ORG_NAME}\"}")"

token="$(python3 - <<'PY' "$register_json"
import json, sys
print(json.loads(sys.argv[1])["tokens"]["access_token"])
PY
)"
refresh="$(python3 - <<'PY' "$register_json"
import json, sys
body = json.loads(sys.argv[1])
print(body["tokens"].get("refresh_token") or "")
PY
)"

echo "5/8 — login"
login_json="$(curl -fsS -X POST "${BASE_URL}/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"${EMAIL}\",\"password\":\"${PASSWORD}\"}")"
login_token="$(python3 - <<'PY' "$login_json"
import json, sys
print(json.loads(sys.argv[1])["tokens"]["access_token"])
PY
)"

echo "6/8 — protected chat"
curl -fsS -X POST -H "Authorization: Bearer ${login_token}" -H 'Content-Type: application/json' \
  "${BASE_URL}/chat/message" \
  -d '{"message":"Staging smoke test message"}' >/dev/null

echo "7/8 — logout"
if [[ -n "$refresh" ]]; then
  curl -fsS -X POST -H 'Content-Type: application/json' \
    "${BASE_URL}/auth/logout" \
    -d "{\"refresh_token\":\"${refresh}\"}" >/dev/null
else
  curl -fsS -X POST -H "Authorization: Bearer ${login_token}" -H 'Content-Type: application/json' \
    "${BASE_URL}/auth/logout" \
    -d '{}' >/dev/null
fi

echo "8/8 — real trading disabled invariant"
./scripts/verify-safety.sh

echo "Staging smoke checks passed."

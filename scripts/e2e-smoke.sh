#!/usr/bin/env bash
# Lightweight authenticated smoke checks against a running stack.
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:3000}"
EMAIL="${SMOKE_EMAIL:-smoke-$(date +%s)@example.com}"
PASSWORD="${SMOKE_PASSWORD:-secure-password-1}"

echo "Registering smoke user at ${BASE_URL}..."
register_json="$(curl -fsS -X POST "${BASE_URL}/auth/register" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"${EMAIL}\",\"password\":\"${PASSWORD}\",\"organization_name\":\"Smoke Org $(date +%s)\"}")"

token="$(python3 - <<'PY' "$register_json"
import json, sys
print(json.loads(sys.argv[1])["tokens"]["access_token"])
PY
)"
refresh="$(python3 - <<'PY' "$register_json"
import json, sys
print(json.loads(sys.argv[1])["tokens"]["refresh_token"])
PY
)"

echo "Checking authenticated /auth/me..."
curl -fsS -H "Authorization: Bearer ${token}" "${BASE_URL}/auth/me" >/dev/null

echo "Checking /chat/message..."
curl -fsS -X POST -H "Authorization: Bearer ${token}" -H 'Content-Type: application/json' \
  "${BASE_URL}/chat/message" \
  -d '{"message":"Smoke test message"}' >/dev/null

echo "Checking /proposals..."
curl -fsS -H "Authorization: Bearer ${token}" "${BASE_URL}/proposals" >/dev/null

echo "Logging out..."
if [[ -n "$refresh" ]]; then
  curl -fsS -X POST -H "Authorization: Bearer ${token}" -H 'Content-Type: application/json' \
    "${BASE_URL}/auth/logout" \
    -d "{\"refresh_token\":\"${refresh}\"}" >/dev/null
else
  curl -fsS -X POST -H "Authorization: Bearer ${token}" -H 'Content-Type: application/json' \
    "${BASE_URL}/auth/logout" \
    -d '{}' >/dev/null
fi

echo "Checking protected route without token returns 401..."
status="$(curl -s -o /dev/null -w '%{http_code}' "${BASE_URL}/proposals")"
test "$status" = "401"

if curl -fsS "${FRONTEND_URL}/login" >/dev/null 2>&1; then
  echo "Frontend login page reachable at ${FRONTEND_URL}/login"
else
  echo "Frontend not reachable at ${FRONTEND_URL} (optional for backend-only smoke)."
fi

echo "Smoke checks passed."

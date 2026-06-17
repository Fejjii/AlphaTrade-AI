#!/usr/bin/env bash
# Shared auth helpers for staging/e2e smoke scripts.
# Callers must define curl_api / curl_api_cookie and set BASE_URL, EMAIL, PASSWORD.

smoke_login_after_register() {
  # Usage: smoke_login_after_register "$register_json"
  # Sets SMOKE_ACCESS_TOKEN and SMOKE_SESSION_JSON (login body or register json).
  local register_json="$1"
  local login_body login_code login_status

  SMOKE_ACCESS_TOKEN="$(python3 - <<'PY' "$register_json"
import json, sys
print(json.loads(sys.argv[1])["tokens"]["access_token"])
PY
)"
  SMOKE_SESSION_JSON="$register_json"

  login_body="$(mktemp)"
  if [[ "${COOKIE_MODE:-false}" == "true" ]]; then
    login_code="$(curl -sS -o "$login_body" -w '%{http_code}' -b "$COOKIE_JAR" -c "$COOKIE_JAR" \
      -X POST "${BASE_URL}/auth/login" \
      -H 'Content-Type: application/json' \
      -d "{\"email\":\"${EMAIL}\",\"password\":\"${PASSWORD}\"}")"
  else
    login_code="$(curl -sS -o "$login_body" -w '%{http_code}' \
      -X POST "${BASE_URL}/auth/login" \
      -H 'Content-Type: application/json' \
      -d "{\"email\":\"${EMAIL}\",\"password\":\"${PASSWORD}\"}")"
  fi

  if ! login_status="$(python3 - <<'PY' "$login_code" "$(cat "$login_body")"
import json, sys

code, body = sys.argv[1], sys.argv[2]
if code == "200":
    print("ok")
    sys.exit(0)
if code != "401":
    print(f"fail:http_{code}:{body}", file=sys.stderr)
    sys.exit(1)
try:
    message = json.loads(body).get("error", {}).get("message", "")
except json.JSONDecodeError:
    message = body
if "not verified" in message.lower():
    print("unverified")
    sys.exit(0)
print(f"fail:login_401:{body}", file=sys.stderr)
sys.exit(1)
PY
)"; then
    rm -f "$login_body"
    return 1
  fi

  if [[ "$login_status" == "ok" ]]; then
    SMOKE_SESSION_JSON="$(cat "$login_body")"
    SMOKE_ACCESS_TOKEN="$(python3 - <<'PY' "$SMOKE_SESSION_JSON"
import json, sys
print(json.loads(sys.argv[1])["tokens"]["access_token"])
PY
)"
    echo "  OK: login"
  else
    echo "  OK: login blocked for unverified email (REQUIRE_EMAIL_VERIFIED); using register session"
  fi
  rm -f "$login_body"
}

#!/usr/bin/env bash
# API staging validation for Slice 82 run sessions (record only, no scan/Telegram/orders).
#
# Usage:
#   STAGING_BOOTSTRAP_PASSWORD='...' ./scripts/validate-run-sessions-staging.sh
#
# Optional:
#   BACKEND_URL=https://alphatrade-api-staging.onrender.com
#   STAGING_BOOTSTRAP_EMAIL=seed-bootstrap-1782212606@example.com
set -euo pipefail

BACKEND_URL="${BACKEND_URL:-https://alphatrade-api-staging.onrender.com}"
BACKEND_URL="${BACKEND_URL%/}"
EMAIL="${STAGING_BOOTSTRAP_EMAIL:-seed-bootstrap-1782212606@example.com}"
PASSWORD="${STAGING_BOOTSTRAP_PASSWORD:-}"

if [[ -z "$PASSWORD" ]]; then
  echo "STAGING_BOOTSTRAP_PASSWORD required (not printed)." >&2
  exit 1
fi

echo "Run session staging validation — BACKEND_URL=${BACKEND_URL}"

health_json="$(curl -fsS "${BACKEND_URL}/health")"
python3 - <<'PY' "$health_json"
import json, sys
payload = json.loads(sys.argv[1])
assert payload.get("execution_mode") == "paper", payload
assert payload.get("real_trading_enabled") is False, payload
git_sha = payload.get("git_sha")
print(f"  OK: paper mode; git_sha={git_sha or 'null'}")
if not git_sha:
    print("  WARN: git_sha missing — deploy visibility not configured yet")
PY

python3 - <<PY
import json, sys, urllib.error, urllib.request

BASE = "${BACKEND_URL}"
EMAIL = "${EMAIL}"
PASSWORD = "${PASSWORD}"
START = "START_PAPER_VALIDATION_RUN"
CREATE_DRAFT = "CREATE_PAPER_VALIDATION_DRAFT"
QUEUE = "QUEUE_PAPER_VALIDATION_CANDIDATE"
CREATE_PLAN = "CREATE_PAPER_VALIDATION_RUN_PLAN"

def req(method, path, token=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=120) as resp:
            return resp.status, json.loads(resp.read().decode() or "null")
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode() or "null")
        except Exception:
            payload = None
        return e.code, payload

def build_plan(token, alert_id):
    req("PATCH", f"/alerts/setup-review/{alert_id}", token=token, body={"review_status": "important"})
    _, draft = req("POST", f"/alerts/setup-review/{alert_id}/draft", token=token, body={
        "confirm": CREATE_DRAFT, "risk_mode": "conservative", "notes": "validate-run-sessions-staging",
    })
    draft_id = draft["draft"]["draft_id"]
    req("PATCH", f"/paper-validation/drafts/{draft_id}/prep", token=token, body={
        "prep_status": "ready_for_validation", "thesis": "t", "entry_criteria": "e",
        "invalidation_criteria": "i", "risk_notes": "r",
        "checklist": {k: True for k in [
            "trend_checked","support_resistance_checked","volume_checked","risk_reward_checked",
            "invalidation_checked","higher_timeframe_checked","news_or_funding_checked",
        ]},
    })
    _, queued = req("POST", f"/paper-validation/drafts/{draft_id}/queue", token=token, body={"confirm": QUEUE})
    cid = queued["candidate"]["candidate_id"]
    req("PATCH", f"/paper-validation/candidates/{cid}", token=token, body={"candidate_status": "reviewing"})
    _, plan = req("POST", f"/paper-validation/candidates/{cid}/plan", token=token, body={
        "confirm": CREATE_PLAN, "validation_window": "intraday", "observation_timeframe": "1h",
        "max_duration_minutes": 240, "planned_entry_rule": "e", "planned_invalidation_rule": "i",
        "planned_success_criteria": "s", "planned_failure_criteria": "f",
    })
    return plan["plan"]["plan_id"]

_, login = req("POST", "/auth/login", body={"email": EMAIL, "password": PASSWORD})
token = login["tokens"]["access_token"]

_, plans = req("GET", "/paper-validation/run-plans?limit=50", token=token)
planned = [p for p in plans.get("items", []) if p.get("plan_status") == "planned"]
if not planned:
    _, listing = req("GET", "/alerts/setup-review?limit=50", token=token)
    alerts = listing.get("items") or []
    if not alerts:
        raise SystemExit("No setup-review alerts available for bootstrap")
    plan_id = build_plan(token, alerts[0]["alert_id"])
else:
    plan_id = planned[0]["plan_id"]

# persistence probe
_, start = req("POST", f"/paper-validation/run-plans/{plan_id}/start", token=token, body={
    "confirm": START, "notes": "validate-run-sessions-staging",
})
sid = start["session"]["session_id"]
code, _ = req("GET", f"/paper-validation/run-sessions/{sid}", token=token)
assert code == 200, f"persistence probe failed: readback {code}"
print("  OK: persistence probe (start + readback)")

# duplicate guard
_, dup = req("POST", f"/paper-validation/run-plans/{plan_id}/start", token=token, body={"confirm": START})
assert dup.get("already_active") is True, dup
print("  OK: duplicate active session")

# non-planned blocked (bootstrap second plan when needed)
second = next((p["plan_id"] for p in plans.get("items", []) if p.get("plan_status") == "planned" and p["plan_id"] != plan_id), None)
if not second:
    _, listing = req("GET", "/alerts/setup-review?limit=50", token=token)
    alerts = listing.get("items") or []
    if len(alerts) < 2:
        raise SystemExit("Need a second setup-review alert to validate non-planned blocking")
    second = build_plan(token, alerts[1]["alert_id"])
req("PATCH", f"/paper-validation/run-plans/{second}", token=token, body={"plan_status": "needs_revision"})
code, _ = req("POST", f"/paper-validation/run-plans/{second}/start", token=token, body={"confirm": START})
assert code == 422, f"non-planned start should be 422, got {code}"
print("  OK: non-planned start blocked")

print("Run session staging validation passed.")
PY

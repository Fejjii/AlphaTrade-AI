#!/usr/bin/env bash
# API staging validation for Slice 87 coaching (read + audited save into lessons).
# No orders, proposals, approvals, execution, exchange, Telegram, or automation.
#
# Usage:
#   STAGING_BOOTSTRAP_PASSWORD='...' ./scripts/validate-coaching-staging.sh
set -euo pipefail

BACKEND_URL="${BACKEND_URL:-https://alphatrade-api-staging.onrender.com}"
BACKEND_URL="${BACKEND_URL%/}"
EMAIL="${STAGING_BOOTSTRAP_EMAIL:-seed-bootstrap-1782212606@example.com}"
PASSWORD="${STAGING_BOOTSTRAP_PASSWORD:-}"

if [[ -z "$PASSWORD" ]]; then
  echo "STAGING_BOOTSTRAP_PASSWORD required (not printed)." >&2
  exit 1
fi

echo "Coaching staging validation — BACKEND_URL=${BACKEND_URL}"

health_json="$(curl -fsS "${BACKEND_URL}/health")"
python3 - <<'PY' "$health_json"
import json, sys

payload = json.loads(sys.argv[1])
assert payload.get("execution_mode") == "paper", payload
assert payload.get("real_trading_enabled") is False, payload
print(f"  OK: paper mode; git_sha={payload.get('git_sha')}")
PY

python3 - <<PY
import json, sys, urllib.error, urllib.request

BASE = "${BACKEND_URL}"
EMAIL = "${EMAIL}"
PASSWORD = "${PASSWORD}"

COACHING_CATEGORIES = {
    "missed_entry",
    "should_have_waited",
    "should_have_avoided",
    "invalidation_hit",
    "low_quality_setup",
    "overconfidence",
    "weak_confidence_correlation",
}
SEVERITIES = {"low", "medium", "high", "critical"}
FORBIDDEN_KEY_TERMS = (
    "order",
    "execution",
    "proposal",
    "approval",
    "exchange",
    "telegram",
    "secret",
    "api_key",
    "token",
    "password",
)
ACTION_WORDS = ("buy", "sell", "place order", "execute", "take this trade")

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    status = "OK" if condition else "FAIL"
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))
    if not condition:
        failures.append(name)


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


def scan_forbidden_keys(obj, path=""):
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            if kl not in ("user_id", "organization_id") and any(
                term in kl for term in FORBIDDEN_KEY_TERMS
            ):
                hits.append(f"{path}.{k}")
            hits.extend(scan_forbidden_keys(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hits.extend(scan_forbidden_keys(v, f"{path}[{i}]"))
    return hits


def scan_action_wording(obj):
    hits = []
    if isinstance(obj, str):
        lower = obj.lower()
        for word in ACTION_WORDS:
            if word in lower:
                hits.append(word)
    elif isinstance(obj, dict):
        for v in obj.values():
            hits.extend(scan_action_wording(v))
    elif isinstance(obj, list):
        for v in obj:
            hits.extend(scan_action_wording(v))
    return hits


code, login = req("POST", "/auth/login", body={"email": EMAIL, "password": PASSWORD})
check("auth login", login is not None and code == 200, f"status={code}")
if code != 200:
    raise SystemExit(1)
token = login["tokens"]["access_token"]

code, prompts = req("GET", "/coaching/prompts", token=token)
prompts_ok = code == 200 and isinstance(prompts, dict) and "items" in prompts
check("prompts endpoint works", prompts_ok, f"status={code}")
if prompts_ok:
    check("prompts no forbidden keys", not scan_forbidden_keys(prompts))
    check("prompts review-only wording", not scan_action_wording(prompts))
    check(
        "prompt text uses review framing",
        all(
            (item.get("prompt_text") or "").lower().startswith("review this behavior")
            for item in prompts.get("items", [])
        )
        or prompts.get("total", 0) == 0,
    )

code, summary = req("GET", "/coaching/summary", token=token)
summary_ok = code == 200 and isinstance(summary, dict) and "total_open" in summary
check("summary endpoint works", summary_ok, f"status={code}")

items = prompts.get("items", []) if prompts_ok else []
if items:
    first = items[0]
    cat = first["category"]
    key = first["source"]["matched_key"]
    code, explain = req("GET", f"/coaching/prompts/{cat}/{key}/explain", token=token)
    check("explain endpoint works", code == 200, f"status={code}")
    check("explain no forbidden keys", not scan_forbidden_keys(explain))

code, strict = req("GET", "/coaching/prompts?min_sample=100", token=token)
check("small-sample safety", code == 200, f"status={code}")

if items:
    first = items[0]
    save_body = {
        "category": first["category"],
        "matched_dimension": first["source"]["matched_dimension"],
        "matched_key": first["source"]["matched_key"],
        "min_sample": prompts.get("min_sample", 5),
    }
    code, saved = req("POST", "/coaching/prompts/save", token=token, body=save_body)
    check("save endpoint works for trader", code == 200 and saved.get("source_type") == "coaching", f"status={code}")
    if code == 200:
        check("saved lesson has no proposed_rule_update", saved.get("proposed_rule_update") is None)
        code2, again = req("POST", "/coaching/prompts/save", token=token, body=save_body)
        check("save idempotent", code2 == 200 and again.get("id") == saved.get("id"), f"status={code2}")
else:
    print("  INFO: no coaching prompts in staging; save/idempotency skipped")

code, stale = req(
    "POST",
    "/coaching/prompts/save",
    token=token,
    body={
        "category": "invalidation_hit",
        "matched_dimension": "condition",
        "matched_key": "__nonexistent_pattern__",
        "min_sample": 5,
    },
)
check("stale pattern rejected", code == 422, f"status={code}")

if failures:
    print(f"FAILED checks: {failures}")
    raise SystemExit(1)

print("Coaching staging validation passed.")
PY

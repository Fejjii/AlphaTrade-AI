#!/usr/bin/env bash
# Read-only API staging validation for Slice 85 validation prioritization.
# GET-only — no orders, proposals, approvals, execution, exchange, Telegram, or automation.
#
# Usage:
#   STAGING_BOOTSTRAP_PASSWORD='...' ./scripts/validate-validation-priority-staging.sh
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

echo "Validation priority staging validation — BACKEND_URL=${BACKEND_URL}"

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

ACTION_LABELS = {"prioritize", "watch", "collect_more_data", "avoid_for_now"}
RELIABILITY_TIERS = {"none", "low", "medium", "high"}
FORBIDDEN_KEY_TERMS = (
    "order",
    "execution",
    "proposal",
    "approval",
    "exchange",
    "telegram",
    "secret",
    "api_key",
    "apikey",
    "token",
    "password",
    "webhook",
    "private_key",
)

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


code, login = req("POST", "/auth/login", body={"email": EMAIL, "password": PASSWORD})
check("auth login", login is not None and code == 200, f"status={code}")
if code != 200:
    raise SystemExit(1)
token = login["tokens"]["access_token"]

# 1. queue endpoint (org scope default; no user filter).
code, queue = req("GET", "/validation-priority/queue", token=token)
queue_ok = code == 200 and isinstance(queue, dict) and "organization_id" in queue
check("queue endpoint works", queue_ok, f"status={code}")
if queue_ok:
    check("queue org scope default (user_id null)", queue.get("user_id") is None)
    check("queue no order/exec/exchange/secret keys", not scan_forbidden_keys(queue))
    labels_ok = all(
        item.get("action_label") in ACTION_LABELS and item.get("reliability") in RELIABILITY_TIERS
        for item in queue.get("items", [])
    )
    check("queue action labels + reliability within enums", labels_ok)

# 2. summary endpoint.
code, summary = req("GET", "/validation-priority/summary", token=token)
summary_ok = code == 200 and isinstance(summary, dict) and "total_pending" in summary
check("summary endpoint works", summary_ok, f"status={code}")
if summary_ok:
    check("summary no forbidden keys", not scan_forbidden_keys(summary))
    action_labels = {row.get("action_label") for row in summary.get("by_action", [])}
    check("summary reports all action labels", action_labels == ACTION_LABELS, str(action_labels))

# 3. explain endpoint on the first pending item (if any); else confirm empty is safe.
items = queue.get("items", []) if queue_ok else []
if items:
    first = items[0]
    code, explain = req(
        "GET",
        f"/validation-priority/explain/{first['item_type']}/{first['item_id']}",
        token=token,
    )
    check(
        "explain endpoint works",
        code == 200 and explain.get("item", {}).get("item_id") == first["item_id"],
        f"status={code}",
    )
    check("explain no forbidden keys", not scan_forbidden_keys(explain))
else:
    print("  INFO: no pending items in staging org; empty-state handled safely by queue/summary")

# 4. optional user filter accepted (structurally).
code, filtered = req(
    "GET", f"/validation-priority/queue?user_id={queue.get('organization_id')}", token=token
)
check("optional user filter accepted", code == 200 and filtered.get("user_id") is not None,
      f"status={code}")

# 5. small-sample safety: high min_sample must not error and must not fake high priority.
code, strict = req("GET", "/validation-priority/queue?min_sample=100", token=token)
strict_ok = code == 200 and all(
    item.get("action_label") in ACTION_LABELS for item in strict.get("items", [])
)
check("small-sample queue handled safely", strict_ok, f"status={code}")

# 6. item_type filter.
code, plans = req("GET", "/validation-priority/queue?item_type=run_plan", token=token)
check(
    "item_type=run_plan filter works",
    code == 200 and all(i.get("item_type") == "run_plan" for i in plans.get("items", [])),
    f"status={code}",
)

if failures:
    print(f"FAILED checks: {failures}")
    raise SystemExit(1)

print("Validation priority staging validation passed.")
PY

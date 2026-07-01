#!/usr/bin/env bash
# Read-only API staging validation for Slice 84 learning analytics.
# GET-only — no orders, proposals, approvals, execution, exchange, Telegram, or automation.
#
# Usage:
#   STAGING_BOOTSTRAP_PASSWORD='...' ./scripts/validate-learning-analytics-staging.sh
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

echo "Learning analytics staging validation — BACKEND_URL=${BACKEND_URL}"

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


def scan_forbidden_keys(obj, path: str = "") -> list[str]:
    hits: list[str] = []
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

org_id = None
endpoints = [
    ("summary", "/learning-analytics/summary"),
    ("setup-performance", "/learning-analytics/setup-performance"),
    ("discipline", "/learning-analytics/discipline"),
    ("confidence-outcome", "/learning-analytics/confidence-outcome"),
    ("behavior-insights", "/learning-analytics/behavior-insights"),
    ("lessons", "/learning-analytics/lessons"),
    ("setup-ranking", "/learning-analytics/setup-ranking"),
]

for label, path in endpoints:
    code, payload = req("GET", path, token=token)
    ok = code == 200 and isinstance(payload, dict) and "organization_id" in payload
    check(f"{label} endpoint works", ok, f"status={code}")
    if not ok:
        continue
    if org_id is None:
        org_id = payload.get("organization_id")
    check(
        f"{label} org scope default (user_id null)",
        payload.get("organization_id") == org_id and payload.get("user_id") is None,
    )
    hits = scan_forbidden_keys(payload)
    check(f"{label} no order/exec/exchange/secret keys", not hits, str(hits))

code, filtered = req("GET", f"/learning-analytics/summary?user_id={org_id}", token=token)
check(
    "optional user filter accepted",
    code == 200 and filtered.get("user_id") is not None,
    f"status={code}",
)

code, disc = req("GET", "/learning-analytics/discipline?min_sample=100", token=token)
check(
    "small-sample discipline handled safely",
    code == 200
    and isinstance(disc.get("insufficient_data"), bool)
    and (disc.get("discipline_score") is None or disc.get("insufficient_data") is False),
    f"insufficient_data={disc.get('insufficient_data')}",
)

code, perf = req("GET", "/learning-analytics/setup-performance?min_sample=100", token=token)
all_insufficient = all(g.get("insufficient_data") is True for g in perf.get("groups", []))
check(
    "small-sample setup-performance handled safely",
    code == 200 and (not perf.get("groups") or all_insufficient),
)

code, rank = req(
    "GET", "/learning-analytics/setup-ranking?dimension=confidence_bucket", token=token
)
check("setup-ranking dimension=confidence_bucket works", code == 200, f"status={code}")

if failures:
    print(f"FAILED checks: {failures}")
    raise SystemExit(1)

print("Learning analytics staging validation passed.")
PY

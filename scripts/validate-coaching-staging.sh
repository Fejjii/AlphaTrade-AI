#!/usr/bin/env bash
# API staging validation for Slice 87 coaching (read + audited save into lessons).
# Slice 87B: seeds record-only paper validation outcomes when the bootstrap org has
# no coaching prompts above threshold, then validates explain, save, and idempotency.
# No orders, proposals, approvals, execution, exchange, Telegram, scans, or automation.
#
# Usage:
#   STAGING_BOOTSTRAP_PASSWORD='...' ./scripts/validate-coaching-staging.sh
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

MIN_SAMPLE = 5
SEED_SESSIONS = 6

START = "START_PAPER_VALIDATION_RUN"
CREATE_DRAFT = "CREATE_PAPER_VALIDATION_DRAFT"
QUEUE = "QUEUE_PAPER_VALIDATION_CANDIDATE"
CREATE_PLAN = "CREATE_PAPER_VALIDATION_RUN_PLAN"
RECORD_OUTCOME = "RECORD_PAPER_VALIDATION_OUTCOME"

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


def build_plan(token, alert_id):
    req(
        "PATCH",
        f"/alerts/setup-review/{alert_id}",
        token=token,
        body={"review_status": "important"},
    )
    _, draft = req(
        "POST",
        f"/alerts/setup-review/{alert_id}/draft",
        token=token,
        body={
            "confirm": CREATE_DRAFT,
            "risk_mode": "conservative",
            "notes": "validate-coaching-staging-seed",
        },
    )
    draft_id = draft["draft"]["draft_id"]
    req(
        "PATCH",
        f"/paper-validation/drafts/{draft_id}/prep",
        token=token,
        body={
            "prep_status": "ready_for_validation",
            "thesis": "t",
            "entry_criteria": "e",
            "invalidation_criteria": "i",
            "risk_notes": "r",
            "checklist": {
                k: True
                for k in (
                    "trend_checked",
                    "support_resistance_checked",
                    "volume_checked",
                    "risk_reward_checked",
                    "invalidation_checked",
                    "higher_timeframe_checked",
                    "news_or_funding_checked",
                )
            },
        },
    )
    _, queued = req(
        "POST",
        f"/paper-validation/drafts/{draft_id}/queue",
        token=token,
        body={"confirm": QUEUE},
    )
    cid = queued["candidate"]["candidate_id"]
    req(
        "PATCH",
        f"/paper-validation/candidates/{cid}",
        token=token,
        body={"candidate_status": "reviewing"},
    )
    _, plan = req(
        "POST",
        f"/paper-validation/candidates/{cid}/plan",
        token=token,
        body={
            "confirm": CREATE_PLAN,
            "validation_window": "intraday",
            "observation_timeframe": "1h",
            "max_duration_minutes": 240,
            "planned_entry_rule": "e",
            "planned_invalidation_rule": "i",
            "planned_success_criteria": "s",
            "planned_failure_criteria": "f",
        },
    )
    return plan["plan"]["plan_id"], plan["plan"].get("condition")


def ensure_plan(token):
    _, plans = req("GET", "/paper-validation/run-plans?limit=50", token=token)
    planned = [
        p
        for p in plans.get("items", [])
        if p.get("plan_status") == "planned" and p.get("condition")
    ]
    if planned:
        return planned[0]["plan_id"], planned[0]["condition"]
    _, listing = req("GET", "/alerts/setup-review?limit=50", token=token)
    alerts = [a for a in (listing.get("items") or []) if a.get("condition")]
    if not alerts:
        raise SystemExit("No setup-review alert with condition available for coaching seed")
    return build_plan(token, alerts[0]["alert_id"])


def finish_running_on_plan(token, plan_id):
    _, sessions = req("GET", "/paper-validation/run-sessions?limit=50", token=token)
    for session in sessions.get("items", []):
        if session.get("run_plan_id") != plan_id or session.get("session_status") != "running":
            continue
        sid = session["session_id"]
        code, _ = req("GET", f"/paper-validation/run-sessions/{sid}/result", token=token)
        if code != 200:
            req(
                "POST",
                f"/paper-validation/run-sessions/{sid}/result",
                token=token,
                body={
                    "confirm": RECORD_OUTCOME,
                    "outcome": "invalidated",
                    "success_criteria_met": "not_met",
                    "failure_criteria_met": "met",
                    "invalidation_hit": True,
                    "entry_assessment": "entered_as_planned",
                    "discipline_assessment": "disciplined",
                },
            )
        req(
            "PATCH",
            f"/paper-validation/run-sessions/{sid}",
            token=token,
            body={"session_status": "completed"},
        )


def record_invalidation_session(token, plan_id, index):
    finish_running_on_plan(token, plan_id)
    _, start = req(
        "POST",
        f"/paper-validation/run-plans/{plan_id}/start",
        token=token,
        body={"confirm": START, "notes": f"validate-coaching-staging-seed-{index}"},
    )
    sid = start["session"]["session_id"]
    code, result = req(
        "POST",
        f"/paper-validation/run-sessions/{sid}/result",
        token=token,
        body={
            "confirm": RECORD_OUTCOME,
            "outcome": "invalidated",
            "success_criteria_met": "not_met",
            "failure_criteria_met": "met",
            "invalidation_hit": True,
            "entry_assessment": "entered_as_planned",
            "discipline_assessment": "disciplined",
            "lessons": "Coaching staging seed outcome.",
        },
    )
    if code != 200:
        raise SystemExit(f"Failed to record coaching seed outcome: status={code}")
    code, _ = req(
        "PATCH",
        f"/paper-validation/run-sessions/{sid}",
        token=token,
        body={"session_status": "completed"},
    )
    if code != 200:
        raise SystemExit(f"Failed to complete coaching seed session: status={code}")
    return sid


def seed_coaching_outcomes(token):
    _, prompts = req("GET", f"/coaching/prompts?min_sample={MIN_SAMPLE}", token=token)
    if prompts.get("total", 0) >= 1:
        print("  OK: coaching prompts already present; seed skipped")
        return prompts

    plan_id, condition = ensure_plan(token)
    print(
        f"  INFO: seeding record-only paper validation outcomes "
        f"(plan={plan_id}, condition={condition}, sessions={SEED_SESSIONS})"
    )
    for index in range(1, SEED_SESSIONS + 1):
        sid = record_invalidation_session(token, plan_id, index)
        print(f"  OK: seeded completed session {sid}")

    _, prompts = req("GET", f"/coaching/prompts?min_sample={MIN_SAMPLE}", token=token)
    if prompts.get("total", 0) >= 1:
        return prompts

    print("  INFO: extra seed pass (3 more invalidated sessions)")
    for index in range(SEED_SESSIONS + 1, SEED_SESSIONS + 4):
        record_invalidation_session(token, plan_id, index)
    _, prompts = req("GET", f"/coaching/prompts?min_sample={MIN_SAMPLE}", token=token)
    return prompts


code, login = req("POST", "/auth/login", body={"email": EMAIL, "password": PASSWORD})
check("auth login", login is not None and code == 200, f"status={code}")
if code != 200:
    raise SystemExit(1)
token = login["tokens"]["access_token"]

prompts = seed_coaching_outcomes(token)

code, prompts = req("GET", "/coaching/prompts", token=token)
prompts_ok = code == 200 and isinstance(prompts, dict) and "items" in prompts
check("prompts endpoint works", prompts_ok, f"status={code}")
check(
    "coaching prompt generated",
    prompts_ok and prompts.get("total", 0) >= 1,
    f"total={prompts.get('total', 0)}",
)
if prompts_ok:
    check("prompts no forbidden keys", not scan_forbidden_keys(prompts))
    check("prompts review-only wording", not scan_action_wording(prompts))
    check(
        "prompt text uses review framing",
        all(
            (item.get("prompt_text") or "").lower().startswith("review this behavior")
            for item in prompts.get("items", [])
        ),
    )
    check(
        "prompt categories within enum",
        all(item.get("category") in COACHING_CATEGORIES for item in prompts.get("items", [])),
    )
    check(
        "prompt severities within enum",
        all(item.get("severity") in SEVERITIES for item in prompts.get("items", [])),
    )

code, summary = req("GET", "/coaching/summary", token=token)
summary_ok = code == 200 and isinstance(summary, dict) and "total_open" in summary
check("summary endpoint works", summary_ok, f"status={code}")
if summary_ok:
    check("summary reports open prompts", summary.get("total_open", 0) >= 1)

items = prompts.get("items", []) if prompts_ok else []
if items:
    first = items[0]
    cat = first["category"]
    key = first["source"]["matched_key"]
    code, explain = req(
        "GET",
        f"/coaching/prompts/{cat}/{key}/explain?min_sample={MIN_SAMPLE}",
        token=token,
    )
    check("explain endpoint works", code == 200, f"status={code}")
    if code == 200:
        check("explain no forbidden keys", not scan_forbidden_keys(explain))
        check("explain review-only wording", not scan_action_wording(explain))
        explain_prompt = explain.get("prompt") or {}
        check(
            "explain prompt text uses review framing",
            (explain_prompt.get("prompt_text") or "").lower().startswith("review this behavior"),
        )

code, strict = req("GET", f"/coaching/prompts?min_sample=100", token=token)
check("small-sample safety", code == 200, f"status={code}")

if items:
    first = items[0]
    save_body = {
        "category": first["category"],
        "matched_dimension": first["source"]["matched_dimension"],
        "matched_key": first["source"]["matched_key"],
        "min_sample": prompts.get("min_sample", MIN_SAMPLE),
    }
    code, saved = req("POST", "/coaching/prompts/save", token=token, body=save_body)
    check(
        "save endpoint works for trader",
        code == 200 and saved.get("source_type") == "coaching",
        f"status={code}",
    )
    if code == 200:
        check("saved lesson has no proposed_rule_update", saved.get("proposed_rule_update") is None)
        check(
            "saved lesson text uses review framing",
            (saved.get("lesson_text") or "").lower().startswith("review this behavior"),
        )
        check("saved lesson no forbidden keys", not scan_forbidden_keys(saved))
        check("saved lesson review-only wording", not scan_action_wording(saved))
        code2, again = req("POST", "/coaching/prompts/save", token=token, body=save_body)
        check(
            "save idempotent",
            code2 == 200 and again.get("id") == saved.get("id"),
            f"status={code2}",
        )
else:
    check("save validation prerequisites", False, "no coaching prompts available")

code, stale = req(
    "POST",
    "/coaching/prompts/save",
    token=token,
    body={
        "category": "invalidation_hit",
        "matched_dimension": "condition",
        "matched_key": "__nonexistent_pattern__",
        "min_sample": MIN_SAMPLE,
    },
)
check("stale pattern rejected", code == 422, f"status={code}")

if failures:
    print(f"FAILED checks: {failures}")
    raise SystemExit(1)

print("Coaching staging validation passed.")
PY

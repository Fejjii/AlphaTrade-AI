#!/usr/bin/env bash
# Post-activation smoke for paper Watcher monitoring.
#
# Does not activate Watcher, does not deploy, and does not modify environment
# variables. Refuses to run with no target. Proves the five fail-closed cases
# only through --self-check (no network).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ "${1:-}" == "--self-check" ]]; then
  grep -q 'Does not activate Watcher' "$0"
  grep -q 'replay evidence' "$0"
  grep -q 'provider unavailable' "$0"
  grep -q 'invalid lineage' "$0"
  grep -q 'real trading' "$0"
  grep -q 'unhealthy migration' "$0"
  grep -q 'heartbeat_age_seconds' "$0"
  grep -q 'health_state' "$0"
  grep -q 'STALE' "$0"
  if grep -E '^[[:space:]]*(export[[:space:]]+)?WATCHER_PAPER_STAGING_ACTIVATION=true' "$0"; then
    echo "FAIL: smoke must not arm activation" >&2
    exit 1
  fi
  if grep -E '^[[:space:]]*(export[[:space:]]+)?ENABLE_REAL_TRADING=true' "$0"; then
    echo "FAIL: smoke must not enable real trading" >&2
    exit 1
  fi
  echo "watcher paper activation smoke self-check passed."
  exit 0
fi

if [[ -z "${BASE_URL:-}" && -z "${WATCHER_ACTIVATION_SMOKE_JSON:-}" ]]; then
  echo "Refusing to run: set BASE_URL or WATCHER_ACTIVATION_SMOKE_JSON." >&2
  echo "This script does not activate Watcher." >&2
  echo "Fail-closed cases: replay evidence, provider unavailable, invalid lineage, real trading, unhealthy migration." >&2
  exit 2
fi

if [[ -n "${BASE_URL:-}" ]]; then
  BASE_URL="${BASE_URL%/}"
  health_json="$(curl -fsS "${BASE_URL}/health")"
  python3 "${ROOT_DIR}/scripts/lib/watcher_paper_health.py" "$health_json"
  python3 - "$health_json" <<'PY'
import json
import sys
from datetime import datetime, timezone

payload = json.loads(sys.argv[1])
if payload.get("environment") == "production":
    print("FAIL: production watcher is forbidden", file=sys.stderr)
    sys.exit(1)
runtime = payload.get("worker_runtime")
if not isinstance(runtime, dict) or runtime.get("available") is not True:
    print("FAIL: post-activation smoke expects observed worker_runtime", file=sys.stderr)
    sys.exit(1)
watcher = runtime.get("watcher")
if not isinstance(watcher, dict):
    print("FAIL: worker_runtime.watcher is missing", file=sys.stderr)
    sys.exit(1)
if watcher.get("activation_state") not in {"running", "cleared", "monitoring"}:
    print(
        "FAIL: watcher activation_state="
        f"{watcher.get('activation_state')!r}",
        file=sys.stderr,
    )
    sys.exit(1)
if watcher.get("health_state") != "RUNNING" or watcher.get("available") is not True:
    print(
        "FAIL: watcher health_state="
        f"{watcher.get('health_state')!r} available={watcher.get('available')!r}",
        file=sys.stderr,
    )
    sys.exit(1)
heartbeat_at = watcher.get("heartbeat_at")
if not isinstance(heartbeat_at, str) or not heartbeat_at:
    print("FAIL: watcher heartbeat_at is missing", file=sys.stderr)
    sys.exit(1)
limit = watcher.get("heartbeat_stale_after_seconds")
reported_age = watcher.get("heartbeat_age_seconds")
if not isinstance(limit, (int, float)) or isinstance(limit, bool):
    print("FAIL: watcher heartbeat freshness threshold is missing", file=sys.stderr)
    sys.exit(1)
if not isinstance(reported_age, (int, float)) or isinstance(reported_age, bool):
    print("FAIL: watcher heartbeat_age_seconds is missing", file=sys.stderr)
    sys.exit(1)
if reported_age < 0 or reported_age > float(limit):
    print(
        f"FAIL: watcher heartbeat is STALE age={reported_age} limit={limit}",
        file=sys.stderr,
    )
    sys.exit(1)
stamp = datetime.fromisoformat(heartbeat_at)
if stamp.tzinfo is None:
    print("FAIL: watcher heartbeat_at is not timezone-aware", file=sys.stderr)
    sys.exit(1)
age = (datetime.now(timezone.utc) - stamp).total_seconds()
if age < 0 or age > float(limit):
    print(
        f"FAIL: watcher heartbeat freshness failed age={age} limit={limit}",
        file=sys.stderr,
    )
    sys.exit(1)
print("  OK: observed paper watcher runtime")
PY
fi

if [[ -n "${WATCHER_ACTIVATION_SMOKE_JSON:-}" ]]; then
  cd "${ROOT_DIR}/backend"
  exec uv run python -m app.workers.watcher_activation --smoke-json "${WATCHER_ACTIVATION_SMOKE_JSON}"
fi

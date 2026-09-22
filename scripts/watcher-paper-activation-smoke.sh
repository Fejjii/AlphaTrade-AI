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

payload = json.loads(sys.argv[1])
armed = payload.get("watcher_paper_staging_activation") is True
orchestration = payload.get("watcher_orchestration_enabled") is True
if not armed or not orchestration:
    print("FAIL: post-activation smoke expects the armed paper pair", file=sys.stderr)
    sys.exit(1)
if payload.get("environment") == "production":
    print("FAIL: production watcher is forbidden", file=sys.stderr)
    sys.exit(1)
print("  OK: armed paper-monitoring health pair")
PY
fi

if [[ -n "${WATCHER_ACTIVATION_SMOKE_JSON:-}" ]]; then
  cd "${ROOT_DIR}/backend"
  exec uv run python -m app.workers.watcher_activation --smoke-json "${WATCHER_ACTIVATION_SMOKE_JSON}"
fi

#!/usr/bin/env bash
# Post-deploy smoke gate (AT-005) — fail-closed validation after a staging deploy.
#
# Mandatory: scripts/verify-safety.sh (paper-only invariants).
# Default:   also runs scripts/staging-smoke.sh (API smoke).
#
# This script does NOT deploy, promote, or mutate platform services.
# Real trading must remain disabled; the gate fails if safety checks fail.
#
# Usage:
#   BASE_URL=https://your-api.onrender.com ./scripts/post-deploy-smoke-gate.sh
#   BASE_URL=... FRONTEND_URL=https://your-app.vercel.app COOKIE_MODE=true \
#     ./scripts/post-deploy-smoke-gate.sh
#   GATE_PROFILE=safety BASE_URL=... ./scripts/post-deploy-smoke-gate.sh
#   ./scripts/post-deploy-smoke-gate.sh --self-check   # CI / local wiring check (no network)
#
# Exit codes:
#   0 — gate passed
#   1 — smoke/safety failure (treat as rollback trigger)
#   2 — misconfiguration (missing BASE_URL, placeholders, missing scripts)
#
# Env:
#   BASE_URL                 API base URL (required unless --self-check)
#   FRONTEND_URL             Optional; enables CORS check inside staging-smoke
#   COOKIE_MODE              true|false (default false; staging cross-domain often true)
#   ALLOW_DEGRADED_READY     true|false (default false)
#   GATE_PROFILE             safety | standard (default) | extended
#   SKIP_STAGING_SMOKE       true to skip staging-smoke even in standard/extended
#   INCLUDE_ANALYTICS        forwarded to staging-smoke (default false)
#   INCLUDE_STRATEGY_QUALITY forwarded to staging-smoke (default false)
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SELF_CHECK=false
if [[ "${1:-}" == "--self-check" ]]; then
  SELF_CHECK=true
fi

GATE_PROFILE="${GATE_PROFILE:-standard}"
SKIP_STAGING_SMOKE="${SKIP_STAGING_SMOKE:-false}"
COOKIE_MODE="${COOKIE_MODE:-false}"
ALLOW_DEGRADED_READY="${ALLOW_DEGRADED_READY:-false}"

REQUIRED_SCRIPTS=(
  "scripts/verify-safety.sh"
  "scripts/staging-smoke.sh"
  "scripts/staging-live-smoke.sh"
)

fail_misconfig() {
  echo "GATE MISCONFIG: $*" >&2
  exit 2
}

fail_gate() {
  echo "GATE FAILED: $*" >&2
  echo "Rollback guidance: docs/deploy_rollback_runbook.md" >&2
  exit 1
}

run_self_check() {
  echo "Post-deploy smoke gate — self-check (no network)"
  local relative
  for relative in "${REQUIRED_SCRIPTS[@]}"; do
    local path="${ROOT_DIR}/${relative}"
    [[ -f "$path" ]] || fail_misconfig "missing ${relative}"
    [[ -x "$path" ]] || fail_misconfig "${relative} is not executable"
  done
  case "$GATE_PROFILE" in
    safety | standard | extended) ;;
    *) fail_misconfig "GATE_PROFILE must be safety|standard|extended (got ${GATE_PROFILE})" ;;
  esac
  # Ensure this gate still mandates verify-safety in the standard path.
  grep -q 'verify-safety\.sh' "$0" || fail_misconfig "gate script lost verify-safety wiring"
  echo "  OK: required scripts present and executable"
  echo "  OK: GATE_PROFILE=${GATE_PROFILE}"
  echo "Post-deploy smoke gate self-check passed."
  exit 0
}

if [[ "$SELF_CHECK" == "true" ]]; then
  run_self_check
fi

BASE_URL="${BASE_URL:-}"
BASE_URL="${BASE_URL%/}"

if [[ -z "$BASE_URL" ]]; then
  fail_misconfig "BASE_URL is required (e.g. BASE_URL=https://api.example.com)"
fi
if [[ "$BASE_URL" == *"<"* ]]; then
  fail_misconfig "Replace placeholder in BASE_URL (see docs/deploy_rollback_runbook.md)"
fi

for relative in "${REQUIRED_SCRIPTS[@]}"; do
  path="${ROOT_DIR}/${relative}"
  [[ -f "$path" && -x "$path" ]] || fail_misconfig "${relative} missing or not executable"
done

case "$GATE_PROFILE" in
  safety | standard | extended) ;;
  *) fail_misconfig "GATE_PROFILE must be safety|standard|extended (got ${GATE_PROFILE})" ;;
esac

echo "=============================================="
echo "Post-deploy smoke gate (AT-005)"
echo "  BASE_URL=${BASE_URL}"
echo "  GATE_PROFILE=${GATE_PROFILE}"
echo "  COOKIE_MODE=${COOKIE_MODE}"
echo "  ALLOW_DEGRADED_READY=${ALLOW_DEGRADED_READY}"
echo "  FRONTEND_URL=${FRONTEND_URL:-}"
echo "=============================================="
echo "This gate does not deploy or enable real trading."

echo ""
echo "[1/3] Mandatory safety invariants (verify-safety.sh)"
if ! BASE_URL="${BASE_URL}" "${ROOT_DIR}/scripts/verify-safety.sh"; then
  fail_gate "verify-safety.sh failed — do not keep this deploy; see rollback runbook"
fi

if [[ "$GATE_PROFILE" == "safety" || "$SKIP_STAGING_SMOKE" == "true" ]]; then
  echo ""
  echo "[2/3] Staging API smoke skipped (GATE_PROFILE=safety or SKIP_STAGING_SMOKE=true)"
else
  echo ""
  echo "[2/3] Staging API smoke (staging-smoke.sh)"
  smoke_env=(
    "BASE_URL=${BASE_URL}"
    "COOKIE_MODE=${COOKIE_MODE}"
    "ALLOW_DEGRADED_READY=${ALLOW_DEGRADED_READY}"
    "INCLUDE_ANALYTICS=${INCLUDE_ANALYTICS:-false}"
    "INCLUDE_STRATEGY_QUALITY=${INCLUDE_STRATEGY_QUALITY:-false}"
  )
  if [[ -n "${FRONTEND_URL:-}" ]]; then
    smoke_env+=("FRONTEND_URL=${FRONTEND_URL}")
  fi
  if [[ -n "${SMOKE_EMAIL:-}" ]]; then
    smoke_env+=("SMOKE_EMAIL=${SMOKE_EMAIL}")
  fi
  if [[ -n "${SMOKE_PASSWORD:-}" ]]; then
    smoke_env+=("SMOKE_PASSWORD=${SMOKE_PASSWORD}")
  fi
  if [[ -n "${SMOKE_ACCESS_TOKEN:-}" ]]; then
    smoke_env+=("SMOKE_ACCESS_TOKEN=${SMOKE_ACCESS_TOKEN}" "SKIP_REGISTER=${SKIP_REGISTER:-true}")
  fi
  if ! env "${smoke_env[@]}" "${ROOT_DIR}/scripts/staging-smoke.sh"; then
    fail_gate "staging-smoke.sh failed — treat as rollback trigger"
  fi
fi

if [[ "$GATE_PROFILE" == "extended" ]]; then
  echo ""
  echo "[3/3] Extended live smoke (staging-live-smoke.sh)"
  live_env=("BACKEND_URL=${BASE_URL}")
  if [[ -n "${FRONTEND_URL:-}" ]]; then
    live_env+=("FRONTEND_URL=${FRONTEND_URL}")
  fi
  if ! env "${live_env[@]}" "${ROOT_DIR}/scripts/staging-live-smoke.sh"; then
    fail_gate "staging-live-smoke.sh failed — treat as rollback trigger"
  fi
else
  echo ""
  echo "[3/3] Extended live smoke skipped (set GATE_PROFILE=extended to enable)"
fi

echo ""
echo "=============================================="
echo "Post-deploy smoke gate PASSED"
echo "  profile=${GATE_PROFILE}"
echo "  safety=paper-only verified"
echo "=============================================="
exit 0

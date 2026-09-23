#!/usr/bin/env bash
# Paper Watcher rollback command.
#
# Prints the operator plan and does not apply it. Does not deploy, does not
# edit staging environment files, does not enable Telegram, and does not enable
# real trading. Does not clear the kill switch.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ "${1:-}" == "--self-check" ]]; then
  PLAN="${ROOT_DIR}/backend/src/app/workers/watcher_activation.py"
  grep -q 'Does not deploy' "$0"
  grep -q 'kill switch' "$0"
  grep -q 'ENABLE_REAL_TRADING false' "$PLAN"
  grep -q 'Do not deploy' "$PLAN"
  grep -q 'NOT APPLIED' "$PLAN"
  grep -q 'Leave the kill switch unchanged' "$PLAN"
  if grep -E '^[[:space:]]*render[[:space:]]+deploy' "$0" "$PLAN"; then
    echo "FAIL: rollback command must not call a platform deploy" >&2
    exit 1
  fi
  if grep -E '^[[:space:]]*(export[[:space:]]+)?ENABLE_REAL_TRADING=true' "$0" "$PLAN"; then
    echo "FAIL: rollback command must not enable real trading" >&2
    exit 1
  fi
  if grep -E '^[[:space:]]*(export[[:space:]]+)?TELEGRAM_[A-Z_]+=true' "$0" "$PLAN"; then
    echo "FAIL: rollback command must not activate Telegram" >&2
    exit 1
  fi
  echo "watcher paper rollback self-check passed."
  exit 0
fi

cd "${ROOT_DIR}/backend"
exec uv run python -m app.workers.watcher_activation --rollback-plan

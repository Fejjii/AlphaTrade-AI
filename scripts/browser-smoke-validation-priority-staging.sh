#!/usr/bin/env bash
# Read-only browser smoke for staging validation prioritization (Slice 85).
# No orders, proposals, approvals, execution, exchange, Telegram, or automation.
#
# Usage:
#   STAGING_BOOTSTRAP_PASSWORD='...' ./scripts/browser-smoke-validation-priority-staging.sh
#
# Optional overrides:
#   PLAYWRIGHT_BASE_URL=https://alpha-trade-ai-eight.vercel.app
#   PLAYWRIGHT_API_URL=https://alphatrade-api-staging.onrender.com
#   STAGING_BOOTSTRAP_EMAIL=seed-bootstrap-1782212606@example.com
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/frontend"

export PLAYWRIGHT_SKIP_WEBSERVER=1
export PLAYWRIGHT_STAGING_VALIDATION_PRIORITY_SMOKE=1
export PLAYWRIGHT_BASE_URL="${PLAYWRIGHT_BASE_URL:-https://alpha-trade-ai-eight.vercel.app}"
export PLAYWRIGHT_API_URL="${PLAYWRIGHT_API_URL:-https://alphatrade-api-staging.onrender.com}"
export STAGING_BOOTSTRAP_EMAIL="${STAGING_BOOTSTRAP_EMAIL:-seed-bootstrap-1782212606@example.com}"

if [[ -z "${STAGING_BOOTSTRAP_PASSWORD:-}" ]]; then
  cat >&2 <<'EOF'
STAGING_BOOTSTRAP_PASSWORD required for validation priority browser smoke (not printed).

Example:
  STAGING_BOOTSTRAP_PASSWORD='...' ./scripts/browser-smoke-validation-priority-staging.sh
EOF
  exit 1
fi

# validation-priority-staging.spec.ts reads STAGING_DEMO_* env vars.
export STAGING_DEMO_EMAIL="${STAGING_DEMO_EMAIL:-$STAGING_BOOTSTRAP_EMAIL}"
export STAGING_DEMO_PASSWORD="${STAGING_DEMO_PASSWORD:-$STAGING_BOOTSTRAP_PASSWORD}"

echo "Browser smoke — ${PLAYWRIGHT_BASE_URL}/validation-priority (read only)"
npx playwright test e2e/validation-priority-staging.spec.ts --project=chromium
echo "Validation priority browser smoke passed."

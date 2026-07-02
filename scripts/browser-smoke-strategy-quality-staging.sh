#!/usr/bin/env bash
# Read-only browser smoke for staging strategy quality (Slice 89).
# No orders, proposals, approvals, execution, rule changes, detector toggles,
# exchange, Telegram, or automation.
#
# Usage:
#   STAGING_BOOTSTRAP_PASSWORD='...' ./scripts/browser-smoke-strategy-quality-staging.sh
#
# Optional overrides:
#   PLAYWRIGHT_BASE_URL=https://alpha-trade-ai-eight.vercel.app
#   PLAYWRIGHT_API_URL=https://alphatrade-api-staging.onrender.com
#   STAGING_BOOTSTRAP_EMAIL=seed-bootstrap-1782212606@example.com
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/frontend"

export PLAYWRIGHT_SKIP_WEBSERVER=1
export PLAYWRIGHT_STAGING_STRATEGY_QUALITY_SMOKE=1
export PLAYWRIGHT_BASE_URL="${PLAYWRIGHT_BASE_URL:-https://alpha-trade-ai-eight.vercel.app}"
export PLAYWRIGHT_API_URL="${PLAYWRIGHT_API_URL:-https://alphatrade-api-staging.onrender.com}"
export STAGING_BOOTSTRAP_EMAIL="${STAGING_BOOTSTRAP_EMAIL:-seed-bootstrap-1782212606@example.com}"

if [[ -z "${STAGING_BOOTSTRAP_PASSWORD:-}" ]]; then
  cat >&2 <<'EOF'
STAGING_BOOTSTRAP_PASSWORD required for strategy quality browser smoke (not printed).

Example:
  STAGING_BOOTSTRAP_PASSWORD='...' ./scripts/browser-smoke-strategy-quality-staging.sh
EOF
  exit 1
fi

# strategy-quality-staging.spec.ts reads STAGING_DEMO_* env vars.
export STAGING_DEMO_EMAIL="${STAGING_DEMO_EMAIL:-$STAGING_BOOTSTRAP_EMAIL}"
export STAGING_DEMO_PASSWORD="${STAGING_DEMO_PASSWORD:-$STAGING_BOOTSTRAP_PASSWORD}"

echo "Browser smoke — ${PLAYWRIGHT_BASE_URL}/strategy-quality (read only)"
npx playwright test e2e/strategy-quality-staging.spec.ts --project=chromium
echo "Strategy quality browser smoke passed."

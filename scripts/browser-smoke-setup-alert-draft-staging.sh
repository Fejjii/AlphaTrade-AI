#!/usr/bin/env bash
# Record-only browser smoke for staging setup alert → paper draft flow (Slice 78).
# Creates a paper validation draft with explicit confirmation — no orders, Telegram,
# execution, exchange calls, scans, or automation.
#
# Usage:
#   STAGING_BOOTSTRAP_PASSWORD='...' ./scripts/browser-smoke-setup-alert-draft-staging.sh
#
# Optional overrides:
#   PLAYWRIGHT_BASE_URL=https://alpha-trade-ai-eight.vercel.app
#   PLAYWRIGHT_API_URL=https://alphatrade-api-staging.onrender.com
#   STAGING_BOOTSTRAP_EMAIL=seed-bootstrap-1782212606@example.com
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/frontend"

export PLAYWRIGHT_SKIP_WEBSERVER=1
export PLAYWRIGHT_STAGING_DRAFT_SMOKE=1
export PLAYWRIGHT_BASE_URL="${PLAYWRIGHT_BASE_URL:-https://alpha-trade-ai-eight.vercel.app}"
export PLAYWRIGHT_API_URL="${PLAYWRIGHT_API_URL:-https://alphatrade-api-staging.onrender.com}"
export STAGING_BOOTSTRAP_EMAIL="${STAGING_BOOTSTRAP_EMAIL:-seed-bootstrap-1782212606@example.com}"

if [[ -z "${STAGING_BOOTSTRAP_PASSWORD:-}" ]]; then
  cat >&2 <<'EOF'
STAGING_BOOTSTRAP_PASSWORD required for setup alert draft browser smoke (not printed).

Example:
  STAGING_BOOTSTRAP_PASSWORD='...' ./scripts/browser-smoke-setup-alert-draft-staging.sh
EOF
  exit 1
fi

export STAGING_DEMO_EMAIL="${STAGING_DEMO_EMAIL:-$STAGING_BOOTSTRAP_EMAIL}"
export STAGING_DEMO_PASSWORD="${STAGING_DEMO_PASSWORD:-$STAGING_BOOTSTRAP_PASSWORD}"

echo "Browser smoke — ${PLAYWRIGHT_BASE_URL}/alerts/review → paper draft (record only)"
npx playwright test e2e/setup-alert-draft-staging.spec.ts --project=chromium
echo "Setup alert draft browser smoke passed."

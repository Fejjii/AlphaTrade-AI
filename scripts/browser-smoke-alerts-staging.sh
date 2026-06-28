#!/usr/bin/env bash
# Read-only browser smoke for staging /alerts (Slice 70).
# Does NOT click "Send to Telegram" — no Telegram messages sent.
#
# Usage:
#   STAGING_DEMO_PASSWORD='...' ./scripts/browser-smoke-alerts-staging.sh
#
# Optional overrides:
#   PLAYWRIGHT_BASE_URL=https://alpha-trade-ai-eight.vercel.app
#   PLAYWRIGHT_API_URL=https://alphatrade-api-staging.onrender.com
#   STAGING_DEMO_EMAIL=demo@alphatrade.ai
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/frontend"

export PLAYWRIGHT_SKIP_WEBSERVER=1
export PLAYWRIGHT_STAGING_ALERTS_SMOKE=1
export PLAYWRIGHT_BASE_URL="${PLAYWRIGHT_BASE_URL:-https://alpha-trade-ai-eight.vercel.app}"
export PLAYWRIGHT_API_URL="${PLAYWRIGHT_API_URL:-https://alphatrade-api-staging.onrender.com}"
export STAGING_DEMO_EMAIL="${STAGING_DEMO_EMAIL:-demo@alphatrade.ai}"

if [[ -z "${STAGING_DEMO_PASSWORD:-}" ]]; then
  echo "STAGING_DEMO_PASSWORD required for staging browser smoke (not printed)." >&2
  exit 1
fi

echo "Browser smoke — ${PLAYWRIGHT_BASE_URL}/alerts (read-only, no Telegram send)"
npx playwright test e2e/alerts-staging-readonly.spec.ts --project=chromium
echo "Browser smoke passed."

#!/usr/bin/env bash
# Read-only browser smoke for staging /alerts/review (Slice 77).
# Does NOT send Telegram messages or place orders — review-only PATCH only.
#
# Usage:
#   STAGING_DEMO_PASSWORD='...' ./scripts/browser-smoke-setup-review-staging.sh
#
# Optional overrides:
#   PLAYWRIGHT_BASE_URL=https://alpha-trade-ai-eight.vercel.app
#   PLAYWRIGHT_API_URL=https://alphatrade-api-staging.onrender.com
#   STAGING_DEMO_EMAIL=demo@alphatrade.ai
#
# Password: set STAGING_DEMO_PASSWORD in env or gitignored docs/staging_ops.local.md
# (must match Render DEMO_SEED_PASSWORD). Never commit passwords.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/frontend"

export PLAYWRIGHT_SKIP_WEBSERVER=1
export PLAYWRIGHT_STAGING_REVIEW_SMOKE=1
export PLAYWRIGHT_BASE_URL="${PLAYWRIGHT_BASE_URL:-https://alpha-trade-ai-eight.vercel.app}"
export PLAYWRIGHT_API_URL="${PLAYWRIGHT_API_URL:-https://alphatrade-api-staging.onrender.com}"
export STAGING_DEMO_EMAIL="${STAGING_DEMO_EMAIL:-demo@alphatrade.ai}"

if [[ -z "${STAGING_DEMO_PASSWORD:-}" ]]; then
  cat >&2 <<'EOF'
STAGING_DEMO_PASSWORD required for setup review browser smoke (not printed).

Set from env or gitignored docs/staging_ops.local.md (Render DEMO_SEED_PASSWORD).
No safe fallback is configured for this wrapper — use demo login only.

Example:
  STAGING_DEMO_PASSWORD='...' ./scripts/browser-smoke-setup-review-staging.sh
EOF
  exit 1
fi

echo "Browser smoke — ${PLAYWRIGHT_BASE_URL}/alerts/review (review-only, no Telegram send)"
npx playwright test e2e/setup-alert-review-staging.spec.ts --project=chromium
echo "Setup review browser smoke passed."

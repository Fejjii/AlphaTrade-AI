#!/usr/bin/env bash
# Browser smoke for staging coaching (Slice 87).
#
# Usage:
#   STAGING_BOOTSTRAP_PASSWORD='...' ./scripts/browser-smoke-coaching-staging.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/frontend"

export PLAYWRIGHT_SKIP_WEBSERVER=1
export PLAYWRIGHT_STAGING_COACHING_SMOKE=1
export PLAYWRIGHT_BASE_URL="${PLAYWRIGHT_BASE_URL:-https://alpha-trade-ai-eight.vercel.app}"
export PLAYWRIGHT_API_URL="${PLAYWRIGHT_API_URL:-https://alphatrade-api-staging.onrender.com}"
export STAGING_BOOTSTRAP_EMAIL="${STAGING_BOOTSTRAP_EMAIL:-seed-bootstrap-1782212606@example.com}"

if [[ -z "${STAGING_BOOTSTRAP_PASSWORD:-}" ]]; then
  cat >&2 <<'EOF'
STAGING_BOOTSTRAP_PASSWORD required for coaching browser smoke (not printed).
EOF
  exit 1
fi

export STAGING_DEMO_EMAIL="${STAGING_DEMO_EMAIL:-$STAGING_BOOTSTRAP_EMAIL}"
export STAGING_DEMO_PASSWORD="${STAGING_DEMO_PASSWORD:-$STAGING_BOOTSTRAP_PASSWORD}"

echo "Browser smoke — ${PLAYWRIGHT_BASE_URL}/coaching"
npx playwright test e2e/coaching-staging.spec.ts --project=chromium
echo "Coaching browser smoke passed."

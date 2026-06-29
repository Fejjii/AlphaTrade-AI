#!/usr/bin/env bash
# Read-only browser smoke for staging paper validation session observations (Slice 83).
# Record-only observations and outcomes — no Telegram, orders, or exchange calls.
#
# Usage:
#   STAGING_BOOTSTRAP_PASSWORD='...' ./scripts/browser-smoke-session-observations-staging.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/frontend"

export PLAYWRIGHT_SKIP_WEBSERVER=1
export PLAYWRIGHT_STAGING_OBSERVATION_SMOKE=1
export PLAYWRIGHT_BASE_URL="${PLAYWRIGHT_BASE_URL:-https://alpha-trade-ai-eight.vercel.app}"
export PLAYWRIGHT_API_URL="${PLAYWRIGHT_API_URL:-https://alphatrade-api-staging.onrender.com}"
export STAGING_BOOTSTRAP_EMAIL="${STAGING_BOOTSTRAP_EMAIL:-seed-bootstrap-1782212606@example.com}"

if [[ -z "${STAGING_BOOTSTRAP_PASSWORD:-}" ]]; then
  cat >&2 <<'EOF'
STAGING_BOOTSTRAP_PASSWORD required for session observations browser smoke (not printed).

Example:
  STAGING_BOOTSTRAP_PASSWORD='...' ./scripts/browser-smoke-session-observations-staging.sh
EOF
  exit 1
fi

echo "Browser smoke — session observations (record only)"
npx playwright test e2e/session-observations-staging.spec.ts --project=chromium
echo "Session observations browser smoke passed."

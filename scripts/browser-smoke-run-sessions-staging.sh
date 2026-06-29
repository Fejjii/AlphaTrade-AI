#!/usr/bin/env bash
# Read-only browser smoke for staging paper validation run sessions (Slice 82).
# Record-only start from a planned run plan — no Telegram, orders, or exchange calls.
#
# Usage:
#   STAGING_BOOTSTRAP_PASSWORD='...' ./scripts/browser-smoke-run-sessions-staging.sh
#
# Optional overrides:
#   PLAYWRIGHT_BASE_URL=https://alpha-trade-ai-eight.vercel.app
#   PLAYWRIGHT_API_URL=https://alphatrade-api-staging.onrender.com
#   STAGING_BOOTSTRAP_EMAIL=seed-bootstrap-1782212606@example.com
#
# Password: gitignored docs/staging_ops.local.md (legacy bootstrap org). Never commit passwords.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/frontend"

export PLAYWRIGHT_SKIP_WEBSERVER=1
export PLAYWRIGHT_STAGING_RUN_SESSION_SMOKE=1
export PLAYWRIGHT_BASE_URL="${PLAYWRIGHT_BASE_URL:-https://alpha-trade-ai-eight.vercel.app}"
export PLAYWRIGHT_API_URL="${PLAYWRIGHT_API_URL:-https://alphatrade-api-staging.onrender.com}"
export STAGING_BOOTSTRAP_EMAIL="${STAGING_BOOTSTRAP_EMAIL:-seed-bootstrap-1782212606@example.com}"

if [[ -z "${STAGING_BOOTSTRAP_PASSWORD:-}" ]]; then
  cat >&2 <<'EOF'
STAGING_BOOTSTRAP_PASSWORD required for run session browser smoke (not printed).

Set from env or gitignored docs/staging_ops.local.md (legacy bootstrap org password).
No safe fallback is configured for this wrapper.

Example:
  STAGING_BOOTSTRAP_PASSWORD='...' ./scripts/browser-smoke-run-sessions-staging.sh
EOF
  exit 1
fi

echo "Browser smoke — ${PLAYWRIGHT_BASE_URL}/paper-validation/run-sessions (record only)"
npx playwright test e2e/run-sessions-staging.spec.ts --project=chromium
echo "Run sessions browser smoke passed."

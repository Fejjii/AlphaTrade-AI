#!/usr/bin/env bash
# Automated browser readiness validation for AT-041 PR4.
# Runs Playwright readiness + deep-link + paper-close + analytics hub specs.
# Does NOT claim staging or physical iPhone results.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}/frontend"

echo "=== AT-041 PR4 automated browser readiness ==="
echo "Scope: Playwright chromium specs (local/CI stack)"
echo "Pending (not run here): staging env walkthrough, physical iPhone Safari"
echo

npx playwright test \
  --project=chromium \
  e2e/readiness-validation.spec.ts \
  e2e/deep-link-contracts.spec.ts \
  e2e/paper-close.spec.ts \
  e2e/analytics-hub.spec.ts \
  "$@"

echo
echo "Automated browser readiness checks completed."
echo "MANUAL PENDING:"
echo "  - Staging: EXECUTION_MODE=paper, ENABLE_REAL_TRADING=false, PROVIDER_MODE=fallback"
echo "  - Physical iPhone Safari: daily loop, paper close, kill-switch, deep links, safe-area"

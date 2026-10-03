#!/usr/bin/env bash
# Repeatable offline/fake acceptance plus browser emulation. No staging writes.
set -euo pipefail
acceptance_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
acceptance_python="${ACCEPTANCE_PYTHON:-${acceptance_root}/backend/.venv/bin/python}"
acceptance_output="${ACCEPTANCE_OUTPUT_DIR:-/tmp/alphatrade-final-acceptance}"
mkdir -p "$acceptance_output"
export ENABLE_REAL_TRADING=false EXECUTION_MODE=paper EXCHANGE_MODE=paper_internal
export TELEGRAM_NETWORK_PERMITTED=false TELEGRAM_INTERACTION_ENABLED=false
export TELEGRAM_PAPER_ACTIVATION_ARMED=false TELEGRAM_INBOUND_MODE=off
export TELEGRAM_ALERTS_ENABLED=false AUTOMATIC_TELEGRAM_DELIVERY_ENABLED=false
export TELEGRAM_BOT_TOKEN= TELEGRAM_BOT_ID= TELEGRAM_CHAT_ID= TELEGRAM_WEBHOOK_SECRET=
export ENVIRONMENT=local PROVIDER_MODE=mock PERPETUAL_EVIDENCE_SOURCE=replay
export WATCHER_ORCHESTRATION_ENABLED=false WATCHER_PAPER_STAGING_ACTIVATION=false
export MARKET_WATCHER_ENABLED=false MARKET_WATCHER_BRIDGE_ENABLED=false
export GLOBAL_KILL_SWITCH_ACTIVE=false ALERT_DELIVERY_ENABLED=false
export PLAYWRIGHT_BASE_URL=http://localhost:3000 PLAYWRIGHT_API_URL=http://localhost:8000
export NEXT_PUBLIC_API_URL=http://localhost:8000
unset PLAYWRIGHT_SKIP_WEBSERVER
export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/alphatrade-uv-cache}"

: "${PHASE1_POSTGRES_URL:?Set PHASE1_POSTGRES_URL to a disposable local PostgreSQL database ending in _test}"
"$acceptance_python" - <<'PY'
import os
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
url = make_url(os.environ['PHASE1_POSTGRES_URL'])
assert url.host in {'localhost', '127.0.0.1', '::1'} and url.database.endswith('_test'), 'Disposable local _test database required'
with create_engine(url).connect() as connection:
    assert connection.execute(text('SELECT 1')).scalar() == 1
PY

cd "$acceptance_root/backend"
PYTHONPATH="src:${acceptance_root}/scripts/lib" "$acceptance_python" -m pytest \
  -p offline_acceptance tests/test_telegram*.py \
  tests/test_phase6_candidate_telegram_alerts.py tests/test_sfp_telegram_policy_integration.py \
  tests/test_deployment_safety.py tests/test_deployment_scripts.py tests/test_health.py \
  tests/test_final_product_acceptance.py --tb=short \
  --junitxml="$acceptance_output/backend.xml"
# Skips are blockers, including a PostgreSQL setup failure; never claim green.
"$acceptance_python" - "$acceptance_output/backend.xml" <<'PY'
import sys
import xml.etree.ElementTree as ET
root = ET.parse(sys.argv[1])
assert not list(root.iter('skipped')), 'Acceptance has skipped cases; resolve the prerequisites'
PY

cd "$acceptance_root/frontend"
npm test
npx playwright test --config playwright.acceptance.config.ts
npx playwright test e2e/final-workspaces.spec.ts e2e/watcher-monitoring.spec.ts --project chromium --workers 1
npx playwright test --config playwright.acceptance-mobile.config.ts
# Mandatory Safari-engine emulation. A missing binary/download grant is a blocker.
npx playwright test e2e/webkit-iphone-audit.spec.ts e2e/notification-settings-v2.spec.ts \
  --project iphone-15-pro --project iphone-15-pro-landscape --workers 1
npm run typecheck
npm run lint
npm run build
cd "$acceptance_root"
"$acceptance_python" scripts/final-product-acceptance.py \
  --capture-frontend-contract "$acceptance_output/frontend-contract.json"
echo "Automated acceptance passed. Physical-device and real Telegram checks remain NOT_TESTED."

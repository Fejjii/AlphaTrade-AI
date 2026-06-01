#!/usr/bin/env bash
# Verify trading safety invariants against a running API (staging smoke subset).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BASE_URL="${BASE_URL:-http://localhost:8000}"

echo "Verifying safety invariants at ${BASE_URL}..."

health_json="$(curl -fsS "${BASE_URL}/health")"
python3 - <<'PY' "$health_json"
import json
import sys

payload = json.loads(sys.argv[1])
assert payload.get("execution_mode") == "paper", payload
assert payload.get("real_trading_enabled") is False, payload
print("  execution_mode=paper, real_trading_enabled=false")
PY

providers_json="$(curl -fsS "${BASE_URL}/providers/status")"
python3 - <<'PY' "$providers_json"
import json
import sys

payload = json.loads(sys.argv[1])
providers = payload.get("providers") or []
exchange = next((p for p in providers if p.get("kind") == "exchange"), None)
assert exchange is not None, providers
assert exchange.get("is_mock") is True, exchange
detail = (exchange.get("detail") or "").lower()
assert "real trading disabled" in detail or "paper" in detail, exchange
print("  exchange provider is mock/paper-only")
PY

echo "Safety verification passed."

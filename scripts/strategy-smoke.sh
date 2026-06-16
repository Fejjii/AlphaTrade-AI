#!/usr/bin/env bash
# Optional lightweight smoke for Slice 34 strategy workflows (paper only).
# Requires a running backend (e.g. docker compose up). Skips gracefully on missing endpoints.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BASE_URL="${BASE_URL:-http://localhost:8000}"
BASE_URL="${BASE_URL%/}"

EMAIL="${SMOKE_EMAIL:-strategy-smoke-$(date +%s)@example.com}"
PASSWORD="${SMOKE_PASSWORD:-secure-password-1}"

auth_header() {
  printf 'Authorization: Bearer %s' "$TOKEN"
}

CARD_JSON='{
  "strategy_name": "Smoke HTF Pullback",
  "market_type": "crypto_perp",
  "asset_universe": ["BTCUSDT"],
  "timeframes": ["4h", "1h"],
  "entry_conditions": ["Pullback to EMA cluster"],
  "confirmation_conditions": ["RSI reset above 40"],
  "invalidation": ["Close below swing low"],
  "stop_loss": ["Below invalidation swing"],
  "take_profit_plan": ["TP1 at prior high"],
  "runner_plan": ["Trail after TP1"],
  "position_sizing": ["Max 1% account risk"],
  "add_rules": ["No adds until TP1"],
  "no_trade_rules": ["Skip if funding extreme"],
  "backtest_rules": ["Placeholder — not run"],
  "success_criteria": ["Win rate > 45% in paper"],
  "validation_status": "draft"
}'

echo "Strategy smoke — BASE_URL=${BASE_URL}"

echo "1/9 — /health (paper mode, real trading disabled)"
health_json="$(curl -fsS "${BASE_URL}/health")"
python3 - <<'PY' "$health_json"
import json, sys
p = json.loads(sys.argv[1])
assert p.get("execution_mode") == "paper", p
assert p.get("real_trading_enabled") is False, p
print("  OK")
PY

echo "2/9 — register or login"
register_json="$(curl -fsS -X POST "${BASE_URL}/auth/register" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"${EMAIL}\",\"password\":\"${PASSWORD}\",\"organization_name\":\"Strategy Smoke Org $(date +%s)\"}")"
TOKEN="$(python3 - <<'PY' "$register_json"
import json, sys
print(json.loads(sys.argv[1])["tokens"]["access_token"])
PY
)"

echo "3/9 — create strategy"
strategy_json="$(curl -fsS -X POST "${BASE_URL}/strategies" \
  -H "$(auth_header)" -H 'Content-Type: application/json' \
  -d "{\"name\":\"Smoke HTF Pullback\",\"setup_type\":\"htf_trend_pullback\",\"card\":${CARD_JSON}}")"
STRATEGY_ID="$(python3 - <<'PY' "$strategy_json"
import json, sys
print(json.loads(sys.argv[1])["id"])
PY
)"
echo "  OK: strategy_id=${STRATEGY_ID}"

echo "4/9 — create strategy version"
curl -fsS -X POST "${BASE_URL}/strategies/${STRATEGY_ID}/versions" \
  -H "$(auth_header)" -H 'Content-Type: application/json' \
  -d "{\"card\":${CARD_JSON}}" >/dev/null
echo "  OK"

echo "5/9 — create manual level"
level_json="$(curl -fsS -X POST "${BASE_URL}/manual-levels" \
  -H "$(auth_header)" -H 'Content-Type: application/json' \
  -d '{
    "symbol": "BTCUSDT",
    "exchange": "mock",
    "level_type": "support",
    "price": "60000"
  }')"
LEVEL_ID="$(python3 - <<'PY' "$level_json"
import json, sys
print(json.loads(sys.argv[1])["id"])
PY
)"
echo "  OK: level_id=${LEVEL_ID}"

echo "6/9 — pre-trade analysis"
curl -fsS -X POST "${BASE_URL}/pretrade/analyze" \
  -H "$(auth_header)" -H 'Content-Type: application/json' \
  -d "{
    \"symbol\": \"BTCUSDT\",
    \"exchange\": \"binance\",
    \"direction\": \"long\",
    \"strategy_id\": \"${STRATEGY_ID}\",
    \"manual_level_ids\": [\"${LEVEL_ID}\"],
    \"account_size\": 10000,
    \"max_risk_per_trade\": 1.0
  }" >/dev/null
echo "  OK"

echo "7/9 — position size + loss acceptance"
size_json="$(curl -fsS -X POST "${BASE_URL}/risk/size" \
  -H "$(auth_header)" -H 'Content-Type: application/json' \
  -d '{
    "entry_price": 62000,
    "invalidation_level": 61000,
    "account_balance": 10000,
    "max_risk_percent": 1.0,
    "direction": "long"
  }')"
curl -fsS -X POST "${BASE_URL}/risk/loss-acceptance" \
  -H "$(auth_header)" -H 'Content-Type: application/json' \
  -d "$(python3 - <<'PY' "$size_json"
import json, sys
planned = json.loads(sys.argv[1])["planned_loss_amount"]
print(json.dumps({"planned_loss_amount": planned, "accepted": True}))
PY
)" >/dev/null
echo "  OK"

echo "8/9 — backtest v1 + paper validation metrics"
backtest_json="$(curl -fsS -X POST "${BASE_URL}/strategies/${STRATEGY_ID}/backtests" \
  -H "$(auth_header)" -H 'Content-Type: application/json' \
  -d '{"assumptions":{"symbol":"BTCUSDT","timeframe":"15m","initial_capital":"10000","fees_bps":10,"slippage_bps":5,"risk_per_trade_pct":1}}')"
python3 - <<'PY' "$backtest_json"
import json, sys
p = json.loads(sys.argv[1])
status = (p.get("status") or "").lower()
assert status in {"completed", "failed"}, p
result = p.get("result") or {}
rec = result.get("recommendation")
print(f"  OK: backtest status={p.get('status')} recommendation={rec}")
PY
curl -fsS -X POST "${BASE_URL}/strategies/${STRATEGY_ID}/paper-validation/start" \
  -H "$(auth_header)" >/dev/null
echo "  OK: paper validation started"

echo "9/9 — confirm real trading remains disabled"
providers_json="$(curl -fsS -H "$(auth_header)" "${BASE_URL}/providers/status")"
python3 - <<'PY' "$providers_json" "$health_json"
import json, sys
payload = json.loads(sys.argv[1])
health = json.loads(sys.argv[2])
providers = payload.get("providers", payload)
assert health.get("real_trading_enabled") is False
exchange = next((p for p in providers if p.get("kind") == "exchange"), None)
if exchange:
    detail = (exchange.get("detail") or "").lower()
    assert exchange.get("is_mock") or "paper" in detail or "disabled" in detail, exchange
print("  OK: exchange provider paper-only / mock")
PY

echo "Strategy smoke passed (paper only)."

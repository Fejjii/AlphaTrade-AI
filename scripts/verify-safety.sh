#!/usr/bin/env bash
# Verify trading and billing safety invariants against a running API.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BASE_URL="${BASE_URL:-http://localhost:8000}"
BASE_URL="${BASE_URL%/}"

if [[ "$BASE_URL" == *"<"* ]]; then
  echo "Replace placeholder in BASE_URL (see docs/deployment_command_pack.md)." >&2
  exit 1
fi

echo "Verifying safety invariants at ${BASE_URL}..."

health_json=""
if ! health_json="$(curl -fsS "${BASE_URL}/health" 2>&1)"; then
  echo "FAIL: cannot reach ${BASE_URL}/health" >&2
  echo "  Is the backend running? For staging: export BASE_URL=https://your-api.onrender.com" >&2
  echo "  curl error: ${health_json}" >&2
  exit 1
fi

python3 - <<'PY' "$health_json"
import json
import sys

payload = json.loads(sys.argv[1])
mode = payload.get("execution_mode")
real = payload.get("real_trading_enabled")
env = payload.get("environment", "")
if mode != "paper":
    print(f"FAIL: execution_mode={mode!r} (expected 'paper')", file=sys.stderr)
    sys.exit(1)
if real is not False:
    print(f"FAIL: real_trading_enabled={real!r} (expected false)", file=sys.stderr)
    sys.exit(1)
exchange_mode = payload.get("exchange_mode")
if exchange_mode not in (None, "paper_internal", "paper_exchange_demo"):
    print(f"FAIL: exchange_mode={exchange_mode!r}", file=sys.stderr)
    sys.exit(1)
always_false = (
    "market_watcher_enabled",
    "market_watcher_bridge_enabled",
    "telegram_alerts_enabled",
    "automatic_telegram_delivery_enabled",
)
for flag in always_false:
    if flag in payload and payload.get(flag) is not False:
        print(f"FAIL: {flag}={payload.get(flag)!r} (expected false)", file=sys.stderr)
        sys.exit(1)
controlled = (
    env != "production"
    and mode == "paper"
    and real is False
    and payload.get("perpetual_evidence_source") == "binance_usdm"
    and payload.get("watcher_orchestration_enabled") is True
    and payload.get("watcher_paper_staging_activation") is True
    and payload.get("telegram_interaction_enabled") is True
    and payload.get("telegram_paper_activation_armed") is True
    and payload.get("telegram_inbound_mode") in ("polling", "webhook")
    and payload.get("telegram_alerts_enabled") is not True
    and payload.get("automatic_telegram_delivery_enabled") is not True
)
if not controlled:
    for flag in ("telegram_interaction_enabled", "telegram_paper_activation_armed"):
        if flag in payload and payload.get(flag) is not False:
            print(f"FAIL: {flag}={payload.get(flag)!r} (expected false)", file=sys.stderr)
            sys.exit(1)
    if "telegram_inbound_mode" in payload and payload.get("telegram_inbound_mode") not in (
        None,
        "off",
    ):
        print(
            f"FAIL: telegram_inbound_mode={payload.get('telegram_inbound_mode')!r}",
            file=sys.stderr,
        )
        sys.exit(1)
    if payload.get("telegram_network_permitted") is True:
        print("FAIL: telegram_network_permitted=true without the paper package", file=sys.stderr)
        sys.exit(1)
source = payload.get("perpetual_evidence_source")
activation = payload.get("perpetual_evidence_activation")
if source is not None and source not in ("replay", "binance_usdm"):
    print(f"FAIL: perpetual_evidence_source={source!r}", file=sys.stderr)
    sys.exit(1)
if activation is not None and activation not in ("inactive", "active"):
    print(f"FAIL: perpetual_evidence_activation={activation!r}", file=sys.stderr)
    sys.exit(1)
if source == "binance_usdm" and activation not in (None, "active"):
    print(f"FAIL: live source activation={activation!r}", file=sys.stderr)
    sys.exit(1)
if payload.get("live_quote_freshness_seconds") not in (None, 10):
    print("FAIL: live_quote_freshness_seconds is not 10", file=sys.stderr)
    sys.exit(1)
if payload.get("spot_fallback_permitted") not in (None, False):
    print("FAIL: spot_fallback_permitted is not false", file=sys.stderr)
    sys.exit(1)
if payload.get("exchange_credentials_used_for_market_evidence") not in (None, False):
    print("FAIL: market evidence reported credentials", file=sys.stderr)
    sys.exit(1)
orchestration = bool(payload.get("watcher_orchestration_enabled"))
armed = bool(payload.get("watcher_paper_staging_activation"))
if "watcher_orchestration_enabled" in payload and orchestration != armed:
    print(
        "FAIL: watcher paper activation pair "
        f"orchestration={orchestration} armed={armed}",
        file=sys.stderr,
    )
    sys.exit(1)
if orchestration and env == "production":
    print("FAIL: production watcher is forbidden", file=sys.stderr)
    sys.exit(1)
print(
    f"  health: execution_mode=paper, real_trading_enabled=false, "
    f"environment={env}, exchange_mode={exchange_mode or 'unset'}, "
    f"perpetual_evidence_source={source or 'unset'}, "
    f"activation={activation or 'unset'}"
)
PY

providers_json=""
if ! providers_json="$(curl -fsS "${BASE_URL}/providers/status" 2>&1)"; then
  echo "FAIL: cannot reach ${BASE_URL}/providers/status" >&2
  exit 1
fi

python3 - <<'PY' "$providers_json"
import json
import sys

payload = json.loads(sys.argv[1])
providers = payload.get("providers") or []
exchange = next((p for p in providers if p.get("kind") == "exchange"), None)
if exchange is None:
    print("FAIL: no exchange provider in /providers/status", file=sys.stderr)
    sys.exit(1)

name = exchange.get("name") or ""
detail = (exchange.get("detail") or "").lower()
is_mock = exchange.get("is_mock") is True

if is_mock:
    if "real trading disabled" not in detail and "paper" not in detail:
        print(
            f"FAIL: exchange detail missing paper-only wording: {exchange.get('detail')}",
            file=sys.stderr,
        )
        sys.exit(1)
    print("  exchange: mock/paper-only")
elif name == "blofin-demo-account":
    if exchange.get("health") != "healthy":
        print(f"FAIL: BloFin demo account unhealthy: {exchange}", file=sys.stderr)
        sys.exit(1)
    if "read-only" not in detail and "withdrawal" not in detail:
        print(
            f"FAIL: BloFin demo detail missing read-only wording: {exchange.get('detail')}",
            file=sys.stderr,
        )
        sys.exit(1)
    print("  exchange: blofin-demo-account (read-only, paper_exchange_demo)")
else:
    print(f"FAIL: unexpected exchange provider: {exchange}", file=sys.stderr)
    sys.exit(1)

billing = next((p for p in providers if p.get("kind") == "billing"), None)
if billing is not None:
    name = (billing.get("name") or "").lower()
    is_mock = billing.get("is_mock") is True
    if "stripe" in name and not is_mock and "mock" not in name:
        print(f"FAIL: billing looks live: {billing}", file=sys.stderr)
        sys.exit(1)
    print(f"  billing: {billing.get('name')} (staging expects mock/disabled — BILLING_ENABLED=false)")
PY

echo "Safety verification passed."

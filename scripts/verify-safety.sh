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
print(f"  health: execution_mode=paper, real_trading_enabled=false, environment={env}")
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

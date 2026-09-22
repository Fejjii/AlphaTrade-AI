#!/usr/bin/env bash
# In-process paper Telegram activation smoke. No Telegram network I/O.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/backend"

exec uv run pytest tests/test_telegram_paper_activation.py tests/test_health.py -q --tb=short

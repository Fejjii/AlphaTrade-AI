#!/usr/bin/env bash
# Paper Telegram activation preflight. Does not arm, send, or edit environment.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/backend"

exec env PYTHONPATH=src uv run python -m app.telegram_activation preflight --expect-disabled

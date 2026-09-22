#!/usr/bin/env bash
# Print the paper Telegram rollback checklist. Does not edit env or deploy.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/backend"

exec env PYTHONPATH=src uv run python -m app.telegram_activation rollback "$@"

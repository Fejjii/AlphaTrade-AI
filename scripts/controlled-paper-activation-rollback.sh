#!/usr/bin/env bash
# Print the controlled paper-package rollback. Does not edit env, deploy, or delete rows.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/backend"

exec env PYTHONPATH=src uv run python -m app.controlled_activation "$@"

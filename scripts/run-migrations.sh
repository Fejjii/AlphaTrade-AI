#!/usr/bin/env bash
# Apply Alembic migrations (local uv or container release command).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/backend"

REVISION="${REVISION:-head}"

echo "Running Alembic upgrade ${REVISION}..."
uv run alembic upgrade "${REVISION}"
echo "Migrations complete."

#!/usr/bin/env bash
# Rotate the staging bootstrap operator password in managed Postgres.
# Never prints passwords. Requires DATABASE_URL (e.g. from gitignored .env.staging).
#
# Interactive:
#   ENV_FILE=.env.staging ./scripts/reset-staging-bootstrap-password.sh
#
# Non-interactive (operator supplies new password via env):
#   STAGING_BOOTSTRAP_PASSWORD_NEW='...' ENV_FILE=.env.staging \\
#     ./scripts/reset-staging-bootstrap-password.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/backend"

ENV_FILE="${ENV_FILE:-}"
if [[ -n "$ENV_FILE" ]]; then
  if [[ ! -f "$ENV_FILE" ]]; then
    if [[ -f "$ROOT_DIR/$ENV_FILE" ]]; then
      ENV_FILE="$ROOT_DIR/$ENV_FILE"
    else
      echo "ENV_FILE not found: $ENV_FILE" >&2
      exit 1
    fi
  fi
  DATABASE_URL="$(
    python3 - <<'PY' "$ENV_FILE"
import sys
from pathlib import Path

path = Path(sys.argv[1])
for line in path.read_text().splitlines():
    s = line.strip()
    if not s or s.startswith("#") or "=" not in s:
        continue
    key, _, val = s.partition("=")
    if key.strip() == "DATABASE_URL":
        print(val.strip().strip('"').strip("'"))
        break
PY
  )"
  export DATABASE_URL
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
  cat >&2 <<'EOF'
DATABASE_URL is required (managed Postgres external URL with sslmode=require).

Example:
  ENV_FILE=.env.staging ./scripts/reset-staging-bootstrap-password.sh
EOF
  exit 1
fi

PYTHONPATH=src uv run python scripts/reset_staging_bootstrap_password.py "$@"

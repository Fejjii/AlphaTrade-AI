#!/usr/bin/env bash
# Validate backend environment variables for deployment (local, staging, production).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/backend"

ENV_FILE="${ENV_FILE:-}"
if [[ -n "$ENV_FILE" ]]; then
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "ENV_FILE not found: $ENV_FILE" >&2
    exit 1
  fi
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

echo "Checking backend deployment environment (ENVIRONMENT=${ENVIRONMENT:-local})..."
PYTHONPATH=src uv run python - <<'PY'
from __future__ import annotations

import sys

from app.core.config import Settings, get_settings
from app.core.deployment_safety import deployment_posture, validate_deployment_settings

get_settings.cache_clear()

try:
    settings = Settings()
    validate_deployment_settings(settings)
except Exception as exc:
    print(f"FAIL: {exc}", file=sys.stderr)
    sys.exit(1)

posture = deployment_posture(settings)
print("OK: environment configuration valid")
for key, value in sorted(posture.items()):
    print(f"  {key}={value}")
PY

#!/usr/bin/env bash
# Validate backend environment variables for deployment (local, staging, production).
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
      echo "Tip: cp .env.staging.example .env.staging && fill values (gitignored)." >&2
      echo "     Or: cp docs/staging_deployment_worksheet.template.md docs/staging_deployment_worksheet.local.md" >&2
      exit 1
    fi
  fi
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
else
  echo "Note: ENV_FILE not set — validating current shell environment only." >&2
  echo "      For staging prep: ENV_FILE=.env.staging $0" >&2
fi

echo "Checking backend deployment environment (ENVIRONMENT=${ENVIRONMENT:-local})..."
if ! PYTHONPATH=src uv run python - <<'PY'
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
    print("Hints:", file=sys.stderr)
    print("  - JWT_SECRET: openssl rand -base64 32", file=sys.stderr)
    print("  - CORS_ORIGINS: exact https:// Vercel URL, no trailing slash", file=sys.stderr)
    print("  - DATABASE_URL: managed Postgres (Render adds postgres:// — OK)", file=sys.stderr)
    print("  - Staging QDRANT_URL: hosted HTTPS or empty for in-memory fallback", file=sys.stderr)
    sys.exit(1)

posture = deployment_posture(settings)
print("OK: environment configuration valid")
for key, value in sorted(posture.items()):
    print(f"  {key}={value}")

failed = False
if settings.environment.value in ("staging", "production"):
    required = {
        "execution_mode": ("paper", settings.execution_mode.value),
        "enable_real_trading": (False, settings.enable_real_trading),
        "billing_enabled": (False, settings.billing_enabled),
    }
    print("Staging/production safety checks:")
    for name, (expected, actual) in required.items():
        if actual == expected:
            print(f"  [OK] {name}={actual}")
        else:
            print(f"  [FAIL] {name}={actual} (required {expected})", file=sys.stderr)
            failed = True
    print(f"  provider_mode={settings.provider_mode} (staging recommended: fallback)")
    if settings.environment.value == "staging" and settings.auth_cookie_samesite != "none":
        print(
            "  [WARN] AUTH_COOKIE_SAMESITE is not 'none' — cross-domain Vercel+Render needs 'none'",
            file=sys.stderr,
        )
if failed:
    sys.exit(1)
PY
then
  echo "check-env failed." >&2
  exit 1
fi

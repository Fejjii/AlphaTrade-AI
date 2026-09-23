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
    print("  - Staging QDRANT_URL: hosted HTTPS Qdrant is required (AT-013 fail-closed)", file=sys.stderr)
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
        "market_watcher_enabled": (False, settings.market_watcher_enabled),
        "market_watcher_bridge_enabled": (False, settings.market_watcher_bridge_enabled),
        "telegram_alerts_enabled": (False, settings.telegram_alerts_enabled),
        "automatic_telegram_delivery_enabled": (False, settings.automatic_telegram_delivery_enabled),
    }
    from app.controlled_activation.profile import controlled_telegram_projection

    if not controlled_telegram_projection(settings):
        required["telegram_interaction_enabled"] = (
            False,
            settings.telegram_interaction_enabled,
        )
    print("Staging/production safety checks:")
    for name, (expected, actual) in required.items():
        if actual == expected:
            print(f"  [OK] {name}={actual}")
        else:
            print(f"  [FAIL] {name}={actual} (required {expected})", file=sys.stderr)
            failed = True
    # Deployment safety already rejects an unpaired Watcher flag and replay
    # evidence while the paper arm is set. Do not require the arm to be false
    # after that check: a cleared staging paper pair is the controlled path.
    print(
        "  watcher_orchestration_enabled="
        f"{settings.watcher_orchestration_enabled} "
        "watcher_paper_staging_activation="
        f"{settings.watcher_paper_staging_activation}"
    )
    print(f"  provider_mode={settings.provider_mode} (staging recommended: fallback)")
    from app.market_activation.profile import perpetual_evidence_health

    evidence = perpetual_evidence_health(settings)
    print(
        "  perpetual_evidence_source="
        f"{evidence['perpetual_evidence_source']} "
        f"activation={evidence['perpetual_evidence_activation']} "
        f"freshness_seconds={evidence['live_quote_freshness_seconds']} "
        "credentials_used=false spot_fallback=false"
    )
    print(
        f"  openai_configured={bool(settings.openai_api_key.strip())} "
        f"qdrant_api_key_configured={bool(settings.qdrant_api_key.strip())} "
        f"embeddings_model={settings.embeddings_model} "
        f"embeddings_dimensions={settings.embeddings_dimensions}"
    )
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

#!/usr/bin/env bash
# Reingest playbook / knowledge fixtures after Qdrant collection recreate.
#
# Staging (recommended):
#   ACCESS_TOKEN=... BASE_URL=https://<staging-api> ./scripts/reingest-knowledge-base.sh --api
#
# Local DB + providers:
#   ORGANIZATION_ID=... ENV_FILE=.env ./scripts/reingest-knowledge-base.sh --local
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/backend"

ENV_FILE="${ENV_FILE:-}"
if [[ -n "$ENV_FILE" ]]; then
  if [[ ! -f "$ENV_FILE" && -f "$ROOT_DIR/$ENV_FILE" ]]; then
    ENV_FILE="$ROOT_DIR/$ENV_FILE"
  fi
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "ENV_FILE not found: $ENV_FILE" >&2
    exit 1
  fi
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 --api | --local [extra args...]" >&2
  exit 2
fi

echo "Reingesting AlphaTrade knowledge fixtures..."
PYTHONPATH=src uv run python scripts/reingest_knowledge_base.py "$@"

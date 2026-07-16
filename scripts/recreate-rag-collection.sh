#!/usr/bin/env bash
# Recreate ONLY alphatrade_knowledge in Qdrant with configured embedding dimensions.
# Does not touch trading, workers, Telegram, or other collections.
#
# Usage:
#   ./scripts/recreate-rag-collection.sh --dry-run
#   ./scripts/recreate-rag-collection.sh --i-understand-this-deletes-vectors
#
# Optional: ENV_FILE=.env.staging ./scripts/recreate-rag-collection.sh ...
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

echo "Recreating AlphaTrade RAG collection (paper-only operator tool)..."
PYTHONPATH=src uv run python scripts/recreate_rag_collection.py "$@"

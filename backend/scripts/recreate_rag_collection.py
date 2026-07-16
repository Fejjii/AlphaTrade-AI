#!/usr/bin/env python3
"""Recreate only the AlphaTrade knowledge Qdrant collection.

Safety:
- Does not touch trading, orders, proposals, workers, or Telegram.
- Deletes/recreates ONLY ``alphatrade_knowledge``.
- Requires an explicit confirmation flag.
- Never prints secret values.

Usage (from backend/):
  uv run python scripts/recreate_rag_collection.py --i-understand-this-deletes-vectors
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
SRC = BACKEND_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from app.core.config import Settings, get_settings  # noqa: E402
from app.providers.embedding_dimensions import resolve_embeddings_dimensions  # noqa: E402
from app.providers.factory import resolve_providers, should_use_qdrant  # noqa: E402
from app.providers.qdrant import QdrantVectorStore  # noqa: E402
from app.services.rag_service import RAG_COLLECTION  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recreate alphatrade_knowledge with the configured embedding dimensions."
    )
    parser.add_argument(
        "--i-understand-this-deletes-vectors",
        action="store_true",
        help="Required confirmation that existing vectors in alphatrade_knowledge will be deleted.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned action without deleting or creating collections.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if not args.i_understand_this_deletes_vectors and not args.dry_run:
        print(
            "Refusing to run without --i-understand-this-deletes-vectors (or use --dry-run).",
            file=sys.stderr,
        )
        return 2

    get_settings.cache_clear()
    settings = Settings()
    dimensions = resolve_embeddings_dimensions(settings)

    print("AlphaTrade RAG collection recreate")
    print(f"  collection={RAG_COLLECTION}")
    print(f"  provider_mode={settings.provider_mode}")
    print(f"  embeddings_model={settings.embeddings_model}")
    print(f"  embeddings_dimensions={dimensions}")
    print(f"  openai_configured={bool(settings.openai_api_key.strip())}")
    print(f"  qdrant_configured={bool(settings.qdrant_url.strip())}")
    print(f"  qdrant_api_key_configured={bool(settings.qdrant_api_key.strip())}")
    print(
        f"  execution_mode={settings.execution_mode.value} "
        f"real_trading={settings.real_trading_enabled}"
    )

    if settings.real_trading_enabled or settings.execution_mode.value != "paper":
        print("Refusing: trading posture is not paper-only.", file=sys.stderr)
        return 3

    if not should_use_qdrant(settings):
        print(
            "Refusing: Qdrant is not active (set QDRANT_URL and PROVIDER_MODE=fallback|live).",
            file=sys.stderr,
        )
        return 4

    resolved = resolve_providers(settings)
    store = resolved.vector_store
    if not isinstance(store, QdrantVectorStore):
        print("Refusing: resolved vector store is not Qdrant.", file=sys.stderr)
        return 5
    if not store.using_qdrant:
        print("Refusing: Qdrant is not connected (check URL/API key).", file=sys.stderr)
        return 6

    existing = store.collection_vector_size(RAG_COLLECTION)
    print(f"  existing_collection_dims={existing}")

    if args.dry_run:
        print("DRY RUN: would delete and recreate collection; no changes made.")
        return 0

    store.recreate_collection(RAG_COLLECTION, vector_size=dimensions)
    after = store.collection_vector_size(RAG_COLLECTION)
    print(f"OK: recreated {RAG_COLLECTION} at {after}-d")
    print("Next: reingest playbook/knowledge via scripts/reingest-knowledge-base.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

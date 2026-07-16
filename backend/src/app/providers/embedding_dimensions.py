"""Embedding dimension resolution for mock and OpenAI providers.

Keeps mock (tests/offline) and live OpenAI vectors aligned with the Qdrant
collection size so fallback embeddings never write incompatible dimensions.
"""

from __future__ import annotations

from app.core.config import Settings

MOCK_EMBEDDINGS_DIMENSIONS = 384

# Native defaults when EMBEDDINGS_DIMENSIONS is unset and OpenAI is configured.
OPENAI_EMBEDDING_MODEL_DIMENSIONS: dict[str, int] = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}

_DEFAULT_OPENAI_DIMENSIONS = 1536


def model_supports_dimensions_param(model: str) -> bool:
    """True when the OpenAI embeddings API accepts a ``dimensions`` field."""
    return model.strip().lower().startswith("text-embedding-3-")


def resolve_embeddings_dimensions(settings: Settings) -> int:
    """Resolve the vector size used by embeddings and Qdrant.

    Priority:
    1. Explicit ``EMBEDDINGS_DIMENSIONS``
    2. OpenAI model native size when ``OPENAI_API_KEY`` is set
    3. Mock default (384)
    """
    if settings.embeddings_dimensions is not None:
        return int(settings.embeddings_dimensions)
    if settings.openai_api_key.strip():
        model = settings.embeddings_model.strip().lower()
        return OPENAI_EMBEDDING_MODEL_DIMENSIONS.get(model, _DEFAULT_OPENAI_DIMENSIONS)
    return MOCK_EMBEDDINGS_DIMENSIONS

"""Provider fail-closed policy for non-local environments (AT-013 / AT-015).

Local (and explicit ``PROVIDER_MODE=mock``) may use deterministic mocks and soft
fallbacks. Staging and production must never silently substitute mock LLM /
embeddings or in-memory vector backends when real providers are configured.
``PROVIDER_MODE=mock`` remains rejected in staging/production by deployment safety.
"""

from __future__ import annotations

from app.core.config import Environment, Settings


def provider_fail_closed(settings: Settings) -> bool:
    """True when silent mock/split-brain provider fallbacks are forbidden.

    Staging and production always fail closed. Local remains permissive so
    developers can run without OpenAI/Qdrant credentials.
    """
    return settings.environment in {Environment.STAGING, Environment.PRODUCTION}


def requires_configured_openai(settings: Settings) -> bool:
    """Staging/production require a non-empty OpenAI API key for LLM/embeddings."""
    return provider_fail_closed(settings)


def requires_authoritative_qdrant(settings: Settings) -> bool:
    """True when RAG must use connected Qdrant (no process-memory substitute).

    Staging/production always require authoritative Qdrant. Deployment safety
    already requires a non-localhost ``qdrant_url`` in those environments.
    """
    return provider_fail_closed(settings)

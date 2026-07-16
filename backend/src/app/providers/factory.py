"""Factory helpers to resolve live vs fallback providers from settings."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.providers.embedding_dimensions import resolve_embeddings_dimensions
from app.providers.embeddings import (
    EmbeddingsProvider,
    MockEmbeddingsProvider,
    OpenAIEmbeddingsProvider,
)
from app.providers.llm import LLMProvider, MockLLMProvider, OpenAILLMProvider
from app.providers.market_data import (
    BinancePublicMarketDataProvider,
    MarketDataProvider,
    MockMarketDataProvider,
)
from app.providers.qdrant import (
    InMemoryVectorStore,
    QdrantVectorStore,
    VectorStore,
    get_process_vector_store,
)


@dataclass(frozen=True)
class ResolvedProviders:
    llm: LLMProvider
    embeddings: EmbeddingsProvider
    vector_store: VectorStore
    fallback_vector_store: InMemoryVectorStore
    market_data: MarketDataProvider
    embeddings_dimensions: int


def resolve_providers(settings: Settings) -> ResolvedProviders:
    """Select real providers when credentials exist; always keep deterministic fallbacks."""
    dimensions = resolve_embeddings_dimensions(settings)
    mock_llm = MockLLMProvider()
    mock_embeddings = MockEmbeddingsProvider(dimensions=dimensions)
    fallback_store = get_process_vector_store()

    if settings.openai_api_key.strip():
        llm: LLMProvider = OpenAILLMProvider(
            api_key=settings.openai_api_key.strip(),
            base_url=settings.openai_base_url,
            model=settings.llm_model,
            fallback=mock_llm,
        )
        embeddings: EmbeddingsProvider = OpenAIEmbeddingsProvider(
            model=settings.embeddings_model,
            api_key=settings.openai_api_key.strip(),
            base_url=settings.openai_base_url,
            dimensions=dimensions,
            fallback=mock_embeddings,
        )
    else:
        llm = mock_llm
        embeddings = mock_embeddings

    if should_use_qdrant(settings):
        vector_store: VectorStore = QdrantVectorStore(
            settings.qdrant_url.strip(),
            api_key=settings.qdrant_api_key.strip() or None,
            fallback=fallback_store,
            vector_size=dimensions,
        )
    else:
        vector_store = fallback_store

    market_data = resolve_market_data_provider(settings)

    return ResolvedProviders(
        llm=llm,
        embeddings=embeddings,
        vector_store=vector_store,
        fallback_vector_store=fallback_store,
        market_data=market_data,
        embeddings_dimensions=dimensions,
    )


def resolve_market_data_provider(settings: Settings) -> MarketDataProvider:
    """Select live Binance public API or mock-only market data."""
    mock = MockMarketDataProvider()
    if settings.market_data_provider.strip().lower() == "mock":
        return mock
    if settings.provider_mode == "mock":
        return mock
    if not settings.market_data_enabled:
        return BinancePublicMarketDataProvider(enabled=False, fallback=mock)
    return BinancePublicMarketDataProvider(
        spot_base_url=settings.market_data_spot_base_url,
        futures_base_url=settings.market_data_futures_base_url,
        fallback=mock,
        timeout_seconds=settings.market_data_timeout_seconds,
        enabled=True,
    )


def should_use_qdrant(settings: Settings) -> bool:
    """True when Qdrant should be attempted (non-test runtime with URL configured)."""
    modes = {"live", "fallback", "auto"}
    return bool(settings.qdrant_url.strip()) and settings.provider_mode in modes

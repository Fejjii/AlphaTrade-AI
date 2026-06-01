"""Provider integration tests for Slice 18."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.agents.runtime import AgentRuntime
from app.core.config import Settings, get_settings
from app.providers.embeddings import MockEmbeddingsProvider, OpenAIEmbeddingsProvider
from app.providers.factory import resolve_providers
from app.providers.llm import LLMCompletionRequest, LLMMessage, MockLLMProvider
from app.providers.qdrant import (
    InMemoryVectorStore,
    QdrantVectorStore,
    VectorSearchFilters,
    reset_process_vector_store,
)
from app.providers.registry import build_default_registry
from app.services.agent_service import AgentInvokeContext, AgentService
from app.services.risk_service import RiskService
from app.services.strategy_service import StrategyService
from app.strategies.registry import build_default_registry as build_strategy_registry
from app.tools.registry import build_default_registry as build_tools


@pytest.fixture(autouse=True)
def _reset_vector_store() -> None:
    reset_process_vector_store()


def test_openai_llm_fallback_when_no_key() -> None:
    resolved = resolve_providers(Settings(openai_api_key="", log_json=False))
    assert isinstance(resolved.llm, MockLLMProvider)
    result = resolved.llm.complete(
        LLMCompletionRequest(
            messages=[LLMMessage(role="user", content="analyze btc")],
            model="gpt-4o-mini",
        )
    )
    assert result.fallback_used is True
    assert result.provider == "mock-llm"


def test_llm_provider_status_without_key(client: TestClient) -> None:
    response = client.get("/providers/status")
    llm = next(p for p in response.json()["providers"] if p["kind"] == "llm")
    assert llm["name"] == "mock-llm"
    assert llm["is_mock"] is True


def test_embeddings_fallback_when_no_key() -> None:
    resolved = resolve_providers(Settings(openai_api_key="", log_json=False))
    assert isinstance(resolved.embeddings, MockEmbeddingsProvider)
    result = resolved.embeddings.embed_with_metadata(["alpha", "beta"])
    assert len(result.vectors) == 2
    assert result.fallback_used is True


def test_openai_embeddings_status_without_key() -> None:
    provider = OpenAIEmbeddingsProvider(
        model="text-embedding-3-small",
        api_key="",
        base_url="https://api.openai.com/v1",
    )
    status = provider.status()
    assert status.using_fallback is True
    assert "mock-embeddings" in (status.detail or "")


def test_qdrant_fallback_when_unavailable() -> None:
    store = QdrantVectorStore("http://127.0.0.1:1", fallback=InMemoryVectorStore())
    status = store.status()
    assert status.using_fallback is True
    hits = store.search(
        "alphatrade_knowledge",
        [0.1] * 384,
        filters=VectorSearchFilters(),
        top_k=3,
    )
    assert hits == []


def test_rag_still_works_with_mock_embeddings() -> None:
    resolved = resolve_providers(Settings(openai_api_key="", log_json=False))
    vectors = resolved.embeddings.embed_with_metadata(["test chunk"])
    assert len(vectors.vectors[0]) == 384


def _agent_service() -> AgentService:
    settings = Settings(log_json=False)
    runtime = AgentRuntime(
        settings=settings,
        risk_service=RiskService(),
        strategy_service=StrategyService(registry=build_strategy_registry()),
        tool_registry=build_tools(settings),
    )
    return AgentService(runtime=runtime)


def test_agent_response_includes_analysis_schema() -> None:
    response = _agent_service().run(
        "Please analyze BTC pullback setup on 4h",
        AgentInvokeContext(
            request_id="analysis-schema-test",
            user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            organization_id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
        ),
        symbol="BTCUSDT",
        timeframe="4h",
    )
    assert response.analysis is not None
    assert response.analysis.summary
    assert response.analysis.stop_loss_or_no_trade_reason
    assert response.analysis.approval_status in {"pending", "not_required", "blocked"}
    assert response.analysis.market_data_quality == "mock"


def test_provider_status_shows_fallback_modes(client: TestClient) -> None:
    body = client.get("/providers/status").json()
    kinds = {p["kind"] for p in body["providers"]}
    assert {"llm", "embeddings", "vector", "exchange"}.issubset(kinds)
    exchange = next(p for p in body["providers"] if p["kind"] == "exchange")
    assert exchange["is_mock"] is True
    assert "real trading disabled" in (exchange.get("detail") or "").lower()


def test_usage_metadata_from_mock_llm_provider() -> None:
    response = _agent_service().run(
        "analyze eth setup",
        AgentInvokeContext(
            request_id="usage-meta-test",
            user_id=uuid.UUID("00000000-0000-0000-0000-000000000003"),
            organization_id=uuid.UUID("00000000-0000-0000-0000-000000000004"),
        ),
    )
    assert response.usage is not None
    assert response.usage.provider == "mock-llm"
    assert response.usage.input_tokens >= 1


def test_registry_with_openai_key_registers_openai_providers() -> None:
    get_settings.cache_clear()
    registry = build_default_registry(
        Settings(openai_api_key="test-key", log_json=False, provider_mode="mock")
    )
    names = {p.name for p in registry.all()}
    assert "openai-llm" in names
    assert "openai-embeddings" in names
    get_settings.cache_clear()

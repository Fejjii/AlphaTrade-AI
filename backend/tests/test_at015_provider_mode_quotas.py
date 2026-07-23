"""AT-015 — PROVIDER_MODE honor, narrative quota, search opacity."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents.nodes import narrative_enhancement
from app.agents.runtime import AgentRuntime
from app.agents.state_utils import dump_partial, state_to_dict
from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db.models import Membership, Organization, UsageEvent, User
from app.db.session import get_session
from app.main import create_app
from app.providers.embedding_dimensions import (
    MOCK_EMBEDDINGS_DIMENSIONS,
    resolve_embeddings_dimensions,
)
from app.providers.embeddings import MockEmbeddingsProvider
from app.providers.factory import resolve_providers
from app.providers.llm import MockLLMProvider
from app.providers.qdrant import reset_process_vector_store
from app.providers.registry import build_default_registry
from app.schemas.agent import AgentState, Intent
from app.schemas.analysis import TradingAnalysisDetail
from app.schemas.common import DocumentSourceType, MembershipRole, RiskSeverity
from app.schemas.rag import IngestDocumentRequest, RagQuery
from app.schemas.usage import OrganizationQuotaUpdate
from app.services.narrative_service import NarrativeService
from app.services.quota_service import QuotaService
from app.services.rag_service import build_rag_service
from app.services.risk_service import RiskService
from app.services.strategy_service import StrategyService
from app.strategies.registry import build_default_registry as build_strategy_registry
from app.tools.registry import build_default_registry as build_tools

_PASSWORD = "secure-password-1"

_STAGING_BASE = {
    "environment": "staging",
    "jwt_secret": "x" * 32,
    "database_url": "postgresql+psycopg://user:pass@db.example.com:5432/alphatrade",
    "redis_url": "redis://redis.example.com:6379/0",
    "qdrant_url": "https://qdrant.example.com",
    "openai_api_key": "sk-test-not-a-real-key",
    "cors_origins": "https://app.example.com",
    "auth_refresh_cookie_enabled": True,
    "auth_cookie_secure": True,
    "auth_cookie_samesite": "none",
    "enable_real_trading": False,
    "execution_mode": "paper",
    "provider_mode": "fallback",
    "rate_limit_use_redis": True,
    "rate_limit_allow_in_memory_fallback": False,
    "trusted_proxy_hops": 1,
    "debug": False,
    "log_json": False,
}


@pytest.fixture(autouse=True)
def _reset_vector_store() -> None:
    reset_process_vector_store()


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn: object, _record: object) -> None:
        cursor = dbapi_conn.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        org = Organization(name="AT015 Org")
        owner = User(email="owner@at015.test", hashed_password="hash")
        session.add_all([org, owner])
        session.flush()
        session.add(Membership(user_id=owner.id, organization_id=org.id, role=MembershipRole.OWNER))
        session.commit()
        session.info["org_id"] = org.id
        session.info["owner_id"] = owner.id
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def api_client(db_session: Session) -> Iterator[TestClient]:
    settings = Settings(
        execution_mode="paper",
        enable_real_trading=False,
        log_json=False,
        provider_mode="mock",
        openai_api_key="",
        qdrant_url="",
        rate_limit_use_redis=False,
        rate_limit_allow_in_memory_fallback=True,
    )
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_session] = lambda: db_session
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def _register(client: TestClient, email: str) -> str:
    response = client.post(
        "/auth/register",
        json={"email": email, "password": _PASSWORD, "organization_name": f"Org-{email}"},
    )
    assert response.status_code in (200, 201), response.text
    return response.json()["tokens"]["access_token"]


def _sample_analysis() -> TradingAnalysisDetail:
    return TradingAnalysisDetail.model_validate(
        {
            "summary": "Trade proposal for BTCUSDT.",
            "setup_type": "htf_trend_pullback",
            "evidence": ["RSI 55.0"],
            "risk_level": RiskSeverity.MEDIUM,
            "confidence": 0.72,
            "invalidation": "Close below stop.",
            "stop_loss_or_no_trade_reason": "Stop loss at 58000.",
            "approval_status": "pending",
            "next_decision_point": "Submit for approval.",
            "paper_mode_disclaimer": "Paper mode only.",
            "market_data_quality": "mock",
        }
    )


def _agent_graph_state(agent: AgentState) -> dict:
    state = state_to_dict(agent)
    state["analysis_detail"] = dump_partial(_sample_analysis())
    state["final_answer"] = "deterministic answer"
    return state


class TestProviderModeHonor:
    def test_mock_mode_with_key_forces_mock_llm_and_embeddings(self) -> None:
        settings = Settings(
            openai_api_key="sk-test-should-not-call",
            log_json=False,
            provider_mode="mock",
            qdrant_url="",
        )
        resolved = resolve_providers(settings)
        assert isinstance(resolved.llm, MockLLMProvider)
        assert isinstance(resolved.embeddings, MockEmbeddingsProvider)
        assert resolved.embeddings.name == "mock-embeddings"
        assert resolved.llm.name == "mock-llm"
        assert resolved.embeddings_dimensions == MOCK_EMBEDDINGS_DIMENSIONS

    def test_mock_mode_registry_excludes_openai_providers(self) -> None:
        get_settings.cache_clear()
        registry = build_default_registry(
            Settings(openai_api_key="test-key", log_json=False, provider_mode="mock")
        )
        names = {p.name for p in registry.all()}
        assert "mock-llm" in names
        assert "mock-embeddings" in names
        assert "openai-llm" not in names
        assert "openai-embeddings" not in names
        get_settings.cache_clear()

    def test_fallback_mode_with_key_still_uses_openai(self) -> None:
        settings = Settings(
            openai_api_key="sk-test",
            log_json=False,
            provider_mode="fallback",
            qdrant_url="",
        )
        resolved = resolve_providers(settings)
        assert resolved.llm.name == "openai-llm"
        assert resolved.embeddings.name == "openai-embeddings"

    def test_mock_mode_dimensions_ignore_openai_key(self) -> None:
        settings = Settings(
            openai_api_key="sk-test",
            embeddings_model="text-embedding-3-large",
            log_json=False,
            provider_mode="mock",
        )
        assert resolve_embeddings_dimensions(settings) == MOCK_EMBEDDINGS_DIMENSIONS

    def test_staging_still_rejects_provider_mode_mock(self) -> None:
        with pytest.raises(ValidationError, match="provider_mode=mock"):
            Settings(**{**_STAGING_BASE, "provider_mode": "mock"})


class TestNarrativeQuota:
    def test_hard_block_skips_llm_and_uses_deterministic_fallback(
        self, db_session: Session
    ) -> None:
        org_id = db_session.info["org_id"]
        user_id = db_session.info["owner_id"]
        quota = QuotaService(db_session)
        quota.update_quota(
            org_id,
            OrganizationQuotaUpdate(
                limit_agent_narrative=0,
                hard_block_threshold=Decimal("0.00"),
            ),
        )

        settings = Settings(
            log_json=False,
            provider_mode="mock",
            narrative_llm_enabled=True,
            openai_api_key="",
        )
        llm = MagicMock(spec=MockLLMProvider)
        llm.name = "mock-llm"
        narrative = NarrativeService(llm_provider=llm, llm_model="gpt-4o-mini", enabled=True)
        runtime = AgentRuntime(
            settings=settings,
            risk_service=RiskService(),
            strategy_service=StrategyService(registry=build_strategy_registry()),
            tool_registry=build_tools(settings),
            llm_provider=llm,
            narrative_service=narrative,
            quota_service=quota,
            session=db_session,
        )

        agent = AgentState(
            request_id="at015-narr-quota",
            user_id=user_id,
            organization_id=org_id,
            message="Analyze BTC pullback",
            intent=Intent.PLAN_TRADE,
        )
        out = narrative_enhancement(_agent_graph_state(agent), runtime)
        llm.complete.assert_not_called()
        meta = out.get("narrative_metadata") or {}
        assert meta.get("fallback_used") is True
        assert meta.get("source") == "deterministic_fallback"
        assert meta.get("provider") == "quota"
        assert out.get("narrative_detail") is not None

    def test_narrative_quota_allows_llm_when_under_limit(self, db_session: Session) -> None:
        org_id = db_session.info["org_id"]
        user_id = db_session.info["owner_id"]
        quota = QuotaService(db_session)
        quota.update_quota(
            org_id,
            OrganizationQuotaUpdate(
                limit_agent_narrative=100,
                hard_block_threshold=Decimal("1.00"),
            ),
        )

        settings = Settings(
            log_json=False,
            provider_mode="mock",
            narrative_llm_enabled=True,
            openai_api_key="",
        )
        runtime = AgentRuntime(
            settings=settings,
            risk_service=RiskService(),
            strategy_service=StrategyService(registry=build_strategy_registry()),
            tool_registry=build_tools(settings),
            quota_service=quota,
            session=db_session,
        )
        assert runtime.narrative_service is not None

        agent = AgentState(
            request_id="at015-narr-ok",
            user_id=user_id,
            organization_id=org_id,
            message="Analyze ETH setup",
            intent=Intent.PLAN_TRADE,
        )
        out = narrative_enhancement(_agent_graph_state(agent), runtime)
        meta = out.get("narrative_metadata") or {}
        assert meta.get("provider") != "quota"


class TestSearchOpacity:
    def test_search_response_includes_fallback_and_degraded_flags(
        self, db_session: Session
    ) -> None:
        settings = Settings(log_json=False, provider_mode="mock", openai_api_key="")
        org_id = db_session.info["org_id"]
        user_id = db_session.info["owner_id"]
        rag = build_rag_service(settings, db_session)
        rag.ingest(
            IngestDocumentRequest(
                organization_id=org_id,
                user_id=user_id,
                source_type=DocumentSourceType.TRADING_PLAYBOOK,
                title="AT015 playbook",
                text="Human approval is required before any executable order.",
            )
        )
        result = rag.search(
            RagQuery(
                query="approval required before executable order",
                organization_id=org_id,
                user_id=user_id,
                top_k=3,
            )
        )
        assert isinstance(result.degraded, bool)
        assert isinstance(result.fallback_used, bool)
        assert result.vector_backend is not None
        # Local mock path uses in-memory vectors → fallback/degraded opacity flags.
        assert result.fallback_used is True or result.degraded is True

    def test_knowledge_search_api_returns_opacity_fields(self, api_client: TestClient) -> None:
        token = _register(api_client, "search-opacity@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        ingest = api_client.post(
            "/knowledge/ingest",
            headers=headers,
            json={
                "source_type": "trading_playbook",
                "title": "Opacity playbook",
                "text": "Paper mode only. Human approval required before executable orders.",
            },
        )
        assert ingest.status_code in (200, 201), ingest.text
        search = api_client.post(
            "/knowledge/search",
            headers=headers,
            json={"query": "human approval paper mode", "top_k": 3},
        )
        assert search.status_code == 200, search.text
        body = search.json()
        assert "degraded" in body
        assert "fallback_used" in body
        assert "vector_backend" in body
        assert body["fallback_used"] is True or body["degraded"] is True


class TestRegressionSafety:
    def test_paper_defaults_unchanged(self) -> None:
        settings = Settings(log_json=False)
        assert settings.execution_mode == "paper"
        assert settings.enable_real_trading is False

    def test_usage_events_not_written_when_narrative_quota_blocks(
        self, db_session: Session
    ) -> None:
        org_id = db_session.info["org_id"]
        user_id = db_session.info["owner_id"]
        quota = QuotaService(db_session)
        quota.update_quota(
            org_id,
            OrganizationQuotaUpdate(
                limit_agent_narrative=0,
                hard_block_threshold=Decimal("0.00"),
            ),
        )
        settings = Settings(log_json=False, provider_mode="mock", narrative_llm_enabled=True)
        llm = MagicMock(spec=MockLLMProvider)
        llm.name = "mock-llm"
        runtime = AgentRuntime(
            settings=settings,
            risk_service=RiskService(),
            strategy_service=StrategyService(registry=build_strategy_registry()),
            tool_registry=build_tools(settings),
            llm_provider=llm,
            narrative_service=NarrativeService(
                llm_provider=llm, llm_model="gpt-4o-mini", enabled=True
            ),
            quota_service=quota,
            session=db_session,
        )
        agent = AgentState(
            request_id="at015-no-usage",
            user_id=user_id,
            organization_id=org_id,
            message="Analyze SOL",
            intent=Intent.PLAN_TRADE,
        )
        narrative_enhancement(_agent_graph_state(agent), runtime)
        events = db_session.scalars(
            select(UsageEvent).where(UsageEvent.feature == "agent_narrative")
        ).all()
        assert events == []

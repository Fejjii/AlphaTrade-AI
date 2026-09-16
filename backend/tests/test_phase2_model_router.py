"""Phase 2 — ModelRouter, least privilege, fallback, and actual-call telemetry."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.errors import PersistencePolicyError, ServiceUnavailableError
from app.core.operation_policy import operation_scope
from app.core.persistence_firewall import install_persistence_firewall
from app.db.base import Base
from app.db.models import JournalTrade, ModelCallAttempt, Organization, UsageEvent, User
from app.providers.llm import LLMCompletionRequest, LLMCompletionResult, LLMMessage, MockLLMProvider
from app.repositories.base import SQLAlchemyRepository
from app.schemas.agent import Intent, IntentDecision, OperationClass, PrincipalRef, RequestedAction
from app.schemas.common import CostSource, JournalTradeSource, TradeDirection, UsageStatus
from app.schemas.model_routing import (
    ModelContextScope,
    ModelFailureCategory,
    ModelResourceType,
    ModelRetentionCategory,
    ModelRoutingPurpose,
    ModelRoutingTier,
    ModelTaskRequest,
)
from app.services.model_call_telemetry import ModelCallTelemetryService, resolve_model_call_cost
from app.services.model_router import (
    CrossTenantModelContextError,
    ModelRouter,
    ModelRoutingError,
)
from app.services.usage_service import UsageService

ORG_A = uuid.UUID("00000000-0000-0000-0000-00000000a001")
ORG_B = uuid.UUID("00000000-0000-0000-0000-00000000b001")
USER_A = uuid.UUID("00000000-0000-0000-0000-00000000a002")
USER_B = uuid.UUID("00000000-0000-0000-0000-00000000b002")


class _FailingLLM:
    name = "failing-llm"
    kind = MockLLMProvider().kind

    def __init__(self, *, error: Exception | None = None) -> None:
        self.calls: list[str] = []
        self._error = error or ServiceUnavailableError(
            "LLM provider is unavailable.",
            details={"reason": "openai_llm_unavailable"},
        )

    def complete(self, request: LLMCompletionRequest) -> LLMCompletionResult:
        self.calls.append(request.model)
        raise self._error

    def status(self) -> object:
        return None


class _SelectiveFailLLM:
    """Fails for Tier A model, succeeds for Tier B model."""

    name = "selective-llm"
    kind = MockLLMProvider().kind

    def __init__(self, *, fail_model: str) -> None:
        self.fail_model = fail_model
        self.calls: list[str] = []

    def complete(self, request: LLMCompletionRequest) -> LLMCompletionResult:
        self.calls.append(request.model)
        if request.model == self.fail_model:
            raise ServiceUnavailableError(
                "LLM provider is unavailable.",
                details={"reason": "openai_llm_timeout"},
            )
        return LLMCompletionResult(
            content='{"summary":"ok"}',
            model=request.model,
            provider=self.name,
            input_tokens=12,
            output_tokens=4,
            latency_ms=7.5,
            fallback_used=False,
            parsed_json={"summary": "ok"},
        )


class _JournalRepo(SQLAlchemyRepository[JournalTrade]):
    model = JournalTrade


@pytest.fixture
def session() -> Iterator[Session]:
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
    install_persistence_firewall()
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as sess:
        sess.add_all(
            [
                Organization(id=ORG_A, name="Org A"),
                Organization(id=ORG_B, name="Org B"),
                User(id=USER_A, email="a@example.com", hashed_password="x"),
                User(id=USER_B, email="b@example.com", hashed_password="x"),
            ]
        )
        sess.commit()
        yield sess
    Base.metadata.drop_all(engine)
    engine.dispose()


def _scope(
    purpose: ModelRoutingPurpose,
    *,
    org: uuid.UUID | None = ORG_A,
    user: uuid.UUID | None = USER_A,
) -> ModelContextScope:
    return ModelContextScope(
        organization_id=org,
        user_id=user,
        purpose=purpose,
        resource_type=ModelResourceType.CONVERSATION,
        retention_category=ModelRetentionCategory.STANDARD,
    )


def _request(
    purpose: ModelRoutingPurpose,
    *,
    override: str | None = None,
    org: uuid.UUID | None = ORG_A,
    caller_org: uuid.UUID | None = ORG_A,
    user: uuid.UUID | None = USER_A,
    caller_user: uuid.UUID | None = USER_A,
    correlation_id: str = "corr-1",
) -> ModelTaskRequest:
    return ModelTaskRequest(
        purpose=purpose,
        context=_scope(purpose, org=org, user=user),
        correlation_id=correlation_id,
        caller_organization_id=caller_org,
        caller_user_id=caller_user,
        model_override=override,
    )


def _messages() -> list[LLMMessage]:
    return [LLMMessage(role="user", content="Summarize the frozen setup facts.")]


def _router(
    provider: object | None = None,
    *,
    fail_closed: bool = False,
    telemetry: ModelCallTelemetryService | None = None,
) -> ModelRouter:
    return ModelRouter(
        provider or MockLLMProvider(),  # type: ignore[arg-type]
        tier_a_model="gpt-4o",
        tier_b_model="gpt-4o-mini",
        fail_closed=fail_closed,
        telemetry=telemetry,
    )


def test_routing_by_purpose_assigns_tiers() -> None:
    router = _router()
    a = router.decide(_request(ModelRoutingPurpose.STRATEGY_REVIEW))
    b = router.decide(_request(ModelRoutingPurpose.INTENT_CLASSIFICATION))
    assert a.selected_tier is ModelRoutingTier.TIER_A
    assert a.selected_model == "gpt-4o"
    assert b.selected_tier is ModelRoutingTier.TIER_B
    assert b.selected_model == "gpt-4o-mini"
    assert a.policy_version == "model-router/v1"
    assert a.token_budget == 4096
    assert b.token_budget == 1024


def test_tier_a_selection() -> None:
    router = _router()
    decision = router.decide(_request(ModelRoutingPurpose.EVIDENCE_EXPLANATION))
    assert decision.selected_tier is ModelRoutingTier.TIER_A
    assert decision.selected_model == "gpt-4o"
    assert decision.retention_category is ModelRetentionCategory.AUDIT_REQUIRED


def test_tier_b_selection() -> None:
    router = _router()
    decision = router.decide(_request(ModelRoutingPurpose.NARRATIVE_SYNTHESIS))
    assert decision.selected_tier is ModelRoutingTier.TIER_B
    assert decision.selected_model == "gpt-4o-mini"


def test_unauthorized_model_override_rejected() -> None:
    router = _router()
    with pytest.raises(ModelRoutingError, match="Unauthorized model override"):
        router.decide(_request(ModelRoutingPurpose.INTENT_CLASSIFICATION, override="gpt-4o"))


def test_tier_a_may_request_explicit_lower_fallback() -> None:
    router = _router()
    decision = router.decide(_request(ModelRoutingPurpose.STRATEGY_REVIEW, override="gpt-4o-mini"))
    assert decision.selected_model == "gpt-4o-mini"
    assert decision.selected_tier is ModelRoutingTier.TIER_A


def test_provider_fallback_uses_lower_model() -> None:
    provider = _SelectiveFailLLM(fail_model="gpt-4o")
    router = _router(provider)
    result = router.complete(_request(ModelRoutingPurpose.STRATEGY_REVIEW), _messages())
    assert result.fallback_used is True
    assert result.unavailable is False
    assert result.mutation_allowed is False
    assert provider.calls == ["gpt-4o", "gpt-4o-mini"]
    assert result.resolved_model == "gpt-4o-mini"
    assert any(not row.success for row in result.attempts)
    assert any(row.success for row in result.attempts)


def test_fail_closed_mode_returns_unavailable() -> None:
    provider = _FailingLLM()
    router = _router(provider, fail_closed=True)
    result = router.complete(_request(ModelRoutingPurpose.NARRATIVE_SYNTHESIS), _messages())
    assert result.unavailable is True
    assert result.mutation_allowed is False
    assert result.failure_category is ModelFailureCategory.PROVIDER_UNAVAILABLE
    assert provider.calls == ["gpt-4o-mini"]
    assert result.deterministic_facts is not None
    assert result.deterministic_facts["mutation_allowed"] is False


def test_open_fallback_returns_deterministic_facts() -> None:
    provider = _FailingLLM()
    router = _router(provider, fail_closed=False)
    result = router.complete(_request(ModelRoutingPurpose.GENERAL_AGENT_SYNTHESIS), _messages())
    assert result.unavailable is False
    assert result.fallback_used is True
    assert result.deterministic_facts is not None
    assert result.deterministic_facts["tier_c_authority"] is True
    assert result.mutation_allowed is False
    assert result.content == ""


def test_telemetry_success(session: Session) -> None:
    usage = UsageService(session)
    telemetry = ModelCallTelemetryService(session, usage)
    router = _router(telemetry=telemetry)
    result = router.complete(
        _request(ModelRoutingPurpose.NARRATIVE_SYNTHESIS, correlation_id="corr-ok"),
        _messages(),
    )
    assert result.unavailable is False
    rows = list(session.scalars(select(ModelCallAttempt)).all())
    assert len(rows) == 1
    row = rows[0]
    assert row.success is True
    assert row.purpose.value == "narrative_synthesis"
    assert row.tier.value == "tier_b"
    assert row.requested_model == "gpt-4o-mini"
    assert row.resolved_model
    assert row.input_tokens >= 1
    assert row.latency_ms is not None
    assert row.correlation_id == "corr-ok"
    assert row.organization_id == ORG_A
    assert row.mutation_allowed is False
    usage_rows = list(session.scalars(select(UsageEvent)).all())
    assert len(usage_rows) == 1
    assert usage_rows[0].feature == "agent_narrative"
    assert usage_rows[0].input_tokens == row.input_tokens


def test_telemetry_failure(session: Session) -> None:
    usage = UsageService(session)
    telemetry = ModelCallTelemetryService(session, usage)
    router = _router(_FailingLLM(), fail_closed=True, telemetry=telemetry)
    result = router.complete(_request(ModelRoutingPurpose.LESSON_SYNTHESIS), _messages())
    assert result.unavailable is True
    rows = list(session.scalars(select(ModelCallAttempt)).all())
    assert len(rows) == 1
    assert rows[0].success is False
    assert rows[0].failure_category.value == "provider_unavailable"
    assert rows[0].status is UsageStatus.FAILURE
    usage_rows = list(session.scalars(select(UsageEvent)).all())
    assert len(usage_rows) == 1
    assert usage_rows[0].status is UsageStatus.FAILURE


def test_token_counts_and_latency() -> None:
    provider = _SelectiveFailLLM(fail_model="never")
    result = _router(provider).complete(
        _request(ModelRoutingPurpose.GENERAL_AGENT_SYNTHESIS),
        _messages(),
    )
    assert result.input_tokens == 12
    assert result.output_tokens == 4
    assert result.total_latency_ms == 7.5
    assert result.attempts[0].latency_ms == 7.5


def test_cost_unavailable_for_unknown_model() -> None:
    cost = resolve_model_call_cost(model="mystery-model", input_tokens=100, output_tokens=20)
    assert cost.cost_source is CostSource.UNAVAILABLE
    assert cost.estimated_cost == Decimal("0")


def test_cost_static_estimated_for_known_model() -> None:
    cost = resolve_model_call_cost(model="gpt-4o-mini", input_tokens=1_000_000, output_tokens=0)
    assert cost.cost_source is CostSource.STATIC_ESTIMATED
    assert cost.estimated_cost > Decimal("0")


def test_cross_tenant_context_rejected() -> None:
    router = _router()
    with pytest.raises(CrossTenantModelContextError):
        router.decide(
            _request(
                ModelRoutingPurpose.STRATEGY_REVIEW,
                org=ORG_B,
                caller_org=ORG_A,
            )
        )


def test_fallback_cannot_mutate_domain_state(session: Session) -> None:
    before = session.scalar(select(JournalTrade).limit(1))
    assert before is None
    result = _router(_FailingLLM(), fail_closed=False).complete(
        _request(ModelRoutingPurpose.NARRATIVE_SYNTHESIS),
        _messages(),
    )
    assert result.mutation_allowed is False
    assert session.scalars(select(JournalTrade)).all() == []


def test_readonly_remains_readonly_during_model_failure(session: Session) -> None:
    usage = UsageService(session)
    telemetry = ModelCallTelemetryService(session, usage)
    router = _router(_FailingLLM(), fail_closed=True, telemetry=telemetry)
    decision = IntentDecision(
        intent=Intent.MARKET_ANALYSIS,
        operation_class=OperationClass.READ_ONLY,
        organization_id=ORG_A,
        principal=PrincipalRef(user_id=USER_A),
        requested_action=RequestedAction.NONE,
    )
    with operation_scope(decision):
        result = router.complete(_request(ModelRoutingPurpose.NARRATIVE_SYNTHESIS), _messages())
        assert result.unavailable is True
        attempts = list(session.scalars(select(ModelCallAttempt)).all())
        assert len(attempts) == 1
        with pytest.raises(PersistencePolicyError, match="READ_ONLY"):
            _JournalRepo(session).add(
                JournalTrade(
                    organization_id=ORG_A,
                    user_id=USER_A,
                    source=JournalTradeSource.MANUAL,
                    symbol="BTCUSDT",
                    timeframe="15m",
                    direction=TradeDirection.SHORT,
                )
            )


def test_secret_in_prompt_rejected() -> None:
    router = _router()
    with pytest.raises(ModelRoutingError, match="secrets"):
        router.complete(
            _request(ModelRoutingPurpose.GENERAL_AGENT_SYNTHESIS),
            [
                LLMMessage(
                    role="user",
                    content="Use OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz1234",
                )
            ],
        )


def test_usage_tracking_does_not_call_llm() -> None:
    from app.agents.nodes import usage_tracking
    from app.agents.runtime import AgentRuntime
    from app.core.config import Settings
    from app.services.risk_service import RiskService
    from app.services.strategy_service import StrategyService
    from app.strategies.registry import build_default_registry
    from app.tools.registry import build_default_registry as build_tools

    provider = _FailingLLM()
    settings = Settings(log_json=False, provider_mode="mock")
    runtime = AgentRuntime(
        settings=settings,
        risk_service=RiskService(),
        strategy_service=StrategyService(registry=build_default_registry()),
        tool_registry=build_tools(settings),
        llm_provider=provider,  # type: ignore[arg-type]
    )
    state = {
        "message": "analyze eth trend",
        "request_id": "no-meter-call",
        "organization_id": str(ORG_A),
        "user_id": str(USER_A),
        "tool_outputs": [],
        "tool_calls": [],
        "audit_events": [],
        "citations": [],
    }
    out = usage_tracking(state, runtime)
    assert provider.calls == []
    meta = out["usage_metadata"]
    assert meta["feature"] == "agent_chat"
    assert meta["input_tokens"] > 0
    assert meta["cost_source"] == CostSource.UNAVAILABLE.value

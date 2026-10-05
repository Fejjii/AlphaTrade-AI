"""Brain Agent Daily Review reads: grounding, scope, routing and side-effect boundaries."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event, select

from app.api.routes import interactive_agent as agent_routes
from app.core.auth import get_current_tenant
from app.core.config import get_settings
from app.core.errors import ForbiddenError, ValidationAppError, register_exception_handlers
from app.daily_review.contracts import ReviewTopic
from app.daily_review.reader import DailyReviewService
from app.daily_review.service import daily_window
from app.db.models import (
    ConversationMessage,
    JournalTrade,
    LessonCandidate,
    Membership,
    TradeJournal,
)
from app.db.session import get_session
from app.interactive_agent.action_registry import resolve_action, route_action
from app.interactive_agent.actions import ActionRequest
from app.interactive_agent.classify import classify_turn
from app.interactive_agent.contracts import AgentCapability, AgentTurnRequest, TurnOperation
from app.interactive_agent.service import InteractiveAgentService
from app.paper_evaluation.contracts import DataQualityClass, PaperEvaluationStage
from app.persistence.paper_evaluation_postgres import PostgresPaperEvaluationStore
from app.schemas.common import (
    JournalTradeSource,
    JournalTradeStatus,
    MembershipRole,
    TradeDirection,
)
from app.security.tenant import TenantContext
from app.signal_fusion.enums import ActionEligibilityState, SetupAssessmentState
from tests.support.paper_evaluation import make_observation
from tests.test_interactive_agent_foundation import ORG_A, ORG_B, USER_A, USER_A2, USER_B

pytest_plugins = ("tests.test_interactive_agent_foundation",)
AT = datetime(2026, 10, 1, 22, 30, tzinfo=UTC)
RECORDED = AT - timedelta(hours=12)
DAY = date(2026, 10, 1)


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    monkeypatch.setattr(
        "app.interactive_agent.service.datetime", SimpleNamespace(now=lambda _zone: AT)
    )


def turn(session, settings, message="What happened today?", action=None, **scope):
    return InteractiveAgentService(session, settings=settings).handle_turn(
        AgentTurnRequest(message=message, action=action),
        organization_id=scope.get("organization_id", ORG_A),
        user_id=scope.get("user_id", USER_A),
    )


@pytest.mark.parametrize(
    "message",
    [
        "What is the current BTCUSDT Nested setup state on 15m? Explain the long and short "
        "states using stored evidence, its timestamp and any missing data. Do not create "
        "or approve any trade.",
        "Show the latest SFP setup status and missing evidence.",
    ],
)
def test_current_setup_gaps_do_not_route_to_daily_review(message):
    assert route_action(AgentTurnRequest(message=message)) is None
    assert classify_turn(message).capability is AgentCapability.STRATEGY_BRAIN


@pytest.mark.parametrize(
    ("message", "focus"),
    [
        ("What happened today?", "summary"),
        ("What setups did we see?", "setups"),
        ("What trades did we take?", "trades"),
        ("Why were trades blocked?", "blocked"),
        ("How did I perform today?", "performance"),
        ("What mistakes did I make?", "mistakes"),
        ("What lessons should I review?", "lessons"),
        ("What evidence is missing?", "evidence"),
        ("What should I review tomorrow?", "tomorrow"),
    ],
)
def test_natural_questions_are_reads_without_other_sources(agent_db, monkeypatch, message, focus):
    def forbidden(*args, **kwargs):
        pytest.fail("Daily Review must not use retrieval, market data or a narrative model")

    monkeypatch.setattr("app.interactive_agent.service.retrieve_knowledge", forbidden)
    monkeypatch.setattr("app.interactive_agent.service.retrieve_strategies", forbidden)
    monkeypatch.setattr("app.interactive_agent.service.gather_reads", forbidden)
    factory, settings = agent_db
    with factory() as session:
        result = InteractiveAgentService(
            session, settings=settings, responder=SimpleNamespace(compose=forbidden)
        ).handle_turn(AgentTurnRequest(message=message), organization_id=ORG_A, user_id=USER_A)
        assert route_action(AgentTurnRequest(message=message)).arguments["focus"] == focus
        assert result.capability is AgentCapability.DAILY_REVIEW
        assert result.operation is TurnOperation.READ
        assert result.proposals == result.knowledge == result.strategies == result.connections == []
        assert result.daily_review.window.day == DAY
        assert result.daily_review.daily_pnl == ()
        assert not result.execution_attempted and not result.authority_mutated
        assert not result.daily_review.telegram_delivery
        assert all(
            f"{label}:" in result.reply
            for label in ("Facts", "User observations", "System inference", "Research suggestions")
        )
        assert "absence of records does not prove inactivity" in result.reply
        assert len(result.reply) <= 4000


def seed(session):
    for i, (org, user, source) in enumerate(
        [
            (ORG_A, USER_A, JournalTradeSource.PAPER_EXECUTION),
            (ORG_A, USER_A2, JournalTradeSource.PAPER_EXECUTION),
            (ORG_B, USER_B, JournalTradeSource.PAPER_EXECUTION),
            (ORG_A, USER_A, JournalTradeSource.BACKTEST),
            (ORG_A, USER_A, JournalTradeSource.MANUAL),
        ],
        100,
    ):
        session.add(
            JournalTrade(
                id=UUID(int=i),
                organization_id=org,
                user_id=user,
                source=source,
                status=JournalTradeStatus.CLOSED,
                symbol="BTCUSDT",
                timeframe="1h",
                direction=TradeDirection.LONG,
                entry_time=RECORDED,
                exit_time=RECORDED,
                updated_at=RECORDED,
                net_pnl=Decimal("7") if i == 100 else Decimal("999"),
            )
        )
        session.add(
            TradeJournal(
                id=UUID(int=i + 100),
                organization_id=org,
                user_id=user,
                symbol="BTCUSDT",
                timeframe="1h",
                direction=TradeDirection.LONG,
                entry_rationale="Recorded plan",
                mistakes=[f"Mistake by {user}"],
                lessons=f"Lesson by {user}",
                updated_at=RECORDED,
                created_at=RECORDED,
            )
        )
        session.add(
            LessonCandidate(
                id=UUID(int=i + 200),
                organization_id=org,
                user_id=user,
                lesson_text=f"Candidate by {user}",
                mistake_type="discipline",
                created_at=RECORDED,
            )
        )
    store = PostgresPaperEvaluationStore(session)
    for org in (ORG_A, ORG_B):
        store.put(
            make_observation(
                organization_id=org,
                occurred_at=RECORDED,
                stage=PaperEvaluationStage.ELIGIBILITY,
                assessment_state=SetupAssessmentState.CONFIRMED_SETUP,
                eligibility_state=ActionEligibilityState.BLOCKED,
                reason_code="blocked_daily_loss",
                data_quality=DataQualityClass.STALE,
                narrative_explanation="Invented market event and guaranteed profit",
            )
        )
    session.commit()


def test_service_record_is_preserved_and_only_transcript_is_written(agent_db):
    factory, settings = agent_db
    with factory() as session:
        seed(session)
        expected = DailyReviewService(session).review(
            organization_id=ORG_A, user_id=USER_A, window=daily_window(DAY), generated_at=AT
        )
        statements = []

        def record(_conn, _cursor, statement, _parameters, _context, _many):
            statements.append(statement.lower())

        event.listen(session.bind, "before_cursor_execute", record)
        try:
            result = turn(session, settings)
        finally:
            event.remove(session.bind, "before_cursor_execute", record)
        assert result.daily_review == expected
        assert result.daily_review.daily_pnl[0].recorded_net_pnl == 7
        assert result.daily_review.daily_pnl[0].win_rate is None
        assert result.daily_review.daily_pnl[0].expectancy is None
        assert "win rate=None" in result.reply and "expectancy=None" in result.reply
        assert all(str(other) not in result.reply for other in (USER_A2, USER_B))
        assert "Invented market event" not in result.model_dump_json()
        assert result.daily_review.counts[ReviewTopic.BLOCKED] == 1
        assert result.daily_review.system_inference and result.daily_review.research_suggestions
        assert "blocked_daily_loss" in turn(session, settings, "Why were trades blocked?").reply
        assert str(UUID(int=100)) in result.reply
        private_sources = {
            s.record_id
            for section in (
                expected.facts,
                expected.user_observations,
                expected.system_inference,
                expected.research_suggestions,
            )
            for item in section
            for s in item.sources
            if s.record_type != "paper_evaluation_observations"
        }
        assert not private_sources.intersection(str(UUID(int=i)) for i in (101, 102, 301, 302))
        writes = [s for s in statements if s.startswith(("insert", "update", "delete"))]
        assert writes and all(
            "into conversations " in s
            or "into conversation_messages " in s
            or s.startswith("update conversations ")
            for s in writes
        )
        payload = session.get(ConversationMessage, result.assistant_message_id).payload
        assert payload["interactive_agent"]["daily_review"] == expected.model_dump(mode="json")


def test_focused_lessons_and_tomorrow_remain_review_suggestions(agent_db):
    factory, settings = agent_db
    with factory() as session:
        seed(session)
        result = turn(session, settings, "What should I review tomorrow?")
        assert result.daily_review.window.day == DAY
        assert "Tomorrow's review suggestions use this recorded day" in result.reply
        assert "review_lesson_candidate" in result.reply
        assert not result.proposals
        assert result.daily_review.daily_pnl[0].recorded_net_pnl == 7


def test_explicit_scope_timezone_relative_days_and_future_rejection(agent_db):
    factory, settings = agent_db
    with factory() as session:
        action = ActionRequest(name="daily_review.read", arguments={"timezone": "Europe/Berlin"})
        result = turn(session, settings, action=action)
        assert result.daily_review.window.day == date(2026, 10, 2)
        assert result.daily_review.window.start == datetime(2026, 10, 1, 22, tzinfo=UTC)
        yesterday = turn(session, settings, "What happened yesterday?")
        assert yesterday.daily_review.window.day == date(2026, 9, 30)
        explicit = turn(
            session,
            settings,
            action=ActionRequest(
                name="daily_review.read",
                arguments={"day": "2026-03-29", "timezone": "Europe/Berlin"},
            ),
        )
        assert explicit.daily_review.window.end - explicit.daily_review.window.start == timedelta(
            hours=23
        )
        with pytest.raises(ValidationAppError, match="current or past"):
            turn(
                session,
                settings,
                action=ActionRequest(name="daily_review.read", arguments={"day": "2026-10-02"}),
            )


@pytest.mark.parametrize(
    "arguments",
    [
        {"timezone": "Not/AZone"},
        {"day": "2026-02-30"},
        {"focus": "execute"},
        {"user_id": str(USER_B)},
        {"organization_id": str(ORG_B)},
        {"schedule": True},
        {"telegram_delivery": True},
    ],
)
def test_input_rejects_invalid_values_identity_and_delivery_overrides(arguments):
    with pytest.raises(ValidationAppError):
        resolve_action(ActionRequest(name="daily_review.read", arguments=arguments))


def test_permissions_and_live_refusal_take_precedence(agent_db):
    factory, settings = agent_db
    with factory() as session:
        membership = session.scalar(select(Membership).where(Membership.user_id == USER_A))
        membership.role = MembershipRole.VIEWER
        session.commit()
        assert turn(session, settings).daily_review is not None
        with pytest.raises(ForbiddenError):
            turn(session, settings, organization_id=ORG_B)
        result = turn(
            session,
            settings,
            "What happened today? Enable live trading",
            action=ActionRequest(name="daily_review.read"),
        )
        assert result.operation is TurnOperation.REFUSE and result.daily_review is None


def test_read_failures_propagate_without_fabricating_empty_review(agent_db, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("source unavailable")

    monkeypatch.setattr(DailyReviewService, "review", fail)
    factory, settings = agent_db
    with factory() as session, pytest.raises(RuntimeError, match="source unavailable"):
        turn(session, settings)


def test_large_review_discloses_omissions_and_keeps_full_sources(agent_db):
    factory, settings = agent_db
    with factory() as session:
        session.add(
            TradeJournal(
                organization_id=ORG_A,
                user_id=USER_A,
                symbol="BTCUSDT",
                timeframe="1h",
                direction=TradeDirection.LONG,
                entry_rationale="Plan",
                mistakes=[f"Mistake {i}: " + "x" * 200 for i in range(100)],
                created_at=RECORDED,
                updated_at=RECORDED,
            )
        )
        session.commit()
        result = turn(session, settings, "What mistakes did I make?")
        assert len(result.reply) <= 4000
        assert len(result.daily_review.user_observations) == 100
        assert "more entries in the attached daily_review record" in result.reply


@pytest.mark.parametrize("missing", [False, True])
def test_performance_uses_service_values_and_preserves_missing_measurements(agent_db, missing):
    factory, settings = agent_db
    with factory() as session:
        for i in range(10):
            session.add(
                JournalTrade(
                    organization_id=ORG_A,
                    user_id=USER_A,
                    source=JournalTradeSource.PAPER_EXECUTION,
                    status=JournalTradeStatus.CLOSED,
                    symbol="BTCUSDT",
                    timeframe="1h",
                    direction=TradeDirection.LONG,
                    entry_time=RECORDED,
                    exit_time=RECORDED,
                    updated_at=RECORDED,
                    net_pnl=None if missing and i == 0 else Decimal("2"),
                )
            )
        session.commit()
        result = turn(session, settings, "How did I perform today?")
        expected = DailyReviewService(session).review(
            organization_id=ORG_A, user_id=USER_A, window=daily_window(DAY), generated_at=AT
        )
        assert result.daily_review.daily_pnl == expected.daily_pnl
        assert len(result.daily_review.daily_pnl[0].sources) == 10
        assert f"recorded net PnL={18 if missing else 20}" in result.reply
        assert f"complete={not missing}" in result.reply
        assert f"missing={int(missing)}" in result.reply
        assert f"win rate={'None' if missing else '1'}" in result.reply
        assert f"expectancy={'None' if missing else '2'}" in result.reply
        assert "partial recorded sum" in result.reply
        assert "8 more sources in daily_review" in result.reply


def test_http_contract_catalog_and_review(agent_db):
    factory, settings = agent_db
    app = FastAPI()
    app.include_router(agent_routes.router)
    register_exception_handlers(app)
    with factory() as session:
        app.dependency_overrides[get_session] = lambda: session
        app.dependency_overrides[get_settings] = lambda: settings
        app.dependency_overrides[get_current_tenant] = lambda: TenantContext(
            user_id=USER_A,
            organization_id=ORG_A,
            email="agent-a@test.example",
            membership_role=MembershipRole.OWNER,
        )
        with TestClient(app) as client:
            catalog = client.get("/agent/capabilities").json()
            tool = next(a for a in catalog["actions"] if a["name"] == "daily_review.read")
            assert tool["behavior"] == "read" and not tool["explicit_confirmation_required"]
            response = client.post("/agent/turns", json={"message": "What happened today?"})
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["daily_review"]["window"]["day"] == "2026-10-01"
            assert body["daily_review"]["user_id"] == str(USER_A)
            assert body["operation"] == "read" and body["proposals"] == []


def test_ambiguous_periods_and_existing_actions():
    with pytest.raises(ValidationAppError):
        route_action(AgentTurnRequest(message="What mistakes did I make last week?"))
    with pytest.raises(ValidationAppError):
        route_action(AgentTurnRequest(message="What happened today and yesterday?"))
    with pytest.raises(ValidationAppError):
        route_action(AgentTurnRequest(message="What setups will we see tomorrow?"))
    request = AgentTurnRequest(
        message="What happened today?", action=ActionRequest(name="context.read")
    )
    assert route_action(request).name == "context.read"
    assert (
        route_action(AgentTurnRequest(message="Record a lesson: wait for the close")).name
        == "journal.record_lesson"
    )
    assert route_action(AgentTurnRequest(message="How is my overall performance?")) is None
    assert route_action(AgentTurnRequest(message="What trades should I take today?")) is None

"""Slice 37 — lesson review workflow, structured rules, post-exit runner analysis."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents.strategy_intent import classify_strategy_workflow
from app.core.config import Settings
from app.db.base import Base
from app.db.models import Membership, Organization, User
from app.db.session import get_session
from app.main import create_app
from app.schemas.agent import Intent
from app.schemas.common import (
    EntryTriggerType,
    ExitRuleType,
    MembershipRole,
    Timeframe,
    TradeDirection,
)
from app.schemas.structured_rules import EntryRuleBlock, ExitRuleBlock, StructuredRules
from app.security.passwords import hash_password
from app.services.lesson_candidate_service import LessonCandidateService
from app.services.runner_missed_profit_analyzer import (
    RunnerAnalysisInput,
    RunnerAndMissedProfitAnalyzer,
)
from app.services.strategy_testability_service import validate_structured_rules

ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000080")
USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000081")


@pytest.fixture
def slice37_client() -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
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
    settings = Settings(
        environment="local",
        log_json=False,
        execution_mode="paper",
        enable_real_trading=False,
        database_url="sqlite+pysqlite:///:memory:",
        jwt_secret="slice37-test-secret-key-min",
        rate_limit_use_redis=False,
        provider_mode="mock",
        market_data_provider="mock",
        journal_rag_sync_enabled=True,
    )
    with factory() as session:
        org = Organization(id=ORG_ID, name="Slice37 Org")
        user = User(
            id=USER_ID,
            email="slice37@test.example",
            hashed_password=hash_password("TestPassword123!", settings),
            email_verified=True,
        )
        session.add(org)
        session.add(user)
        session.flush()
        session.add(Membership(user_id=USER_ID, organization_id=ORG_ID, role=MembershipRole.OWNER))
        session.commit()

    app = create_app(settings=settings)

    def _override_session() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = _override_session
    with TestClient(app) as client:
        login = client.post(
            "/auth/login",
            json={"email": "slice37@test.example", "password": "TestPassword123!"},
        )
        assert login.status_code == 200
        token = login.json()["tokens"]["access_token"]
        client.headers.update({"Authorization": f"Bearer {token}"})
        yield client, factory
    app.dependency_overrides.clear()


def test_create_and_list_pending_lessons(
    slice37_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = slice37_client
    create = client.post(
        "/lessons/candidates",
        json={
            "source_type": "journal",
            "lesson_text": "I exited too early while structure still supported continuation.",
            "mistake_type": "early_exit",
            "severity": "medium",
            "confidence": "0.7",
        },
    )
    assert create.status_code == 200, create.text
    lesson_id = create.json()["id"]
    assert create.json()["status"] == "pending_review"

    pending = client.get("/lessons/candidates?status=pending_review")
    assert pending.status_code == 200
    assert any(item["id"] == lesson_id for item in pending.json()["items"])


def test_accept_and_reject_lesson(slice37_client: tuple[TestClient, sessionmaker[Session]]) -> None:
    client, session_factory = slice37_client
    create = client.post(
        "/lessons/candidates",
        json={
            "lesson_text": "Stop was moved after entry.",
            "mistake_type": "stop_violation",
            "severity": "high",
        },
    )
    lesson_id = create.json()["id"]

    reject = client.patch(
        f"/lessons/candidates/{lesson_id}/reject",
        json={"reviewer_notes": "Not applicable this week."},
    )
    assert reject.status_code == 200
    assert reject.json()["status"] == "rejected"

    accept = client.patch(
        f"/lessons/candidates/{lesson_id}/accept",
        json={"reviewer_notes": "Accept after review."},
    )
    assert accept.status_code == 200
    assert accept.json()["status"] == "accepted"

    with session_factory() as session:
        service = LessonCandidateService(session)
        text = service.prepare_memory_search_text(uuid.UUID(lesson_id))
        assert text is not None
        assert "accepted trading lesson" in text


def test_accepted_lessons_list(slice37_client: tuple[TestClient, sessionmaker[Session]]) -> None:
    client, _ = slice37_client
    client.post(
        "/lessons/candidates",
        json={"lesson_text": "Runner plan unclear.", "mistake_type": "early_exit"},
    )
    create2 = client.post(
        "/lessons/candidates",
        json={"lesson_text": "Accepted runner lesson.", "mistake_type": "early_exit"},
    )
    lid = create2.json()["id"]
    client.patch(f"/lessons/candidates/{lid}/accept", json={})

    accepted = client.get("/lessons/accepted?mistake_type=early_exit")
    assert accepted.status_code == 200
    assert accepted.json()["total"] >= 1


def test_structured_rule_validation_updates_score(
    slice37_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    rules = StructuredRules(
        primary_timeframe=Timeframe.H4,
        entry_rules=[EntryRuleBlock(trigger_type=EntryTriggerType.EMA_PULLBACK)],
        exit_rules=[
            ExitRuleBlock(rule_type=ExitRuleType.FIXED_STOP, value=Decimal("2")),
            ExitRuleBlock(rule_type=ExitRuleType.TP_MULTIPLE, r_multiple=Decimal("1")),
        ],
        no_trade_rules=[],
    )
    valid, errors, _ = validate_structured_rules(rules)
    assert valid
    assert not errors

    incomplete = StructuredRules(
        primary_timeframe=Timeframe.H4,
        entry_rules=[EntryRuleBlock(trigger_type=EntryTriggerType.RECLAIM)],
        exit_rules=[ExitRuleBlock(rule_type=ExitRuleType.TP_MULTIPLE, r_multiple=Decimal("1"))],
        no_trade_rules=[],
    )
    valid2, errors2, _ = validate_structured_rules(incomplete)
    assert not valid2
    assert errors2


def test_runner_analyzer_post_exit_candles() -> None:
    analyzer = RunnerAndMissedProfitAnalyzer()
    exit_time = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
    candles = [
        (exit_time, Decimal("100"), Decimal("105"), Decimal("99"), Decimal("104")),
        (exit_time, Decimal("104"), Decimal("112"), Decimal("103"), Decimal("111")),
    ]
    result = analyzer.analyze(
        RunnerAnalysisInput(
            entry_price=Decimal("95"),
            exit_price=Decimal("100"),
            exit_time=exit_time,
            direction=TradeDirection.LONG,
            tp_plan_prices=[Decimal("102"), Decimal("110"), Decimal("115")],
            runner_enabled=True,
            invalidation_price=Decimal("98"),
            candles_after_exit=candles,
        )
    )
    assert result.max_favorable_excursion_after_exit is not None
    assert result.early_exit_flag is True
    assert result.tp2_would_have_hit is True
    assert result.confidence.value == "high"


def test_runner_analyzer_missing_candles_limitation() -> None:
    analyzer = RunnerAndMissedProfitAnalyzer()
    result = analyzer.analyze(
        RunnerAnalysisInput(
            entry_price=Decimal("95"),
            exit_price=Decimal("100"),
            exit_time=datetime.now(UTC),
            direction=TradeDirection.LONG,
            tp_plan_prices=[Decimal("110")],
            runner_enabled=True,
        )
    )
    assert any("Post-exit candle data unavailable" in note for note in result.limitations)


def test_agent_lesson_intents() -> None:
    assert (
        classify_strategy_workflow("What lessons are pending review?")
        == Intent.LESSON_PENDING_QUERY
    )
    assert classify_strategy_workflow("Show my accepted lessons") == Intent.LESSON_ACCEPTED_QUERY
    assert classify_strategy_workflow("Accept this lesson") == Intent.LESSON_ACCEPT
    assert classify_strategy_workflow("Reject this lesson") == Intent.LESSON_REJECT
    assert (
        classify_strategy_workflow("Make this strategy more testable")
        == Intent.STRATEGY_TESTABILITY
    )
    assert (
        classify_strategy_workflow("Add a runner rule to this strategy") == Intent.ADD_RUNNER_RULE
    )


def test_no_live_trading_in_lesson_create(
    slice37_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = slice37_client
    settings: Settings = client.app.state.settings  # type: ignore[attr-defined]
    assert settings.real_trading_enabled is False
    resp = client.post(
        "/lessons/candidates",
        json={"lesson_text": "Paper only lesson.", "mistake_type": "discipline"},
    )
    assert resp.status_code == 200

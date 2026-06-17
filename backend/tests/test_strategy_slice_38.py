"""Slice 38 — lesson-driven versioning, paper eligibility gates, RAG retrieval."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
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
    PaperEligibilityStatus,
    Timeframe,
)
from app.schemas.structured_rules import EntryRuleBlock, ExitRuleBlock, StructuredRules
from app.security.passwords import hash_password
from app.services.lesson_candidate_service import LessonCandidateService

ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000090")
USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000091")


def _sample_card(**overrides: object) -> dict:
    base = {
        "strategy_name": "Slice38 Test",
        "market_type": "crypto_perp",
        "asset_universe": ["BTCUSDT"],
        "timeframes": ["4h"],
        "entry_conditions": ["Pullback to EMA cluster"],
        "confirmation_conditions": ["RSI reset above 40"],
        "invalidation": ["Close below swing low"],
        "stop_loss": ["2% below entry"],
        "take_profit_plan": ["TP1 at 1R"],
        "runner_plan": ["Trail after TP1"],
        "position_sizing": ["Max 1% account risk"],
        "add_rules": [],
        "no_trade_rules": ["Skip if funding extreme"],
        "backtest_rules": [],
        "success_criteria": ["Win rate > 45%"],
        "validation_status": "draft",
    }
    base.update(overrides)
    return base


def _structured_rules() -> dict:
    return StructuredRules(
        primary_timeframe=Timeframe.H4,
        entry_rules=[EntryRuleBlock(trigger_type=EntryTriggerType.EMA_PULLBACK)],
        exit_rules=[
            ExitRuleBlock(rule_type=ExitRuleType.FIXED_STOP, value=Decimal("2")),
            ExitRuleBlock(rule_type=ExitRuleType.TP_MULTIPLE, r_multiple=Decimal("1")),
        ],
        no_trade_rules=[],
    ).model_dump(mode="json")


@pytest.fixture
def slice38_client() -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
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
        jwt_secret="slice38-test-secret-key-min",
        rate_limit_use_redis=False,
        provider_mode="mock",
        market_data_provider="mock",
        journal_rag_sync_enabled=True,
    )
    with factory() as session:
        org = Organization(id=ORG_ID, name="Slice38 Org")
        user = User(
            id=USER_ID,
            email="slice38@test.example",
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
            json={"email": "slice38@test.example", "password": "TestPassword123!"},
        )
        assert login.status_code == 200
        token = login.json()["tokens"]["access_token"]
        client.headers.update({"Authorization": f"Bearer {token}"})
        yield client, factory
    app.dependency_overrides.clear()


def _create_strategy(client: TestClient) -> str:
    res = client.post(
        "/strategies",
        json={
            "name": "Slice38 Strategy",
            "setup_type": "htf_trend_pullback",
            "card": _sample_card(),
        },
    )
    assert res.status_code == 200, res.text
    strategy_id = res.json()["id"]
    patch = client.patch(
        f"/strategies/{strategy_id}/structured-rules",
        json=_structured_rules(),
    )
    assert patch.status_code == 200, patch.text
    return strategy_id


def _create_lesson(client: TestClient, strategy_id: str | None = None) -> str:
    res = client.post(
        "/lessons/candidates",
        json={
            "source_type": "journal",
            "lesson_text": "I exited too early while structure still supported continuation.",
            "mistake_type": "early_exit",
            "severity": "medium",
            "related_strategy_id": strategy_id,
            "proposed_rule_update": {
                "summary": "Hold runner until structure break after TP1.",
                "structured_rules_patch": _structured_rules(),
            },
        },
    )
    assert res.status_code == 200, res.text
    return res.json()["id"]


def test_accept_lesson_only(slice38_client: tuple[TestClient, sessionmaker[Session]]) -> None:
    client, _ = slice38_client
    lesson_id = _create_lesson(client)
    res = client.patch(
        f"/lessons/candidates/{lesson_id}/accept",
        json={"reviewer_notes": "Accepted memory only."},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "accepted"


def test_accept_lesson_with_rule_attach(
    slice38_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = slice38_client
    strategy_id = _create_strategy(client)
    lesson_id = _create_lesson(client, strategy_id)
    res = client.patch(
        f"/lessons/candidates/{lesson_id}/accept",
        json={
            "reviewer_notes": "Attach rule",
            "attach_rule_to_strategy": True,
            "related_strategy_id": strategy_id,
            "accepted_rule_update": {
                "summary": "Attach runner hold rule",
                "structured_rules_patch": _structured_rules(),
            },
        },
    )
    assert res.status_code == 200
    testability = client.get(f"/strategies/{strategy_id}/testability")
    assert testability.status_code == 200
    assert testability.json()["has_structured_rules"] is True


def test_accept_lesson_creates_strategy_version(
    slice38_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = slice38_client
    strategy_id = _create_strategy(client)
    lesson_id = _create_lesson(client, strategy_id)
    before = client.get(f"/strategies/{strategy_id}")
    assert before.status_code == 200
    v_before = before.json()["current_version"]

    res = client.patch(
        f"/lessons/candidates/{lesson_id}/accept",
        json={
            "create_strategy_version": True,
            "related_strategy_id": strategy_id,
            "accepted_rule_update": {
                "summary": "Version from lesson",
                "structured_rules_patch": _structured_rules(),
            },
        },
    )
    assert res.status_code == 200

    after = client.get(f"/strategies/{strategy_id}")
    assert after.json()["current_version"] == v_before + 1

    versions = client.get(f"/strategies/{strategy_id}/versions")
    assert versions.status_code == 200
    latest = versions.json()["items"][0]
    meta = latest.get("lesson_source_metadata")
    assert meta is not None
    assert meta["lesson_id"] == lesson_id
    assert meta["mistake_type"] == "early_exit"


def test_paper_eligibility_blocks_vague_strategy(
    slice38_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = slice38_client
    res = client.post(
        "/strategies",
        json={
            "name": "Vague",
            "setup_type": "htf_trend_pullback",
            "card": _sample_card(),
        },
    )
    strategy_id = res.json()["id"]
    elig = client.get(f"/strategies/{strategy_id}/paper-eligibility")
    assert elig.status_code == 200
    body = elig.json()
    assert body["status"] == PaperEligibilityStatus.NEEDS_STRUCTURE.value
    assert body["paper_eligible"] is False
    assert body["blockers"]


def test_paper_eligibility_blocks_insufficient_sample(
    slice38_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = slice38_client
    strategy_id = _create_strategy(client)
    backtest = client.post(
        f"/strategies/{strategy_id}/backtests",
        json={"assumptions": {"symbol": "BTCUSDT", "timeframe": "15m"}},
    )
    assert backtest.status_code == 200
    elig = client.get(f"/strategies/{strategy_id}/paper-eligibility")
    body = elig.json()
    assert body["paper_eligible"] is False
    assert body["status"] in {
        PaperEligibilityStatus.NEEDS_MORE_SAMPLE.value,
        PaperEligibilityStatus.NEEDS_BACKTEST.value,
        PaperEligibilityStatus.RESTRICTED.value,
    }


def test_paper_eligibility_blocks_critical_unresolved_lesson(
    slice38_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = slice38_client
    strategy_id = _create_strategy(client)
    client.post(
        "/lessons/candidates",
        json={
            "source_type": "journal",
            "lesson_text": "Critical stop violation pending review.",
            "mistake_type": "stop_violation",
            "severity": "critical",
            "related_strategy_id": strategy_id,
        },
    )
    backtest = client.post(
        f"/strategies/{strategy_id}/backtests",
        json={"assumptions": {"symbol": "BTCUSDT", "timeframe": "15m"}},
    )
    assert backtest.status_code == 200

    elig = client.get(f"/strategies/{strategy_id}/paper-eligibility")
    body = elig.json()
    assert body["status"] == PaperEligibilityStatus.NEEDS_LESSON_REVIEW.value
    assert any("critical" in b.lower() for b in body["blockers"])


def test_accepted_lesson_rag_retrieval(
    slice38_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = slice38_client
    lesson_id = _create_lesson(client)

    with factory() as session:
        service = LessonCandidateService(
            session,
            settings=Settings(
                journal_rag_sync_enabled=True,
                jwt_secret="slice38-test-secret-key-min",
            ),
        )
        assert service.prepare_memory_search_text(uuid.UUID(lesson_id)) is None

    client.patch(f"/lessons/candidates/{lesson_id}/accept", json={})

    with factory() as session:
        service = LessonCandidateService(
            session,
            settings=Settings(
                journal_rag_sync_enabled=True,
                jwt_secret="slice38-test-secret-key-min",
            ),
        )
        accepted_text = service.prepare_memory_search_text(uuid.UUID(lesson_id))
        assert accepted_text is not None
        assert "accepted" in accepted_text.lower()
        assert "early_exit" in accepted_text.lower()

    pending = client.get("/lessons/candidates", params={"status": "pending_review"})
    assert all(item["id"] != lesson_id for item in pending.json()["items"])


def test_agent_paper_eligibility_intent() -> None:
    assert classify_strategy_workflow("Why is this strategy blocked from paper validation?") == (
        Intent.PAPER_ELIGIBILITY_BLOCKERS
    )
    assert classify_strategy_workflow("Which lessons should update my strategy?") == (
        Intent.LESSON_STRATEGY_UPDATE
    )


def test_no_live_trading_path(slice38_client: tuple[TestClient, sessionmaker[Session]]) -> None:
    client, _ = slice38_client
    health = client.get("/health")
    assert health.json()["real_trading_enabled"] is False
    elig = client.get(f"/strategies/{_create_strategy(client)}/paper-eligibility")
    assert elig.json()["real_trading_enabled"] is False

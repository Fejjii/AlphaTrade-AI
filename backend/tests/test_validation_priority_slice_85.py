"""Tests for validation prioritization (Slice 85 — read-only, record derived).

Covers pure scoring (shrinkage, penalties, boosts, action labels, reliability
tiers), the service/endpoints over seeded pending run plans and candidates,
RBAC, tenant isolation, the optional user filter, and empty/small-sample
safety. No order/execution/proposal/approval/automation paths are exercised.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, get_settings
from app.core.errors import ForbiddenError
from app.db.base import Base
from app.db.models import (
    PaperValidationAlert,
    PaperValidationCandidate,
    PaperValidationDraft,
    PaperValidationRunPlan,
    PaperValidationRunSession,
    PaperValidationSessionResult,
)
from app.db.session import get_session
from app.main import create_app
from app.schemas.common import MembershipRole, PaperAlertType
from app.security.rate_limit import reset_rate_limiter
from app.security.rbac import require_membership_roles
from app.services.validation_priority.scoring import (
    ACTION_AVOID_FOR_NOW,
    ACTION_COLLECT_MORE_DATA,
    ACTION_PRIORITIZE,
    RELIABILITY_HIGH,
    RELIABILITY_LOW,
    RELIABILITY_MEDIUM,
    RELIABILITY_NONE,
    HistoryStats,
    ItemContext,
    compute_priority,
    reliability_tier,
)

_FULL_CHECKLIST = {
    "trend_checked": True,
    "support_resistance_checked": True,
    "volume_checked": True,
    "risk_reward_checked": True,
    "invalidation_checked": True,
    "higher_timeframe_checked": True,
    "news_or_funding_checked": True,
}

_BASE = {
    "environment": "local",
    "log_json": False,
    "execution_mode": "paper",
    "enable_real_trading": False,
    "database_url": "sqlite+pysqlite:///:memory:",
    "jwt_secret": "validation-priority-test-secret-min-32-chars",
    "rate_limit_use_redis": False,
    "access_token_denylist_use_redis": False,
    "provider_mode": "mock",
    "market_data_provider": "mock",
    "worker_enabled": False,
    "market_watcher_enabled": False,
    "market_watcher_bridge_enabled": False,
}


@dataclass
class Harness:
    client: TestClient
    factory: sessionmaker[Session]


@pytest.fixture(autouse=True)
def _reset_limiter() -> None:
    reset_rate_limiter()


@pytest.fixture
def harness() -> Iterator[Harness]:
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

    def _override_session() -> Iterator[Session]:
        with factory() as session:
            yield session

    get_settings.cache_clear()
    app = create_app(settings=Settings(**_BASE))
    app.dependency_overrides[get_session] = _override_session

    with TestClient(app) as client:
        yield Harness(client=client, factory=factory)

    app.dependency_overrides.clear()
    get_settings.cache_clear()
    engine.dispose()


def _register_owner(
    client: TestClient,
    email: str = "owner@example.com",
    organization_name: str = "Priority Org",
) -> tuple[dict[str, str], uuid.UUID, uuid.UUID]:
    reg = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
            "organization_name": organization_name,
        },
    )
    assert reg.status_code == 201, reg.text
    login = client.post(
        "/auth/login",
        json={"email": email, "password": "SecurePass123!"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["tokens"]["access_token"]
    org_id = uuid.UUID(reg.json()["organization"]["id"])
    user_id = uuid.UUID(reg.json()["user"]["id"])
    return {"Authorization": f"Bearer {token}"}, org_id, user_id


def _base_chain(
    session: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID | None,
    symbol: str,
    timeframe: str,
    condition: str,
    direction: str,
    confidence: float | None,
    candidate_status: str,
    checklist: dict | None,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Insert alert -> draft -> candidate and return (alert_id, draft_id, candidate_id)."""
    alert = PaperValidationAlert(
        organization_id=organization_id,
        user_id=user_id,
        alert_type=PaperAlertType.SETUP_SIGNAL_DETECTED,
        message="seeded setup",
    )
    session.add(alert)
    session.flush()

    draft = PaperValidationDraft(
        organization_id=organization_id,
        source_alert_id=alert.id,
        symbol=symbol,
        timeframe=timeframe,
        condition=condition,
        direction=direction,
        confidence=confidence,
        review_status="important",
        created_by=user_id,
    )
    session.add(draft)
    session.flush()

    candidate = PaperValidationCandidate(
        organization_id=organization_id,
        draft_id=draft.id,
        source_alert_id=alert.id,
        symbol=symbol,
        timeframe=timeframe,
        condition=condition,
        direction=direction,
        confidence=confidence,
        checklist_snapshot=checklist,
        candidate_status=candidate_status,
        created_by=user_id,
    )
    session.add(candidate)
    session.flush()
    return alert.id, draft.id, candidate.id


def _seed_history(
    factory: sessionmaker[Session],
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
    condition: str = "breakout",
    symbol: str = "BTCUSDT",
    confidence: float | None = 0.8,
    outcome: str = "success",
    invalidation_hit: bool = False,
    discipline_assessment: str = "disciplined",
    behaved_as_expected: bool | None = True,
) -> None:
    """Seed a completed session + result. The plan/candidate are archived so they
    never appear in the pending priority queue."""
    recorded = datetime(2026, 1, 10, 12, 0, tzinfo=UTC)
    started = recorded - timedelta(minutes=30)
    with factory() as session:
        alert_id, draft_id, candidate_id = _base_chain(
            session,
            organization_id=organization_id,
            user_id=user_id,
            symbol=symbol,
            timeframe="1h",
            condition=condition,
            direction="long",
            confidence=confidence,
            candidate_status="archived",
            checklist=None,
        )
        plan = PaperValidationRunPlan(
            organization_id=organization_id,
            candidate_id=candidate_id,
            draft_id=draft_id,
            source_alert_id=alert_id,
            symbol=symbol,
            timeframe="1h",
            condition=condition,
            direction="long",
            confidence=confidence,
            plan_status="archived",
            created_by=user_id,
        )
        session.add(plan)
        session.flush()

        run_session = PaperValidationRunSession(
            organization_id=organization_id,
            run_plan_id=plan.id,
            candidate_id=candidate_id,
            draft_id=draft_id,
            source_alert_id=alert_id,
            symbol=symbol,
            timeframe="1h",
            condition=condition,
            direction="long",
            session_status="completed",
            started_by=user_id,
            started_at=started,
            ended_at=recorded,
        )
        session.add(run_session)
        session.flush()

        session.add(
            PaperValidationSessionResult(
                organization_id=organization_id,
                run_session_id=run_session.id,
                run_plan_id=plan.id,
                outcome=outcome,
                success_criteria_met="met" if outcome == "success" else "not_met",
                failure_criteria_met="not_met",
                invalidation_hit=invalidation_hit,
                entry_assessment="entered_as_planned",
                discipline_assessment=discipline_assessment,
                behaved_as_expected=behaved_as_expected,
                recorded_by=user_id,
                recorded_at=recorded,
            )
        )
        session.commit()


def _seed_pending_plan(
    factory: sessionmaker[Session],
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
    condition: str = "breakout",
    symbol: str = "BTCUSDT",
    confidence: float | None = 0.8,
    checklist: dict | None = None,
) -> uuid.UUID:
    """Seed a planned run plan (pending). Its candidate is archived so only the
    plan appears in the pending queue."""
    with factory() as session:
        alert_id, draft_id, candidate_id = _base_chain(
            session,
            organization_id=organization_id,
            user_id=user_id,
            symbol=symbol,
            timeframe="1h",
            condition=condition,
            direction="long",
            confidence=confidence,
            candidate_status="archived",
            checklist=checklist,
        )
        plan = PaperValidationRunPlan(
            organization_id=organization_id,
            candidate_id=candidate_id,
            draft_id=draft_id,
            source_alert_id=alert_id,
            symbol=symbol,
            timeframe="1h",
            condition=condition,
            direction="long",
            confidence=confidence,
            checklist_snapshot=checklist,
            plan_status="planned",
            created_by=user_id,
        )
        session.add(plan)
        session.flush()
        plan_id = plan.id
        session.commit()
        return plan_id


def _seed_pending_candidate(
    factory: sessionmaker[Session],
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
    condition: str = "breakout",
    symbol: str = "BTCUSDT",
    confidence: float | None = 0.8,
    status: str = "queued",
    checklist: dict | None = None,
) -> uuid.UUID:
    """Seed a queued/reviewing candidate (pending). No run plan is created."""
    with factory() as session:
        _, _, candidate_id = _base_chain(
            session,
            organization_id=organization_id,
            user_id=user_id,
            symbol=symbol,
            timeframe="1h",
            condition=condition,
            direction="long",
            confidence=confidence,
            candidate_status=status,
            checklist=checklist,
        )
        session.commit()
        return candidate_id


# --- pure scoring -----------------------------------------------------------


def test_reliability_tiers() -> None:
    assert reliability_tier(0, 5) == RELIABILITY_NONE
    assert reliability_tier(3, 5) == RELIABILITY_LOW
    assert reliability_tier(5, 5) == RELIABILITY_MEDIUM
    assert reliability_tier(14, 5) == RELIABILITY_MEDIUM
    assert reliability_tier(15, 5) == RELIABILITY_HIGH


def test_compute_priority_strong_history_prioritizes() -> None:
    history = HistoryStats(
        sample_size=10,
        quality_score=85.0,
        success_rate=0.8,
        invalidation_hit_rate=0.0,
        should_have_avoided_rate=0.0,
    )
    result = compute_priority(
        history,
        ItemContext(confidence=0.9, confidence_bucket="very_high", readiness=1.0),
        min_sample=5,
        confidence_correlation="none",
    )
    assert result.action_label == ACTION_PRIORITIZE
    assert result.score >= 70
    assert result.reliability == RELIABILITY_MEDIUM


def test_compute_priority_avoid_history() -> None:
    history = HistoryStats(
        sample_size=10,
        quality_score=30.0,
        success_rate=0.2,
        invalidation_hit_rate=0.6,
        should_have_avoided_rate=0.4,
    )
    result = compute_priority(
        history,
        ItemContext(confidence=0.4, confidence_bucket="low", readiness=0.0),
        min_sample=5,
        confidence_correlation="none",
    )
    assert result.action_label == ACTION_AVOID_FOR_NOW
    codes = {factor.code for factor in result.factors}
    assert "invalidation_penalty" in codes
    assert "should_have_avoided_penalty" in codes


def test_compute_priority_insufficient_sample_collects_data() -> None:
    history = HistoryStats(
        sample_size=2,
        quality_score=95.0,
        success_rate=1.0,
        invalidation_hit_rate=0.0,
        should_have_avoided_rate=0.0,
    )
    result = compute_priority(
        history,
        ItemContext(confidence=0.9, confidence_bucket="very_high", readiness=1.0),
        min_sample=5,
        confidence_correlation="positive",
    )
    # Thin evidence must not fake high priority, regardless of raw quality.
    assert result.action_label == ACTION_COLLECT_MORE_DATA
    assert result.reliability == RELIABILITY_LOW


def test_compute_priority_no_history_is_neutral() -> None:
    result = compute_priority(
        HistoryStats(),
        ItemContext(),
        min_sample=5,
        confidence_correlation="none",
    )
    assert result.action_label == ACTION_COLLECT_MORE_DATA
    assert result.reliability == RELIABILITY_NONE
    assert result.score == 50


def test_compute_priority_shrinks_low_sample_toward_prior() -> None:
    result = compute_priority(
        HistoryStats(sample_size=1, quality_score=100.0),
        ItemContext(readiness=0.0),
        min_sample=5,
        confidence_correlation="none",
    )
    # r = 1/6, effective ~ 58 (pulled from 100 toward 50).
    assert 55 <= result.score <= 62
    assert any(factor.code == "low_sample_shrinkage" for factor in result.factors)


# --- auth + empty tenant ----------------------------------------------------


def test_endpoints_require_auth(harness: Harness) -> None:
    for path in (
        "/validation-priority/queue",
        "/validation-priority/summary",
        f"/validation-priority/explain/run_plan/{uuid.uuid4()}",
    ):
        assert harness.client.get(path).status_code == 401, path


def test_empty_tenant_returns_empty_queue(harness: Harness) -> None:
    headers, _, _ = _register_owner(harness.client)
    queue = harness.client.get("/validation-priority/queue", headers=headers)
    assert queue.status_code == 200, queue.text
    body = queue.json()
    assert body["total_pending"] == 0
    assert body["items"] == []
    assert "automation" in body["note"].lower()

    summary = harness.client.get("/validation-priority/summary", headers=headers).json()
    assert summary["total_pending"] == 0
    labels = {row["action_label"] for row in summary["by_action"]}
    assert labels == {"prioritize", "watch", "collect_more_data", "avoid_for_now"}


# --- queue scoring ----------------------------------------------------------


def test_pending_plan_with_strong_history_prioritized(harness: Harness) -> None:
    headers, org_id, user_id = _register_owner(harness.client)
    for _ in range(10):
        _seed_history(
            harness.factory,
            organization_id=org_id,
            user_id=user_id,
            condition="breakout",
            outcome="success",
        )
    plan_id = _seed_pending_plan(
        harness.factory,
        organization_id=org_id,
        user_id=user_id,
        condition="breakout",
        checklist=_FULL_CHECKLIST,
    )

    body = harness.client.get(
        "/validation-priority/queue", headers=headers, params={"min_sample": 5}
    ).json()
    assert body["total_pending"] == 1
    item = body["items"][0]
    assert item["item_id"] == str(plan_id)
    assert item["item_type"] == "run_plan"
    assert item["action_label"] == "prioritize"
    assert item["matched_dimension"] == "condition"
    assert item["matched_key"] == "breakout"
    assert item["matched_sample_size"] == 10
    assert item["priority_score"] >= 70


def test_pending_plan_with_avoid_history(harness: Harness) -> None:
    headers, org_id, user_id = _register_owner(harness.client)
    for _ in range(6):
        _seed_history(
            harness.factory,
            organization_id=org_id,
            user_id=user_id,
            condition="chop",
            outcome="failure",
            invalidation_hit=True,
            discipline_assessment="should_have_avoided",
            behaved_as_expected=False,
        )
    _seed_pending_plan(
        harness.factory,
        organization_id=org_id,
        user_id=user_id,
        condition="chop",
    )

    body = harness.client.get(
        "/validation-priority/queue", headers=headers, params={"min_sample": 5}
    ).json()
    item = body["items"][0]
    assert item["action_label"] == "avoid_for_now"
    assert item["rationale"]


def test_pending_plan_without_history_collects_data(harness: Harness) -> None:
    headers, org_id, user_id = _register_owner(harness.client)
    _seed_pending_plan(
        harness.factory,
        organization_id=org_id,
        user_id=user_id,
        condition="novel_setup",
        symbol="ETHUSDT",
    )

    body = harness.client.get(
        "/validation-priority/queue", headers=headers, params={"min_sample": 5}
    ).json()
    item = body["items"][0]
    assert item["action_label"] == "collect_more_data"
    assert item["reliability"] == "none"
    assert item["matched_dimension"] == "global"


def test_confidence_alignment_boost_applied(harness: Harness) -> None:
    headers, org_id, user_id = _register_owner(harness.client)
    for _ in range(3):
        _seed_history(
            harness.factory,
            organization_id=org_id,
            user_id=user_id,
            condition="breakout",
            confidence=0.3,
            outcome="failure",
        )
    for _ in range(3):
        _seed_history(
            harness.factory,
            organization_id=org_id,
            user_id=user_id,
            condition="breakout",
            confidence=0.9,
            outcome="success",
        )
    _seed_pending_plan(
        harness.factory,
        organization_id=org_id,
        user_id=user_id,
        condition="breakout",
        confidence=0.9,
    )

    body = harness.client.get(
        "/validation-priority/queue", headers=headers, params={"min_sample": 2}
    ).json()
    item = body["items"][0]
    codes = {factor["code"] for factor in item["factors"]}
    assert "confidence_alignment" in codes


# --- item type filter + summary ---------------------------------------------


def test_item_type_filter_and_summary(harness: Harness) -> None:
    headers, org_id, user_id = _register_owner(harness.client)
    _seed_pending_plan(harness.factory, organization_id=org_id, user_id=user_id)
    _seed_pending_candidate(
        harness.factory, organization_id=org_id, user_id=user_id, status="reviewing"
    )

    all_items = harness.client.get(
        "/validation-priority/queue", headers=headers, params={"min_sample": 5}
    ).json()
    assert all_items["total_pending"] == 2

    plans_only = harness.client.get(
        "/validation-priority/queue",
        headers=headers,
        params={"min_sample": 5, "item_type": "run_plan"},
    ).json()
    assert plans_only["total_pending"] == 1
    assert plans_only["items"][0]["item_type"] == "run_plan"

    summary = harness.client.get(
        "/validation-priority/summary", headers=headers, params={"min_sample": 5}
    ).json()
    assert summary["total_pending"] == 2
    assert summary["run_plans_pending"] == 1
    assert summary["candidates_pending"] == 1


# --- explain ----------------------------------------------------------------


def test_explain_returns_item_and_404(harness: Harness) -> None:
    headers, org_id, user_id = _register_owner(harness.client)
    plan_id = _seed_pending_plan(
        harness.factory, organization_id=org_id, user_id=user_id, checklist=_FULL_CHECKLIST
    )

    ok = harness.client.get(
        f"/validation-priority/explain/run_plan/{plan_id}",
        headers=headers,
        params={"min_sample": 5},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["item"]["item_id"] == str(plan_id)

    missing = harness.client.get(
        f"/validation-priority/explain/run_plan/{uuid.uuid4()}",
        headers=headers,
    )
    assert missing.status_code == 404


# --- user filter + tenant isolation -----------------------------------------


def test_user_filter_scopes_pending(harness: Harness) -> None:
    headers, org_id, user_id = _register_owner(harness.client)
    other_user = uuid.uuid4()
    _seed_pending_plan(harness.factory, organization_id=org_id, user_id=user_id)

    mine = harness.client.get(
        "/validation-priority/queue", headers=headers, params={"min_sample": 5}
    ).json()
    assert mine["total_pending"] == 1

    filtered = harness.client.get(
        "/validation-priority/queue",
        headers=headers,
        params={"min_sample": 5, "user_id": str(other_user)},
    ).json()
    assert filtered["total_pending"] == 0


def test_tenant_isolation(harness: Harness) -> None:
    headers_a, org_a, user_a = _register_owner(harness.client, "a@example.com", "Org A")
    headers_b, org_b, user_b = _register_owner(harness.client, "b@example.com", "Org B")
    _seed_pending_plan(harness.factory, organization_id=org_a, user_id=user_a)
    _seed_pending_plan(harness.factory, organization_id=org_a, user_id=user_a)
    _seed_pending_plan(harness.factory, organization_id=org_b, user_id=user_b)

    body_a = harness.client.get(
        "/validation-priority/queue", headers=headers_a, params={"min_sample": 5}
    ).json()
    body_b = harness.client.get(
        "/validation-priority/queue", headers=headers_b, params={"min_sample": 5}
    ).json()
    assert body_a["total_pending"] == 2
    assert body_b["total_pending"] == 1
    assert body_a["organization_id"] != body_b["organization_id"]


# --- RBAC contract ----------------------------------------------------------


def test_reader_dependency_allows_viewer_and_blocks_others() -> None:
    reader = require_membership_roles(
        MembershipRole.OWNER, MembershipRole.TRADER, MembershipRole.VIEWER
    )
    viewer = SimpleNamespace(membership_role=MembershipRole.VIEWER)
    assert reader(viewer) is viewer  # type: ignore[arg-type]

    owner_only = require_membership_roles(MembershipRole.OWNER)
    with pytest.raises(ForbiddenError):
        owner_only(SimpleNamespace(membership_role=MembershipRole.VIEWER))  # type: ignore[arg-type]

"""Tests for the learning analytics slice (Slice 84 — read-only, record derived).

Covers endpoint shapes, rate correctness, small-sample gating, scoring, the
optional user filter, tenant isolation, auth, and empty-tenant behavior, plus a
few pure scoring helpers. No order/execution/automation paths are exercised.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db.models import (
    PaperValidationAlert,
    PaperValidationCandidate,
    PaperValidationDraft,
    PaperValidationRunPlan,
    PaperValidationRunSession,
    PaperValidationSessionObservation,
    PaperValidationSessionResult,
)
from app.db.session import get_session
from app.main import create_app
from app.schemas.common import PaperAlertType
from app.security.rate_limit import reset_rate_limiter
from app.services.learning_analytics.scoring import (
    confidence_bucket,
    correlation_sign,
    discipline_grade,
    quality_score,
    safe_rate,
)

_BASE = {
    "environment": "local",
    "log_json": False,
    "execution_mode": "paper",
    "enable_real_trading": False,
    "database_url": "sqlite+pysqlite:///:memory:",
    "jwt_secret": "learning-analytics-test-secret-min-32-chars",
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
    organization_name: str = "Learning Org",
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


def _seed_session(
    factory: sessionmaker[Session],
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
    outcome: str = "success",
    condition: str = "breakout",
    timeframe: str = "1h",
    symbol: str = "BTCUSDT",
    direction: str = "long",
    confidence: float | None = 0.8,
    entry_assessment: str = "entered_as_planned",
    discipline_assessment: str = "disciplined",
    invalidation_hit: bool = False,
    behaved_as_expected: bool | None = True,
    lessons: str | None = None,
    session_status: str = "completed",
    started_at: datetime | None = None,
    recorded_at: datetime | None = None,
    observation_kinds: tuple[str, ...] = (),
) -> uuid.UUID:
    """Insert a full alert -> ... -> result chain and return the session id."""
    recorded = recorded_at or datetime(2026, 1, 10, 12, 0, tzinfo=UTC)
    started = started_at or (recorded - timedelta(minutes=30))
    with factory() as session:
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
            review_status="important",
            created_by=user_id,
        )
        session.add(draft)
        session.flush()

        candidate = PaperValidationCandidate(
            organization_id=organization_id,
            draft_id=draft.id,
            source_alert_id=alert.id,
            created_by=user_id,
        )
        session.add(candidate)
        session.flush()

        plan = PaperValidationRunPlan(
            organization_id=organization_id,
            candidate_id=candidate.id,
            draft_id=draft.id,
            source_alert_id=alert.id,
            symbol=symbol,
            timeframe=timeframe,
            condition=condition,
            direction=direction,
            confidence=confidence,
            created_by=user_id,
        )
        session.add(plan)
        session.flush()

        run_session = PaperValidationRunSession(
            organization_id=organization_id,
            run_plan_id=plan.id,
            candidate_id=candidate.id,
            draft_id=draft.id,
            source_alert_id=alert.id,
            symbol=symbol,
            timeframe=timeframe,
            condition=condition,
            direction=direction,
            session_status=session_status,
            started_by=user_id,
            started_at=started,
            ended_at=recorded,
        )
        session.add(run_session)
        session.flush()

        result = PaperValidationSessionResult(
            organization_id=organization_id,
            run_session_id=run_session.id,
            run_plan_id=plan.id,
            outcome=outcome,
            success_criteria_met="met" if outcome == "success" else "not_met",
            failure_criteria_met="not_met",
            invalidation_hit=invalidation_hit,
            entry_assessment=entry_assessment,
            discipline_assessment=discipline_assessment,
            behaved_as_expected=behaved_as_expected,
            lessons=lessons,
            recorded_by=user_id,
            recorded_at=recorded,
        )
        session.add(result)

        for kind in observation_kinds:
            session.add(
                PaperValidationSessionObservation(
                    organization_id=organization_id,
                    run_session_id=run_session.id,
                    run_plan_id=plan.id,
                    observation_kind=kind,
                    recorded_by=user_id,
                )
            )

        session.commit()
        return run_session.id


# --- auth + empty tenant ----------------------------------------------------


def test_endpoints_require_auth(harness: Harness) -> None:
    for path in (
        "/learning-analytics/summary",
        "/learning-analytics/setup-performance",
        "/learning-analytics/discipline",
        "/learning-analytics/confidence-outcome",
        "/learning-analytics/behavior-insights",
        "/learning-analytics/lessons",
        "/learning-analytics/setup-ranking",
    ):
        assert harness.client.get(path).status_code == 401, path


def test_empty_tenant_returns_nulls_not_errors(harness: Harness) -> None:
    headers, _, _ = _register_owner(harness.client)
    response = harness.client.get("/learning-analytics/summary", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["results_count"] == 0
    assert body["total_sessions"] == 0
    assert body["rates"]["success_rate"] is None
    assert body["average_minutes_to_outcome"] is None
    assert len(body["outcome_distribution"]) == 6
    assert all(item["count"] == 0 for item in body["outcome_distribution"])


# --- summary ----------------------------------------------------------------


def test_summary_counts_and_rates(harness: Harness) -> None:
    headers, org_id, user_id = _register_owner(harness.client)
    for _ in range(3):
        _seed_session(harness.factory, organization_id=org_id, user_id=user_id, outcome="success")
    _seed_session(
        harness.factory,
        organization_id=org_id,
        user_id=user_id,
        outcome="failure",
        behaved_as_expected=False,
        invalidation_hit=True,
        observation_kinds=("hit_trigger", "hit_invalidation"),
    )

    body = harness.client.get(
        "/learning-analytics/summary", headers=headers, params={"min_sample": 1}
    ).json()
    assert body["results_count"] == 4
    assert body["completed_sessions"] == 4
    assert body["rates"]["success_rate"] == 0.75
    assert body["rates"]["failure_rate"] == 0.25
    assert body["rates"]["invalidation_hit_rate"] == 0.25
    assert body["rates"]["behaved_as_expected_rate"] == 0.75
    assert body["funnel"]["results"] == 4
    assert body["funnel"]["alerts"] == 4
    assert body["observations"]["total_observations"] == 2
    assert body["average_minutes_to_outcome"] == 30.0


# --- setup performance + small-sample gating --------------------------------


def test_setup_performance_gates_small_samples(harness: Harness) -> None:
    headers, org_id, user_id = _register_owner(harness.client)
    for _ in range(6):
        _seed_session(
            harness.factory, organization_id=org_id, user_id=user_id, condition="breakout"
        )
    _seed_session(harness.factory, organization_id=org_id, user_id=user_id, condition="pullback")

    body = harness.client.get(
        "/learning-analytics/setup-performance",
        headers=headers,
        params={"dimension": "condition", "min_sample": 5},
    ).json()
    groups = {g["dimension_value"]: g for g in body["groups"]}
    assert groups["breakout"]["insufficient_data"] is False
    assert groups["breakout"]["quality_score"] is not None
    assert groups["pullback"]["insufficient_data"] is True
    assert groups["pullback"]["quality_score"] is None


# --- discipline -------------------------------------------------------------


def test_discipline_score_and_gating(harness: Harness) -> None:
    headers, org_id, user_id = _register_owner(harness.client)
    for _ in range(4):
        _seed_session(
            harness.factory,
            organization_id=org_id,
            user_id=user_id,
            discipline_assessment="disciplined",
        )
    for _ in range(2):
        _seed_session(
            harness.factory,
            organization_id=org_id,
            user_id=user_id,
            discipline_assessment="should_have_avoided",
        )

    gated = harness.client.get(
        "/learning-analytics/discipline", headers=headers, params={"min_sample": 50}
    ).json()
    assert gated["insufficient_data"] is True
    assert gated["discipline_score"] is None
    assert gated["discipline_grade"] == "insufficient_data"

    body = harness.client.get(
        "/learning-analytics/discipline", headers=headers, params={"min_sample": 1}
    ).json()
    assert body["insufficient_data"] is False
    # 4 disciplined (1.0) + 2 avoided (0.0) => 4/6 => 67
    assert body["discipline_score"] == 67
    assert body["discipline_grade"] == "D"
    assert "should_have_avoided" in body["issue_frequency"]


# --- confidence vs outcome --------------------------------------------------


def test_confidence_outcome_positive_correlation(harness: Harness) -> None:
    headers, org_id, user_id = _register_owner(harness.client)
    # low bucket: mostly failures; high bucket: mostly successes
    for _ in range(3):
        _seed_session(
            harness.factory,
            organization_id=org_id,
            user_id=user_id,
            confidence=0.3,
            outcome="failure",
        )
    for _ in range(3):
        _seed_session(
            harness.factory,
            organization_id=org_id,
            user_id=user_id,
            confidence=0.9,
            outcome="success",
        )

    body = harness.client.get(
        "/learning-analytics/confidence-outcome",
        headers=headers,
        params={"min_sample": 2},
    ).json()
    buckets = {b["bucket"]: b for b in body["buckets"]}
    assert buckets["low"]["success_rate"] == 0.0
    assert buckets["very_high"]["success_rate"] == 1.0
    assert body["correlation"] == "positive"


# --- behavior insights ------------------------------------------------------


def test_behavior_insight_strong_setup_misses(harness: Harness) -> None:
    headers, org_id, user_id = _register_owner(harness.client)
    for _ in range(5):
        _seed_session(
            harness.factory,
            organization_id=org_id,
            user_id=user_id,
            confidence=0.9,
            entry_assessment="missed_entry",
            outcome="missed_entry",
        )

    body = harness.client.get(
        "/learning-analytics/behavior-insights",
        headers=headers,
        params={"min_sample": 5},
    ).json()
    codes = {insight["code"] for insight in body["insights"]}
    assert "misses_entries_on_strong_setups" in codes


# --- lessons ----------------------------------------------------------------


def test_lesson_themes(harness: Harness) -> None:
    headers, org_id, user_id = _register_owner(harness.client)
    for _ in range(3):
        _seed_session(
            harness.factory,
            organization_id=org_id,
            user_id=user_id,
            lessons="Patience before entry improves outcomes",
        )

    body = harness.client.get(
        "/learning-analytics/lessons", headers=headers, params={"min_sample": 1}
    ).json()
    assert body["lessons_count"] == 3
    themes = {theme["theme"] for theme in body["themes"]}
    assert "patience" in themes or "entry" in themes


# --- setup ranking ----------------------------------------------------------


def test_setup_ranking_excludes_insufficient(harness: Harness) -> None:
    headers, org_id, user_id = _register_owner(harness.client)
    for _ in range(6):
        _seed_session(
            harness.factory, organization_id=org_id, user_id=user_id, condition="breakout"
        )
    _seed_session(harness.factory, organization_id=org_id, user_id=user_id, condition="pullback")

    body = harness.client.get(
        "/learning-analytics/setup-ranking",
        headers=headers,
        params={"dimension": "condition", "min_sample": 5},
    ).json()
    keys = {item["setup_key"] for item in body["ranked"]}
    assert "breakout" in keys
    assert "pullback" not in keys
    assert body["ranked"][0]["rank"] == 1
    assert "automation" in body["note"].lower()


# --- user filter ------------------------------------------------------------


def test_user_filter_scopes_results(harness: Harness) -> None:
    headers, org_id, user_id = _register_owner(harness.client)
    other_user = uuid.uuid4()  # not the caller; used only as started_by attribution
    _seed_session(harness.factory, organization_id=org_id, user_id=user_id)
    _seed_session(harness.factory, organization_id=org_id, user_id=user_id)

    all_body = harness.client.get(
        "/learning-analytics/summary", headers=headers, params={"min_sample": 1}
    ).json()
    assert all_body["results_count"] == 2

    filtered = harness.client.get(
        "/learning-analytics/summary",
        headers=headers,
        params={"min_sample": 1, "user_id": str(other_user)},
    ).json()
    assert filtered["results_count"] == 0


# --- tenant isolation -------------------------------------------------------


def test_tenant_isolation(harness: Harness) -> None:
    headers_a, org_a, user_a = _register_owner(harness.client, "a@example.com", "Org A")
    headers_b, org_b, user_b = _register_owner(harness.client, "b@example.com", "Org B")
    _seed_session(harness.factory, organization_id=org_a, user_id=user_a)
    _seed_session(harness.factory, organization_id=org_a, user_id=user_a)
    _seed_session(harness.factory, organization_id=org_b, user_id=user_b)

    body_a = harness.client.get(
        "/learning-analytics/summary", headers=headers_a, params={"min_sample": 1}
    ).json()
    body_b = harness.client.get(
        "/learning-analytics/summary", headers=headers_b, params={"min_sample": 1}
    ).json()
    assert body_a["results_count"] == 2
    assert body_b["results_count"] == 1
    assert body_a["organization_id"] != body_b["organization_id"]


# --- pure scoring helpers ---------------------------------------------------


def test_scoring_helpers() -> None:
    assert safe_rate(1, 4) == 0.25
    assert safe_rate(1, 0) is None
    assert confidence_bucket(0.3) == "low"
    assert confidence_bucket(0.9) == "very_high"
    assert confidence_bucket(1.0) == "very_high"
    assert confidence_bucket(None) is None
    assert discipline_grade(95) == "A"
    assert discipline_grade(50) == "F"
    assert quality_score(1.0, 1.0, 0.0, 0.0) == 100.0
    assert quality_score(0.0, 0.0, 1.0, 1.0) == 0.0
    assert correlation_sign([(0, 0.2), (3, 0.9)]) == "positive"
    assert correlation_sign([(0, 0.9), (3, 0.2)]) == "negative"
    assert correlation_sign([(0, 0.5)]) == "insufficient_data"

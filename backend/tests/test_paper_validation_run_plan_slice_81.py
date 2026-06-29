"""Slice 81 — paper validation run plan endpoints."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.db.base import Base
from app.db.models import (
    Membership,
    Organization,
    PaperValidationAlert,
    PaperValidationRunPlan,
    User,
)
from app.db.session import get_session
from app.main import create_app
from app.schemas.common import (
    MembershipRole,
    PaperAlertSource,
    PaperAlertType,
    SetupAlertReviewStatus,
)
from app.schemas.paper_validation_candidate import QUEUE_PAPER_VALIDATION_CANDIDATE_CONFIRM
from app.schemas.paper_validation_draft import CREATE_PAPER_VALIDATION_DRAFT_CONFIRM
from app.schemas.paper_validation_run_plan import CREATE_PAPER_VALIDATION_RUN_PLAN_CONFIRM
from app.security.passwords import hash_password
from app.security.rate_limit import reset_rate_limiter
from app.services.paper_alert_service import PaperAlertService

ORG_A = uuid.UUID("00000000-0000-0000-0000-000000008101")
ORG_B = uuid.UUID("00000000-0000-0000-0000-000000008102")
USER_A = uuid.UUID("00000000-0000-0000-0000-000000008111")
USER_B = uuid.UUID("00000000-0000-0000-0000-000000008112")

_BASE = {
    "environment": "local",
    "log_json": False,
    "execution_mode": "paper",
    "enable_real_trading": False,
    "database_url": "sqlite+pysqlite:///:memory:",
    "jwt_secret": "paper-validation-run-plan-secret-32",
    "rate_limit_use_redis": False,
    "access_token_denylist_use_redis": False,
    "provider_mode": "mock",
    "market_data_provider": "mock",
    "alert_delivery_enabled": False,
    "telegram_alerts_enabled": False,
    "worker_enabled": False,
    "market_watcher_enabled": False,
}

_READY_PREP = {
    "prep_status": "ready_for_validation",
    "thesis": "Ready thesis for run plan.",
    "entry_criteria": "Entry rules for run plan.",
    "invalidation_criteria": "Invalidation rules for run plan.",
    "risk_notes": "Conservative run plan prep.",
    "checklist": {
        "trend_checked": True,
        "support_resistance_checked": True,
        "volume_checked": True,
        "risk_reward_checked": True,
        "invalidation_checked": True,
        "higher_timeframe_checked": True,
        "news_or_funding_checked": True,
    },
}

_PLAN_PAYLOAD = {
    "confirm": CREATE_PAPER_VALIDATION_RUN_PLAN_CONFIRM,
    "validation_window": "intraday",
    "observation_timeframe": "1h",
    "max_duration_minutes": 240,
    "planned_entry_rule": "Wait for price confirmation around trigger level.",
    "planned_invalidation_rule": "Invalid if price closes beyond invalidation level.",
    "planned_success_criteria": "Price moves toward first target area without invalidation.",
    "planned_failure_criteria": "Invalidation level hit or thesis no longer valid.",
}


@pytest.fixture(autouse=True)
def _reset_limiter() -> None:
    reset_rate_limiter()


@pytest.fixture
def client() -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
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
    settings = Settings(**_BASE)

    with factory() as session:
        session.add(Organization(id=ORG_A, name="Run Plan Org A"))
        session.add(Organization(id=ORG_B, name="Run Plan Org B"))
        session.add(
            User(
                id=USER_A,
                email="run-plan-a@test.example",
                hashed_password=hash_password("SecurePass123!", settings),
                email_verified=True,
            )
        )
        session.add(
            User(
                id=USER_B,
                email="run-plan-b@test.example",
                hashed_password=hash_password("SecurePass123!", settings),
                email_verified=True,
            )
        )
        session.flush()
        session.add(Membership(user_id=USER_A, organization_id=ORG_A, role=MembershipRole.OWNER))
        session.add(Membership(user_id=USER_B, organization_id=ORG_B, role=MembershipRole.OWNER))
        session.commit()

    app = create_app(settings=settings)

    def _override_session() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = _override_session

    with TestClient(app) as test_client:
        yield test_client, factory

    app.dependency_overrides.clear()
    engine.dispose()


def _auth(client: TestClient, email: str, password: str = "SecurePass123!") -> dict[str, str]:
    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    token = login.json()["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_market_watcher_alert(
    factory: sessionmaker[Session],
    *,
    organization_id: uuid.UUID = ORG_A,
    user_id: uuid.UUID = USER_A,
) -> uuid.UUID:
    with factory() as session:
        service = PaperAlertService(session)
        created = service.create(
            organization_id=organization_id,
            user_id=user_id,
            alert_type=PaperAlertType.SETUP_SIGNAL_DETECTED,
            message="order_block on BTCUSDT 15m",
            metadata={
                "source": PaperAlertSource.MARKET_WATCHER.value,
                "condition": "order_block",
                "symbol": "BTCUSDT",
                "timeframe": "15m",
                "direction": "long",
                "confidence": 0.85,
                "reason": "Clean retest setup.",
                "trigger_level": 65000.0,
                "invalidation_level": 64000.0,
                "metrics": {"latest_price": 65100.0},
            },
            dedup_key=f"test:order_block:{uuid.uuid4()}",
            skip_dedup=True,
            source=PaperAlertSource.MARKET_WATCHER,
        )
        assert created is not None
        row = session.scalar(
            select(PaperValidationAlert).where(PaperValidationAlert.id == created.id)
        )
        assert row is not None
        row.review_status = SetupAlertReviewStatus.IMPORTANT.value
        alert_id = row.id
        session.commit()
        return alert_id


def _create_reviewing_candidate(
    client: TestClient,
    headers: dict[str, str],
    factory: sessionmaker[Session],
) -> str:
    alert_id = _create_market_watcher_alert(factory)
    created = client.post(
        f"/alerts/setup-review/{alert_id}/draft",
        headers=headers,
        json={
            "confirm": CREATE_PAPER_VALIDATION_DRAFT_CONFIRM,
            "notes": "Run plan test",
            "risk_mode": "conservative",
        },
    )
    assert created.status_code == 200, created.text
    draft_id = created.json()["draft"]["draft_id"]
    prep = client.patch(
        f"/paper-validation/drafts/{draft_id}/prep",
        headers=headers,
        json=_READY_PREP,
    )
    assert prep.status_code == 200, prep.text
    queued = client.post(
        f"/paper-validation/drafts/{draft_id}/queue",
        headers=headers,
        json={"confirm": QUEUE_PAPER_VALIDATION_CANDIDATE_CONFIRM},
    )
    assert queued.status_code == 200, queued.text
    candidate_id = queued.json()["candidate"]["candidate_id"]
    reviewing = client.patch(
        f"/paper-validation/candidates/{candidate_id}",
        headers=headers,
        json={"candidate_status": "reviewing"},
    )
    assert reviewing.status_code == 200, reviewing.text
    return candidate_id


def _plan_payload(**overrides: object) -> dict[str, object]:
    payload = dict(_PLAN_PAYLOAD)
    payload.update(overrides)
    return payload


def test_exact_confirmation_required(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "run-plan-a@test.example")
    candidate_id = _create_reviewing_candidate(test_client, headers, factory)

    response = test_client.post(
        f"/paper-validation/candidates/{candidate_id}/plan",
        headers=headers,
        json=_plan_payload(confirm="WRONG"),
    )
    assert response.status_code == 422
    assert "confirmation required" in response.json()["error"]["message"].lower()


def test_cannot_create_plan_unless_reviewing(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "run-plan-a@test.example")
    candidate_id = _create_reviewing_candidate(test_client, headers, factory)
    test_client.patch(
        f"/paper-validation/candidates/{candidate_id}",
        headers=headers,
        json={"candidate_status": "queued"},
    )

    response = test_client.post(
        f"/paper-validation/candidates/{candidate_id}/plan",
        headers=headers,
        json=_plan_payload(),
    )
    assert response.status_code == 422
    assert "reviewing" in response.json()["error"]["message"].lower()


def test_can_create_plan_from_reviewing_candidate(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "run-plan-a@test.example")
    candidate_id = _create_reviewing_candidate(test_client, headers, factory)

    response = test_client.post(
        f"/paper-validation/candidates/{candidate_id}/plan",
        headers=headers,
        json=_plan_payload(),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["already_exists"] is False
    assert body["plan"]["candidate_id"] == candidate_id
    assert body["plan"]["plan_status"] == "planned"
    assert body["plan"]["validation_window"] == "intraday"
    assert body["plan"]["thesis"] == _READY_PREP["thesis"]
    assert body["plan"]["planned_entry_rule"] == _PLAN_PAYLOAD["planned_entry_rule"]


def test_duplicate_plan_returns_existing(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "run-plan-a@test.example")
    candidate_id = _create_reviewing_candidate(test_client, headers, factory)

    first = test_client.post(
        f"/paper-validation/candidates/{candidate_id}/plan",
        headers=headers,
        json=_plan_payload(),
    )
    second = test_client.post(
        f"/paper-validation/candidates/{candidate_id}/plan",
        headers=headers,
        json=_plan_payload(planned_entry_rule="Different entry rule text."),
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["already_exists"] is True
    assert second.json()["plan"]["plan_id"] == first.json()["plan"]["plan_id"]


def test_list_read_tenant_scoped(client: tuple[TestClient, sessionmaker[Session]]) -> None:
    test_client, factory = client
    headers_a = _auth(test_client, "run-plan-a@test.example")
    headers_b = _auth(test_client, "run-plan-b@test.example")
    candidate_id = _create_reviewing_candidate(test_client, headers_a, factory)
    created = test_client.post(
        f"/paper-validation/candidates/{candidate_id}/plan",
        headers=headers_a,
        json=_plan_payload(),
    )
    plan_id = created.json()["plan"]["plan_id"]

    listing = test_client.get("/paper-validation/run-plans", headers=headers_a)
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["plan_id"] == plan_id

    read = test_client.get(f"/paper-validation/run-plans/{plan_id}", headers=headers_a)
    assert read.status_code == 200
    assert read.json()["symbol"] == "BTCUSDT"

    other_list = test_client.get("/paper-validation/run-plans", headers=headers_b)
    assert other_list.status_code == 200
    assert other_list.json()["total"] == 0

    other_read = test_client.get(f"/paper-validation/run-plans/{plan_id}", headers=headers_b)
    assert other_read.status_code == 404


def test_plan_summary_works(client: tuple[TestClient, sessionmaker[Session]]) -> None:
    test_client, factory = client
    headers = _auth(test_client, "run-plan-a@test.example")
    candidate_id = _create_reviewing_candidate(test_client, headers, factory)
    test_client.post(
        f"/paper-validation/candidates/{candidate_id}/plan",
        headers=headers,
        json=_plan_payload(),
    )

    summary = test_client.get("/paper-validation/run-plans/summary", headers=headers)
    assert summary.status_code == 200
    body = summary.json()
    assert body["total_planned"] == 1
    assert body["by_condition"]["order_block"] == 1
    assert body["by_symbol"]["BTCUSDT"] == 1


def test_plan_status_update_works(client: tuple[TestClient, sessionmaker[Session]]) -> None:
    test_client, factory = client
    headers = _auth(test_client, "run-plan-a@test.example")
    candidate_id = _create_reviewing_candidate(test_client, headers, factory)
    created = test_client.post(
        f"/paper-validation/candidates/{candidate_id}/plan",
        headers=headers,
        json=_plan_payload(),
    )
    plan_id = created.json()["plan"]["plan_id"]

    updated = test_client.patch(
        f"/paper-validation/run-plans/{plan_id}",
        headers=headers,
        json={"plan_status": "needs_revision"},
    )
    assert updated.status_code == 200
    assert updated.json()["plan_status"] == "needs_revision"


def test_invalid_plan_status_rejected(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "run-plan-a@test.example")
    candidate_id = _create_reviewing_candidate(test_client, headers, factory)
    created = test_client.post(
        f"/paper-validation/candidates/{candidate_id}/plan",
        headers=headers,
        json=_plan_payload(),
    )
    plan_id = created.json()["plan"]["plan_id"]

    response = test_client.patch(
        f"/paper-validation/run-plans/{plan_id}",
        headers=headers,
        json={"plan_status": "running"},
    )
    assert response.status_code == 422


def test_plan_emits_audit_events(client: tuple[TestClient, sessionmaker[Session]]) -> None:
    test_client, factory = client
    headers = _auth(test_client, "run-plan-a@test.example")
    candidate_id = _create_reviewing_candidate(test_client, headers, factory)
    test_client.post(
        f"/paper-validation/candidates/{candidate_id}/plan",
        headers=headers,
        json=_plan_payload(),
    )

    audit = test_client.get(
        "/audit/events?event_type=paper_validation_runtime",
        headers=headers,
    )
    assert audit.status_code == 200
    actions = [item.get("redacted_metadata", {}).get("action") for item in audit.json()["items"]]
    assert "paper_validation_run_plan_requested" in actions
    assert "paper_validation_run_plan_created" in actions


@patch("app.services.telegram_alert_delivery_service.TelegramAlertDeliveryService.deliver_alert")
@patch("app.services.alert_delivery_service.AlertDeliveryService.deliver_alert")
@patch("app.services.execution_service.ExecutionService.place_paper_order")
@patch("app.services.proposal_service.ProposalService.create")
@patch("app.services.approval_service.ApprovalService.create_for_proposal")
@patch("app.services.paper_validation_runtime_service.PaperValidationRuntimeService.tick")
@patch("app.services.paper_validation_runtime_service.PaperValidationRuntimeService.scan")
@patch("app.services.paper_validation_runtime_service.PaperValidationRuntimeService.start")
def test_plan_does_not_start_runtime_or_execute(
    mock_start_run: object,
    mock_scan: object,
    mock_tick: object,
    mock_approval: object,
    mock_proposal: object,
    mock_execute: object,
    mock_deliver: object,
    mock_telegram: object,
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "run-plan-a@test.example")
    candidate_id = _create_reviewing_candidate(test_client, headers, factory)

    response = test_client.post(
        f"/paper-validation/candidates/{candidate_id}/plan",
        headers=headers,
        json=_plan_payload(),
    )
    assert response.status_code == 200

    mock_start_run.assert_not_called()
    mock_scan.assert_not_called()
    mock_tick.assert_not_called()
    mock_execute.assert_not_called()
    mock_proposal.assert_not_called()
    mock_approval.assert_not_called()
    mock_deliver.assert_not_called()
    mock_telegram.assert_not_called()


def test_no_plan_rows_duplicated_on_repeat_create(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "run-plan-a@test.example")
    candidate_id = _create_reviewing_candidate(test_client, headers, factory)
    test_client.post(
        f"/paper-validation/candidates/{candidate_id}/plan",
        headers=headers,
        json=_plan_payload(),
    )
    test_client.post(
        f"/paper-validation/candidates/{candidate_id}/plan",
        headers=headers,
        json=_plan_payload(),
    )

    with factory() as session:
        count = session.scalar(select(func.count()).select_from(PaperValidationRunPlan)) or 0
        assert count == 1

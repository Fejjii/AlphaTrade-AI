"""Slice 83 — paper validation session observations and results (record only, no engine)."""

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
    PaperValidationSessionObservation,
    PaperValidationSessionResult,
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
from app.schemas.paper_validation_run_session import START_PAPER_VALIDATION_RUN_CONFIRM
from app.schemas.paper_validation_session_observation import (
    RECORD_PAPER_VALIDATION_OBSERVATION_CONFIRM,
)
from app.schemas.paper_validation_session_result import RECORD_PAPER_VALIDATION_OUTCOME_CONFIRM
from app.security.passwords import hash_password
from app.security.rate_limit import reset_rate_limiter
from app.services.paper_alert_service import PaperAlertService

ORG_A = uuid.UUID("00000000-0000-0000-0000-000000008301")
ORG_B = uuid.UUID("00000000-0000-0000-0000-000000008302")
USER_A = uuid.UUID("00000000-0000-0000-0000-000000008311")
USER_B = uuid.UUID("00000000-0000-0000-0000-000000008312")
USER_T = uuid.UUID("00000000-0000-0000-0000-000000008313")

_BASE = {
    "environment": "local",
    "log_json": False,
    "execution_mode": "paper",
    "enable_real_trading": False,
    "database_url": "sqlite+pysqlite:///:memory:",
    "jwt_secret": "paper-validation-session-obs-secret-32",
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
    "thesis": "Ready thesis.",
    "entry_criteria": "Entry rules.",
    "invalidation_criteria": "Invalidation rules.",
    "risk_notes": "Conservative prep.",
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
    "planned_entry_rule": "Wait for confirmation.",
    "planned_invalidation_rule": "Invalid beyond level.",
    "planned_success_criteria": "Target area reached.",
    "planned_failure_criteria": "Invalidation hit.",
}

_START_PAYLOAD = {"confirm": START_PAPER_VALIDATION_RUN_CONFIRM, "notes": "Slice 83 session."}

_OBSERVATION_PAYLOAD = {
    "confirm": RECORD_PAPER_VALIDATION_OBSERVATION_CONFIRM,
    "observation_kind": "hit_trigger",
    "observed_price": 65100.0,
    "note": "Price touched trigger zone.",
}

_RESULT_PAYLOAD = {
    "confirm": RECORD_PAPER_VALIDATION_OUTCOME_CONFIRM,
    "outcome": "success",
    "success_criteria_met": "met",
    "failure_criteria_met": "not_met",
    "invalidation_hit": False,
    "entry_assessment": "no_entry",
    "discipline_assessment": "disciplined",
    "behaved_as_expected": True,
    "lessons": "Waited for confirmation.",
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
        session.add(Organization(id=ORG_A, name="Obs Org A"))
        session.add(Organization(id=ORG_B, name="Obs Org B"))
        for user_id, email in (
            (USER_A, "session-obs-a@test.example"),
            (USER_B, "session-obs-b@test.example"),
            (USER_T, "session-obs-trader@test.example"),
        ):
            session.add(
                User(
                    id=user_id,
                    email=email,
                    hashed_password=hash_password("SecurePass123!", settings),
                    email_verified=True,
                )
            )
        session.flush()
        session.add(Membership(user_id=USER_A, organization_id=ORG_A, role=MembershipRole.OWNER))
        session.add(Membership(user_id=USER_B, organization_id=ORG_B, role=MembershipRole.OWNER))
        session.add(Membership(user_id=USER_T, organization_id=ORG_A, role=MembershipRole.TRADER))
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


def _create_planned_plan(
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
            "notes": "Slice 83 test",
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
    plan = client.post(
        f"/paper-validation/candidates/{candidate_id}/plan",
        headers=headers,
        json=dict(_PLAN_PAYLOAD),
    )
    assert plan.status_code == 200, plan.text
    return plan.json()["plan"]["plan_id"]


def _start_session(
    client: TestClient,
    headers: dict[str, str],
    factory: sessionmaker[Session],
) -> str:
    plan_id = _create_planned_plan(client, headers, factory)
    created = client.post(
        f"/paper-validation/run-plans/{plan_id}/start",
        headers=headers,
        json=dict(_START_PAYLOAD),
    )
    assert created.status_code == 200, created.text
    return created.json()["session"]["session_id"]


def test_observation_confirm_required(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "session-obs-a@test.example")
    session_id = _start_session(test_client, headers, factory)

    response = test_client.post(
        f"/paper-validation/run-sessions/{session_id}/observations",
        headers=headers,
        json={"confirm": "WRONG", "observation_kind": "general_note"},
    )
    assert response.status_code == 422
    with factory() as session:
        count = (
            session.scalar(select(func.count()).select_from(PaperValidationSessionObservation)) or 0
        )
        assert count == 0


def test_record_and_list_observations(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "session-obs-a@test.example")
    session_id = _start_session(test_client, headers, factory)

    recorded = test_client.post(
        f"/paper-validation/run-sessions/{session_id}/observations",
        headers=headers,
        json=dict(_OBSERVATION_PAYLOAD),
    )
    assert recorded.status_code == 200, recorded.text
    assert recorded.json()["observation_kind"] == "hit_trigger"
    assert recorded.json()["observed_price"] == 65100.0

    listing = test_client.get(
        f"/paper-validation/run-sessions/{session_id}/observations",
        headers=headers,
    )
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["note"] == "Price touched trigger zone."


def test_observation_blocked_when_session_not_running(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "session-obs-a@test.example")
    session_id = _start_session(test_client, headers, factory)
    test_client.patch(
        f"/paper-validation/run-sessions/{session_id}",
        headers=headers,
        json={"session_status": "cancelled"},
    )

    response = test_client.post(
        f"/paper-validation/run-sessions/{session_id}/observations",
        headers=headers,
        json=dict(_OBSERVATION_PAYLOAD),
    )
    assert response.status_code == 422


def test_result_confirm_required(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "session-obs-a@test.example")
    session_id = _start_session(test_client, headers, factory)

    response = test_client.post(
        f"/paper-validation/run-sessions/{session_id}/result",
        headers=headers,
        json={"confirm": "WRONG", **{k: v for k, v in _RESULT_PAYLOAD.items() if k != "confirm"}},
    )
    assert response.status_code == 422
    with factory() as session:
        count = session.scalar(select(func.count()).select_from(PaperValidationSessionResult)) or 0
        assert count == 0


def test_record_result_idempotent(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "session-obs-a@test.example")
    session_id = _start_session(test_client, headers, factory)

    first = test_client.post(
        f"/paper-validation/run-sessions/{session_id}/result",
        headers=headers,
        json=dict(_RESULT_PAYLOAD),
    )
    assert first.status_code == 200
    assert first.json()["already_exists"] is False

    second = test_client.post(
        f"/paper-validation/run-sessions/{session_id}/result",
        headers=headers,
        json=dict(_RESULT_PAYLOAD),
    )
    assert second.status_code == 200
    assert second.json()["already_exists"] is True
    assert second.json()["result"]["result_id"] == first.json()["result"]["result_id"]

    with factory() as session:
        count = session.scalar(select(func.count()).select_from(PaperValidationSessionResult)) or 0
        assert count == 1


def test_get_and_update_result(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "session-obs-a@test.example")
    session_id = _start_session(test_client, headers, factory)
    test_client.post(
        f"/paper-validation/run-sessions/{session_id}/result",
        headers=headers,
        json=dict(_RESULT_PAYLOAD),
    )

    read = test_client.get(
        f"/paper-validation/run-sessions/{session_id}/result",
        headers=headers,
    )
    assert read.status_code == 200
    assert read.json()["outcome"] == "success"

    updated = test_client.patch(
        f"/paper-validation/run-sessions/{session_id}/result",
        headers=headers,
        json={"outcome": "inconclusive", "lessons": "Need more data."},
    )
    assert updated.status_code == 200
    assert updated.json()["outcome"] == "inconclusive"
    assert updated.json()["lessons"] == "Need more data."


def test_complete_requires_result_cancel_does_not(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "session-obs-a@test.example")

    session_id = _start_session(test_client, headers, factory)
    blocked = test_client.patch(
        f"/paper-validation/run-sessions/{session_id}",
        headers=headers,
        json={"session_status": "completed"},
    )
    assert blocked.status_code == 422
    assert "outcome" in blocked.json()["error"]["message"].lower()

    test_client.post(
        f"/paper-validation/run-sessions/{session_id}/result",
        headers=headers,
        json=dict(_RESULT_PAYLOAD),
    )
    completed = test_client.patch(
        f"/paper-validation/run-sessions/{session_id}",
        headers=headers,
        json={"session_status": "completed"},
    )
    assert completed.status_code == 200

    session_id_2 = _start_session(test_client, headers, factory)
    cancelled = test_client.patch(
        f"/paper-validation/run-sessions/{session_id_2}",
        headers=headers,
        json={"session_status": "cancelled"},
    )
    assert cancelled.status_code == 200


def test_result_blocked_when_session_not_running(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "session-obs-a@test.example")
    session_id = _start_session(test_client, headers, factory)
    test_client.patch(
        f"/paper-validation/run-sessions/{session_id}",
        headers=headers,
        json={"session_status": "cancelled"},
    )

    response = test_client.post(
        f"/paper-validation/run-sessions/{session_id}/result",
        headers=headers,
        json=dict(_RESULT_PAYLOAD),
    )
    assert response.status_code == 422


def test_rbac_trader_can_observe_not_result(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    owner_headers = _auth(test_client, "session-obs-a@test.example")
    trader_headers = _auth(test_client, "session-obs-trader@test.example")
    session_id = _start_session(test_client, owner_headers, factory)

    ok = test_client.post(
        f"/paper-validation/run-sessions/{session_id}/observations",
        headers=trader_headers,
        json=dict(_OBSERVATION_PAYLOAD),
    )
    assert ok.status_code == 200

    blocked = test_client.post(
        f"/paper-validation/run-sessions/{session_id}/result",
        headers=trader_headers,
        json=dict(_RESULT_PAYLOAD),
    )
    assert blocked.status_code == 403

    blocked_patch = test_client.patch(
        f"/paper-validation/run-sessions/{session_id}/result",
        headers=trader_headers,
        json={"outcome": "failure"},
    )
    assert blocked_patch.status_code == 403


def test_tenant_isolation(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers_a = _auth(test_client, "session-obs-a@test.example")
    headers_b = _auth(test_client, "session-obs-b@test.example")
    session_id = _start_session(test_client, headers_a, factory)
    test_client.post(
        f"/paper-validation/run-sessions/{session_id}/observations",
        headers=headers_a,
        json=dict(_OBSERVATION_PAYLOAD),
    )

    other_list = test_client.get(
        f"/paper-validation/run-sessions/{session_id}/observations",
        headers=headers_b,
    )
    assert other_list.status_code == 404

    other_result = test_client.get(
        f"/paper-validation/run-sessions/{session_id}/result",
        headers=headers_b,
    )
    assert other_result.status_code == 404


def test_audit_events_emitted(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "session-obs-a@test.example")
    session_id = _start_session(test_client, headers, factory)
    test_client.post(
        f"/paper-validation/run-sessions/{session_id}/observations",
        headers=headers,
        json=dict(_OBSERVATION_PAYLOAD),
    )
    test_client.post(
        f"/paper-validation/run-sessions/{session_id}/result",
        headers=headers,
        json=dict(_RESULT_PAYLOAD),
    )

    audit = test_client.get(
        "/audit/events?event_type=paper_validation_runtime",
        headers=headers,
    )
    assert audit.status_code == 200
    actions = [item.get("redacted_metadata", {}).get("action") for item in audit.json()["items"]]
    assert "paper_validation_session_observation_recorded" in actions
    assert "paper_validation_session_result_recorded" in actions


def test_audit_request_id_fits_column_limit() -> None:
    session_id = uuid.uuid4()
    assert len(f"pv-session-obs-{session_id}") <= 64
    assert len(f"pv-session-result-{session_id}") <= 64


@patch("app.services.telegram_alert_delivery_service.TelegramAlertDeliveryService.deliver_alert")
@patch("app.services.alert_delivery_service.AlertDeliveryService.deliver_alert")
@patch("app.services.execution_service.ExecutionService.place_paper_order")
@patch("app.services.proposal_service.ProposalService.create")
@patch("app.services.approval_service.ApprovalService.create_for_proposal")
@patch("app.services.paper_validation_runtime_service.PaperValidationRuntimeService.tick")
@patch("app.services.paper_validation_runtime_service.PaperValidationRuntimeService.scan")
@patch("app.services.paper_validation_runtime_service.PaperValidationRuntimeService.start")
def test_observation_and_result_do_not_invoke_runtime(
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
    headers = _auth(test_client, "session-obs-a@test.example")
    session_id = _start_session(test_client, headers, factory)
    test_client.post(
        f"/paper-validation/run-sessions/{session_id}/observations",
        headers=headers,
        json=dict(_OBSERVATION_PAYLOAD),
    )
    test_client.post(
        f"/paper-validation/run-sessions/{session_id}/result",
        headers=headers,
        json=dict(_RESULT_PAYLOAD),
    )

    mock_start_run.assert_not_called()
    mock_scan.assert_not_called()
    mock_tick.assert_not_called()
    mock_proposal.assert_not_called()
    mock_approval.assert_not_called()
    mock_execute.assert_not_called()
    mock_deliver.assert_not_called()
    mock_telegram.assert_not_called()

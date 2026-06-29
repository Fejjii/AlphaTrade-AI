"""Slice 82 — manual paper validation run session endpoints (record only, no engine)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
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
    Order,
    Organization,
    PaperSignal,
    PaperTrade,
    PaperValidationAlert,
    PaperValidationRun,
    PaperValidationRunSession,
    TradeProposal,
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
from app.security.passwords import hash_password
from app.security.rate_limit import reset_rate_limiter
from app.services.audit_service import AuditService
from app.services.paper_alert_service import PaperAlertService
from app.services.paper_validation_run_session_service import PaperValidationRunSessionService

ORG_A = uuid.UUID("00000000-0000-0000-0000-000000008201")
ORG_B = uuid.UUID("00000000-0000-0000-0000-000000008202")
USER_A = uuid.UUID("00000000-0000-0000-0000-000000008211")
USER_B = uuid.UUID("00000000-0000-0000-0000-000000008212")
USER_T = uuid.UUID("00000000-0000-0000-0000-000000008213")  # trader (non-owner) in ORG_A

_BASE = {
    "environment": "local",
    "log_json": False,
    "execution_mode": "paper",
    "enable_real_trading": False,
    "database_url": "sqlite+pysqlite:///:memory:",
    "jwt_secret": "paper-validation-run-session-secret-32",
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
    "thesis": "Ready thesis for run session.",
    "entry_criteria": "Entry rules for run session.",
    "invalidation_criteria": "Invalidation rules for run session.",
    "risk_notes": "Conservative run session prep.",
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

_START_PAYLOAD = {
    "confirm": START_PAPER_VALIDATION_RUN_CONFIRM,
    "notes": "Manual observation start.",
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
        session.add(Organization(id=ORG_A, name="Run Session Org A"))
        session.add(Organization(id=ORG_B, name="Run Session Org B"))
        for user_id, email in (
            (USER_A, "run-session-a@test.example"),
            (USER_B, "run-session-b@test.example"),
            (USER_T, "run-session-trader@test.example"),
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
            "notes": "Run session test",
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


def test_exact_confirmation_required(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "run-session-a@test.example")
    plan_id = _create_planned_plan(test_client, headers, factory)

    response = test_client.post(
        f"/paper-validation/run-plans/{plan_id}/start",
        headers=headers,
        json={"confirm": "WRONG"},
    )
    assert response.status_code == 422
    assert "confirmation required" in response.json()["error"]["message"].lower()
    with factory() as session:
        count = session.scalar(select(func.count()).select_from(PaperValidationRunSession)) or 0
        assert count == 0


def test_cannot_start_unless_plan_planned(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "run-session-a@test.example")

    for blocking_status in ("needs_revision", "archived"):
        plan_id = _create_planned_plan(test_client, headers, factory)
        moved = test_client.patch(
            f"/paper-validation/run-plans/{plan_id}",
            headers=headers,
            json={"plan_status": blocking_status},
        )
        assert moved.status_code == 200, moved.text

        response = test_client.post(
            f"/paper-validation/run-plans/{plan_id}/start",
            headers=headers,
            json=dict(_START_PAYLOAD),
        )
        assert response.status_code == 422, response.text
        assert "planned" in response.json()["error"]["message"].lower()

    with factory() as session:
        count = session.scalar(select(func.count()).select_from(PaperValidationRunSession)) or 0
        assert count == 0


def test_start_from_planned_creates_session(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "run-session-a@test.example")
    plan_id = _create_planned_plan(test_client, headers, factory)

    response = test_client.post(
        f"/paper-validation/run-plans/{plan_id}/start",
        headers=headers,
        json=dict(_START_PAYLOAD),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["already_active"] is False
    session_obj = body["session"]
    assert session_obj["session_status"] == "running"
    assert session_obj["run_plan_id"] == plan_id
    assert session_obj["symbol"] == "BTCUSDT"
    assert session_obj["timeframe"] == "15m"
    assert session_obj["condition"] == "order_block"
    assert session_obj["validation_window"] == "intraday"
    assert session_obj["candidate_id"]
    assert session_obj["draft_id"]
    assert session_obj["source_alert_id"]
    assert session_obj["started_at"] is not None


def test_duplicate_active_session_prevented(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "run-session-a@test.example")
    plan_id = _create_planned_plan(test_client, headers, factory)

    first = test_client.post(
        f"/paper-validation/run-plans/{plan_id}/start",
        headers=headers,
        json=dict(_START_PAYLOAD),
    )
    second = test_client.post(
        f"/paper-validation/run-plans/{plan_id}/start",
        headers=headers,
        json={"confirm": START_PAPER_VALIDATION_RUN_CONFIRM, "notes": "Second attempt."},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["already_active"] is True
    assert second.json()["session"]["session_id"] == first.json()["session"]["session_id"]

    with factory() as session:
        count = session.scalar(select(func.count()).select_from(PaperValidationRunSession)) or 0
        assert count == 1


def test_list_read_tenant_scoped(client: tuple[TestClient, sessionmaker[Session]]) -> None:
    test_client, factory = client
    headers_a = _auth(test_client, "run-session-a@test.example")
    headers_b = _auth(test_client, "run-session-b@test.example")
    plan_id = _create_planned_plan(test_client, headers_a, factory)
    created = test_client.post(
        f"/paper-validation/run-plans/{plan_id}/start",
        headers=headers_a,
        json=dict(_START_PAYLOAD),
    )
    session_id = created.json()["session"]["session_id"]

    listing = test_client.get("/paper-validation/run-sessions", headers=headers_a)
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["session_id"] == session_id

    read = test_client.get(f"/paper-validation/run-sessions/{session_id}", headers=headers_a)
    assert read.status_code == 200
    assert read.json()["symbol"] == "BTCUSDT"

    other_list = test_client.get("/paper-validation/run-sessions", headers=headers_b)
    assert other_list.status_code == 200
    assert other_list.json()["total"] == 0

    other_read = test_client.get(f"/paper-validation/run-sessions/{session_id}", headers=headers_b)
    assert other_read.status_code == 404


def test_status_update_complete_and_cancel(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "run-session-a@test.example")

    # complete
    plan_id = _create_planned_plan(test_client, headers, factory)
    created = test_client.post(
        f"/paper-validation/run-plans/{plan_id}/start",
        headers=headers,
        json=dict(_START_PAYLOAD),
    )
    session_id = created.json()["session"]["session_id"]
    completed = test_client.patch(
        f"/paper-validation/run-sessions/{session_id}",
        headers=headers,
        json={"session_status": "completed"},
    )
    assert completed.status_code == 200
    assert completed.json()["session_status"] == "completed"
    assert completed.json()["ended_at"] is not None
    fresh = test_client.get(f"/paper-validation/run-sessions/{session_id}", headers=headers)
    assert fresh.json()["session_status"] == "completed"

    # cancel a second session
    plan_id_2 = _create_planned_plan(test_client, headers, factory)
    created_2 = test_client.post(
        f"/paper-validation/run-plans/{plan_id_2}/start",
        headers=headers,
        json=dict(_START_PAYLOAD),
    )
    session_id_2 = created_2.json()["session"]["session_id"]
    cancelled = test_client.patch(
        f"/paper-validation/run-sessions/{session_id_2}",
        headers=headers,
        json={"session_status": "cancelled"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["session_status"] == "cancelled"


def test_invalid_status_rejected(client: tuple[TestClient, sessionmaker[Session]]) -> None:
    test_client, factory = client
    headers = _auth(test_client, "run-session-a@test.example")
    plan_id = _create_planned_plan(test_client, headers, factory)
    created = test_client.post(
        f"/paper-validation/run-plans/{plan_id}/start",
        headers=headers,
        json=dict(_START_PAYLOAD),
    )
    session_id = created.json()["session"]["session_id"]

    response = test_client.patch(
        f"/paper-validation/run-sessions/{session_id}",
        headers=headers,
        json={"session_status": "running"},
    )
    assert response.status_code == 422


def test_completing_after_terminal_rejected(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "run-session-a@test.example")
    plan_id = _create_planned_plan(test_client, headers, factory)
    created = test_client.post(
        f"/paper-validation/run-plans/{plan_id}/start",
        headers=headers,
        json=dict(_START_PAYLOAD),
    )
    session_id = created.json()["session"]["session_id"]
    test_client.patch(
        f"/paper-validation/run-sessions/{session_id}",
        headers=headers,
        json={"session_status": "completed"},
    )
    again = test_client.patch(
        f"/paper-validation/run-sessions/{session_id}",
        headers=headers,
        json={"session_status": "cancelled"},
    )
    assert again.status_code == 422


def test_can_restart_after_session_completed(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "run-session-a@test.example")
    plan_id = _create_planned_plan(test_client, headers, factory)
    first = test_client.post(
        f"/paper-validation/run-plans/{plan_id}/start",
        headers=headers,
        json=dict(_START_PAYLOAD),
    )
    session_id = first.json()["session"]["session_id"]
    test_client.patch(
        f"/paper-validation/run-sessions/{session_id}",
        headers=headers,
        json={"session_status": "completed"},
    )

    second = test_client.post(
        f"/paper-validation/run-plans/{plan_id}/start",
        headers=headers,
        json=dict(_START_PAYLOAD),
    )
    assert second.status_code == 200
    assert second.json()["already_active"] is False
    assert second.json()["session"]["session_id"] != session_id


def test_rbac_non_owner_blocked(client: tuple[TestClient, sessionmaker[Session]]) -> None:
    test_client, factory = client
    owner_headers = _auth(test_client, "run-session-a@test.example")
    trader_headers = _auth(test_client, "run-session-trader@test.example")
    plan_id = _create_planned_plan(test_client, owner_headers, factory)

    blocked_start = test_client.post(
        f"/paper-validation/run-plans/{plan_id}/start",
        headers=trader_headers,
        json=dict(_START_PAYLOAD),
    )
    assert blocked_start.status_code == 403

    # trader can still read (ReaderDep)
    listing = test_client.get("/paper-validation/run-sessions", headers=trader_headers)
    assert listing.status_code == 200

    # owner starts, trader cannot patch status
    created = test_client.post(
        f"/paper-validation/run-plans/{plan_id}/start",
        headers=owner_headers,
        json=dict(_START_PAYLOAD),
    )
    session_id = created.json()["session"]["session_id"]
    blocked_patch = test_client.patch(
        f"/paper-validation/run-sessions/{session_id}",
        headers=trader_headers,
        json={"session_status": "completed"},
    )
    assert blocked_patch.status_code == 403


def test_audit_events_emitted(client: tuple[TestClient, sessionmaker[Session]]) -> None:
    test_client, factory = client
    headers = _auth(test_client, "run-session-a@test.example")
    plan_id = _create_planned_plan(test_client, headers, factory)
    test_client.post(
        f"/paper-validation/run-plans/{plan_id}/start",
        headers=headers,
        json=dict(_START_PAYLOAD),
    )

    audit = test_client.get(
        "/audit/events?event_type=paper_validation_runtime",
        headers=headers,
    )
    assert audit.status_code == 200
    actions = [item.get("redacted_metadata", {}).get("action") for item in audit.json()["items"]]
    assert "paper_validation_run_session_requested" in actions
    assert "paper_validation_run_session_started" in actions


@patch("app.services.telegram_alert_delivery_service.TelegramAlertDeliveryService.deliver_alert")
@patch("app.services.alert_delivery_service.AlertDeliveryService.deliver_alert")
@patch("app.services.execution_service.ExecutionService.place_paper_order")
@patch("app.services.proposal_service.ProposalService.create")
@patch("app.services.approval_service.ApprovalService.create_for_proposal")
@patch("app.services.paper_validation_runtime_service.PaperValidationRuntimeService.tick")
@patch("app.services.paper_validation_runtime_service.PaperValidationRuntimeService.scan")
@patch("app.services.paper_validation_runtime_service.PaperValidationRuntimeService.start")
def test_start_does_not_invoke_runtime_or_create_runs(
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
    headers = _auth(test_client, "run-session-a@test.example")
    plan_id = _create_planned_plan(test_client, headers, factory)

    response = test_client.post(
        f"/paper-validation/run-plans/{plan_id}/start",
        headers=headers,
        json=dict(_START_PAYLOAD),
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

    with factory() as session:
        assert (session.scalar(select(func.count()).select_from(PaperValidationRun)) or 0) == 0
        assert (session.scalar(select(func.count()).select_from(PaperSignal)) or 0) == 0
        assert (session.scalar(select(func.count()).select_from(PaperTrade)) or 0) == 0
        assert (session.scalar(select(func.count()).select_from(TradeProposal)) or 0) == 0
        assert (session.scalar(select(func.count()).select_from(Order)) or 0) == 0
        # the record-only session row is the only artifact created
        assert (
            session.scalar(select(func.count()).select_from(PaperValidationRunSession)) or 0
        ) == 1


def test_sanitize_audit_metadata_converts_non_json_types() -> None:
    nested_uuid = uuid.uuid4()
    sanitized = PaperValidationRunSessionService._sanitize_audit_metadata(
        {
            "session_id": nested_uuid,
            "started_at": datetime(2026, 6, 29, 12, 0, tzinfo=UTC),
            "confidence": Decimal("0.85"),
            "nested": {"plan_id": nested_uuid},
        }
    )
    assert sanitized["session_id"] == str(nested_uuid)
    assert sanitized["started_at"] == "2026-06-29T12:00:00+00:00"
    assert sanitized["confidence"] == 0.85
    assert sanitized["nested"] == {"plan_id": str(nested_uuid)}


def test_session_persists_when_started_audit_record_fails(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "run-session-a@test.example")
    plan_id = _create_planned_plan(test_client, headers, factory)
    original_record = AuditService.record

    def _record_with_started_failure(self: AuditService, data: object) -> object:
        from app.schemas.audit import AuditRecordCreate

        assert isinstance(data, AuditRecordCreate)
        if data.metadata.get("action") == "paper_validation_run_session_started":
            if self._session is not None:
                self._session.rollback()
            return None
        return original_record(self, data)  # type: ignore[arg-type]

    with patch.object(AuditService, "record", _record_with_started_failure):
        response = test_client.post(
            f"/paper-validation/run-plans/{plan_id}/start",
            headers=headers,
            json=dict(_START_PAYLOAD),
        )
    assert response.status_code == 200, response.text
    session_id = uuid.UUID(response.json()["session"]["session_id"])

    with factory() as session:
        row = session.get(PaperValidationRunSession, session_id)
        assert row is not None
        assert row.session_status == "running"


def test_start_persists_across_fresh_db_connection(tmp_path: Path) -> None:
    db_path = tmp_path / "slice82_run_session.db"
    engine = create_engine(
        f"sqlite+pysqlite:///{db_path}",
        connect_args={"check_same_thread": False},
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
        session.add(Organization(id=ORG_A, name="Run Session Org A"))
        session.add(
            User(
                id=USER_A,
                email="run-session-file@test.example",
                hashed_password=hash_password("SecurePass123!", settings),
                email_verified=True,
            )
        )
        session.flush()
        session.add(Membership(user_id=USER_A, organization_id=ORG_A, role=MembershipRole.OWNER))
        session.commit()

    app = create_app(settings=settings)

    def _override_session() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = _override_session

    with TestClient(app) as test_client:
        headers = _auth(test_client, "run-session-file@test.example")
        plan_id = _create_planned_plan(test_client, headers, factory)
        first = test_client.post(
            f"/paper-validation/run-plans/{plan_id}/start",
            headers=headers,
            json=dict(_START_PAYLOAD),
        )
        assert first.status_code == 200, first.text
        session_id = first.json()["session"]["session_id"]

        second = test_client.post(
            f"/paper-validation/run-plans/{plan_id}/start",
            headers=headers,
            json={"confirm": START_PAPER_VALIDATION_RUN_CONFIRM, "notes": "Second attempt."},
        )
        assert second.status_code == 200
        assert second.json()["already_active"] is True
        assert second.json()["session"]["session_id"] == session_id

        listing = test_client.get("/paper-validation/run-sessions", headers=headers)
        assert listing.status_code == 200
        assert listing.json()["total"] == 1

        read = test_client.get(f"/paper-validation/run-sessions/{session_id}", headers=headers)
        assert read.status_code == 200

    fresh_engine = create_engine(
        f"sqlite+pysqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    fresh_factory = sessionmaker(bind=fresh_engine, expire_on_commit=False)
    with fresh_factory() as session:
        count = session.scalar(select(func.count()).select_from(PaperValidationRunSession)) or 0
        assert count == 1
        row = session.scalar(
            select(PaperValidationRunSession).where(
                PaperValidationRunSession.id == uuid.UUID(session_id)
            )
        )
        assert row is not None
        assert row.session_status == "running"
    fresh_engine.dispose()
    app.dependency_overrides.clear()
    engine.dispose()

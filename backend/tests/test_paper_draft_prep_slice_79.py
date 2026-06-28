"""Slice 79 — paper validation draft prep workflow endpoints."""

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
from app.db.models import Membership, Organization, PaperValidationAlert, PaperValidationDraft, User
from app.db.session import get_session
from app.main import create_app
from app.schemas.common import (
    MembershipRole,
    PaperAlertSource,
    PaperAlertType,
    SetupAlertReviewStatus,
)
from app.schemas.paper_validation_draft import (
    CREATE_PAPER_VALIDATION_DRAFT_CONFIRM,
    PAPER_VALIDATION_DRAFT_PREP_FIELD_MAX,
)
from app.security.passwords import hash_password
from app.security.rate_limit import reset_rate_limiter
from app.services.paper_alert_service import PaperAlertService

ORG_A = uuid.UUID("00000000-0000-0000-0000-000000007901")
ORG_B = uuid.UUID("00000000-0000-0000-0000-000000007802")
USER_A = uuid.UUID("00000000-0000-0000-0000-000000007811")
USER_B = uuid.UUID("00000000-0000-0000-0000-000000007812")

_BASE = {
    "environment": "local",
    "log_json": False,
    "execution_mode": "paper",
    "enable_real_trading": False,
    "database_url": "sqlite+pysqlite:///:memory:",
    "jwt_secret": "paper-draft-prep-secret-min-32",
    "rate_limit_use_redis": False,
    "access_token_denylist_use_redis": False,
    "provider_mode": "mock",
    "market_data_provider": "mock",
    "alert_delivery_enabled": False,
    "telegram_alerts_enabled": False,
    "worker_enabled": False,
    "market_watcher_enabled": False,
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
        session.add(Organization(id=ORG_A, name="Prep Org A"))
        session.add(Organization(id=ORG_B, name="Prep Org B"))
        session.add(
            User(
                id=USER_A,
                email="prep-a@test.example",
                hashed_password=hash_password("SecurePass123!", settings),
                email_verified=True,
            )
        )
        session.add(
            User(
                id=USER_B,
                email="prep-b@test.example",
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
    review_status: str = SetupAlertReviewStatus.WATCHING.value,
    condition: str = "order_block",
) -> uuid.UUID:
    with factory() as session:
        service = PaperAlertService(session)
        created = service.create(
            organization_id=organization_id,
            user_id=user_id,
            alert_type=PaperAlertType.SETUP_SIGNAL_DETECTED,
            message=f"{condition} on BTCUSDT 15m",
            metadata={
                "source": PaperAlertSource.MARKET_WATCHER.value,
                "condition": condition,
                "symbol": "BTCUSDT",
                "timeframe": "15m",
                "direction": "long",
                "confidence": 0.85,
                "reason": "Clean retest setup.",
                "trigger_level": 65000.0,
                "invalidation_level": 64000.0,
                "metrics": {"latest_price": 65100.0},
            },
            dedup_key=f"test:{condition}:{uuid.uuid4()}",
            skip_dedup=True,
            source=PaperAlertSource.MARKET_WATCHER,
        )
        assert created is not None
        row = session.scalar(
            select(PaperValidationAlert).where(PaperValidationAlert.id == created.id)
        )
        assert row is not None
        row.review_status = review_status
        alert_id = row.id
        session.commit()
        return alert_id


def _create_draft(
    client: TestClient, headers: dict[str, str], factory: sessionmaker[Session]
) -> str:
    alert_id = _create_market_watcher_alert(factory)
    response = client.post(
        f"/alerts/setup-review/{alert_id}/draft",
        headers=headers,
        json={
            "confirm": CREATE_PAPER_VALIDATION_DRAFT_CONFIRM,
            "notes": "Initial draft notes",
            "risk_mode": "conservative",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["draft"]["draft_id"]


def _ready_prep_payload() -> dict[str, object]:
    return {
        "prep_status": "ready_for_validation",
        "thesis": "BTCUSDT long retest into order block.",
        "entry_criteria": "15m close above trigger with volume confirmation.",
        "invalidation_criteria": "15m close below invalidation level.",
        "risk_notes": "Size conservatively; no add-ons until structure confirms.",
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


def test_prep_update_works(client: tuple[TestClient, sessionmaker[Session]]) -> None:
    test_client, factory = client
    headers = _auth(test_client, "prep-a@test.example")
    draft_id = _create_draft(test_client, headers, factory)

    response = test_client.patch(
        f"/paper-validation/drafts/{draft_id}/prep",
        headers=headers,
        json={
            "thesis": "Bullish continuation thesis.",
            "entry_criteria": "Wait for reclaim of trigger.",
            "checklist": {"trend_checked": True},
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["thesis"] == "Bullish continuation thesis."
    assert body["entry_criteria"] == "Wait for reclaim of trigger."
    assert body["checklist"]["trend_checked"] is True
    assert body["prep_status"] == "draft"
    assert body["is_ready_for_validation"] is False
    assert body["prep_completion_score"] > 0


def test_prep_update_tenant_isolated(client: tuple[TestClient, sessionmaker[Session]]) -> None:
    test_client, factory = client
    headers_a = _auth(test_client, "prep-a@test.example")
    headers_b = _auth(test_client, "prep-b@test.example")
    draft_id = _create_draft(test_client, headers_a, factory)

    blocked = test_client.patch(
        f"/paper-validation/drafts/{draft_id}/prep",
        headers=headers_b,
        json={"thesis": "Cross-tenant attempt."},
    )
    assert blocked.status_code == 404


def test_invalid_prep_status_rejected(client: tuple[TestClient, sessionmaker[Session]]) -> None:
    test_client, factory = client
    headers = _auth(test_client, "prep-a@test.example")
    draft_id = _create_draft(test_client, headers, factory)

    response = test_client.patch(
        f"/paper-validation/drafts/{draft_id}/prep",
        headers=headers,
        json={"prep_status": "not_a_status"},
    )
    assert response.status_code == 422


def test_prep_notes_length_enforced(client: tuple[TestClient, sessionmaker[Session]]) -> None:
    test_client, factory = client
    headers = _auth(test_client, "prep-a@test.example")
    draft_id = _create_draft(test_client, headers, factory)

    response = test_client.patch(
        f"/paper-validation/drafts/{draft_id}/prep",
        headers=headers,
        json={"thesis": "x" * (PAPER_VALIDATION_DRAFT_PREP_FIELD_MAX + 1)},
    )
    assert response.status_code == 422


def test_readiness_false_when_required_fields_missing(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "prep-a@test.example")
    draft_id = _create_draft(test_client, headers, factory)

    response = test_client.patch(
        f"/paper-validation/drafts/{draft_id}/prep",
        headers=headers,
        json={"prep_status": "ready_for_validation", "thesis": "Only thesis provided."},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_ready_for_validation"] is False
    assert body["missing_checklist_items"]


def test_readiness_true_when_required_fields_and_checklist_complete(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "prep-a@test.example")
    draft_id = _create_draft(test_client, headers, factory)

    response = test_client.patch(
        f"/paper-validation/drafts/{draft_id}/prep",
        headers=headers,
        json=_ready_prep_payload(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_ready_for_validation"] is True
    assert body["prep_completion_score"] == 100
    assert body["missing_checklist_items"] == []


def test_summary_includes_ready_counts(client: tuple[TestClient, sessionmaker[Session]]) -> None:
    test_client, factory = client
    headers = _auth(test_client, "prep-a@test.example")
    draft_id = _create_draft(test_client, headers, factory)
    test_client.patch(
        f"/paper-validation/drafts/{draft_id}/prep",
        headers=headers,
        json=_ready_prep_payload(),
    )

    summary = test_client.get("/paper-validation/drafts/summary", headers=headers)
    assert summary.status_code == 200
    body = summary.json()
    assert body["total_drafts"] == 1
    assert body["ready_for_validation_count"] == 1


def test_prep_update_emits_audit_events(client: tuple[TestClient, sessionmaker[Session]]) -> None:
    test_client, factory = client
    headers = _auth(test_client, "prep-a@test.example")
    draft_id = _create_draft(test_client, headers, factory)
    test_client.patch(
        f"/paper-validation/drafts/{draft_id}/prep",
        headers=headers,
        json=_ready_prep_payload(),
    )

    audit = test_client.get(
        "/audit/events?event_type=paper_validation_runtime",
        headers=headers,
    )
    assert audit.status_code == 200
    actions = [item.get("redacted_metadata", {}).get("action") for item in audit.json()["items"]]
    assert "paper_draft_prep_updated" in actions
    assert "paper_draft_marked_ready" in actions


def test_blocked_prep_emits_blocked_audit(client: tuple[TestClient, sessionmaker[Session]]) -> None:
    test_client, factory = client
    headers = _auth(test_client, "prep-a@test.example")
    draft_id = _create_draft(test_client, headers, factory)

    with factory() as session:
        row = session.scalar(
            select(PaperValidationDraft).where(PaperValidationDraft.id == uuid.UUID(draft_id))
        )
        assert row is not None
        row.status = "archived"
        session.commit()

    response = test_client.patch(
        f"/paper-validation/drafts/{draft_id}/prep",
        headers=headers,
        json={"thesis": "Should be blocked."},
    )
    assert response.status_code == 422

    audit = test_client.get(
        "/audit/events?event_type=paper_validation_runtime",
        headers=headers,
    )
    actions = [item.get("redacted_metadata", {}).get("action") for item in audit.json()["items"]]
    assert "paper_draft_prep_blocked" in actions


@patch("app.services.telegram_alert_delivery_service.TelegramAlertDeliveryService.deliver_alert")
@patch("app.services.alert_delivery_service.AlertDeliveryService.deliver_alert")
@patch("app.services.execution_service.ExecutionService.place_paper_order")
@patch("app.services.proposal_service.ProposalService.create")
@patch("app.services.approval_service.ApprovalService.create_for_proposal")
def test_prep_update_does_not_execute_or_deliver(
    mock_approval: object,
    mock_proposal: object,
    mock_execute: object,
    mock_deliver: object,
    mock_telegram: object,
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "prep-a@test.example")
    draft_id = _create_draft(test_client, headers, factory)

    response = test_client.patch(
        f"/paper-validation/drafts/{draft_id}/prep",
        headers=headers,
        json=_ready_prep_payload(),
    )
    assert response.status_code == 200

    mock_execute.assert_not_called()
    mock_proposal.assert_not_called()
    mock_approval.assert_not_called()
    mock_deliver.assert_not_called()
    mock_telegram.assert_not_called()


def test_prep_update_no_proposal_approval_or_order_rows(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "prep-a@test.example")
    draft_id = _create_draft(test_client, headers, factory)

    before = _count_rows(factory, PaperValidationDraft)
    response = test_client.patch(
        f"/paper-validation/drafts/{draft_id}/prep",
        headers=headers,
        json=_ready_prep_payload(),
    )
    assert response.status_code == 200
    after = _count_rows(factory, PaperValidationDraft)
    assert after == before


def _count_rows(factory: sessionmaker[Session], model: type[object]) -> int:
    with factory() as session:
        return int(session.scalar(select(func.count()).select_from(model)) or 0)

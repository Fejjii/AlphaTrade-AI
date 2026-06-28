"""Slice 78 — setup alert paper validation draft endpoints."""

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
from app.schemas.paper_validation_draft import CREATE_PAPER_VALIDATION_DRAFT_CONFIRM
from app.security.passwords import hash_password
from app.security.rate_limit import reset_rate_limiter
from app.services.paper_alert_service import PaperAlertService

ORG_A = uuid.UUID("00000000-0000-0000-0000-000000007801")
ORG_B = uuid.UUID("00000000-0000-0000-0000-000000007802")
USER_A = uuid.UUID("00000000-0000-0000-0000-000000007811")
USER_B = uuid.UUID("00000000-0000-0000-0000-000000007812")

_BASE = {
    "environment": "local",
    "log_json": False,
    "execution_mode": "paper",
    "enable_real_trading": False,
    "database_url": "sqlite+pysqlite:///:memory:",
    "jwt_secret": "setup-alert-draft-secret-min-32",
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
        session.add(Organization(id=ORG_A, name="Draft Org A"))
        session.add(Organization(id=ORG_B, name="Draft Org B"))
        session.add(
            User(
                id=USER_A,
                email="draft-a@test.example",
                hashed_password=hash_password("SecurePass123!", settings),
                email_verified=True,
            )
        )
        session.add(
            User(
                id=USER_B,
                email="draft-b@test.example",
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
    review_status: str = SetupAlertReviewStatus.UNREVIEWED.value,
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


def _create_runtime_alert(factory: sessionmaker[Session]) -> uuid.UUID:
    with factory() as session:
        service = PaperAlertService(session)
        created = service.create(
            organization_id=ORG_A,
            user_id=USER_A,
            alert_type=PaperAlertType.SETUP_SIGNAL_DETECTED,
            message="Runtime setup signal",
            metadata={"source": PaperAlertSource.PAPER_VALIDATION_RUNTIME.value},
            skip_dedup=True,
        )
        assert created is not None
        alert_id = created.id
        session.commit()
        return alert_id


def _draft_payload(**overrides: object) -> dict[str, object]:
    payload = {
        "confirm": CREATE_PAPER_VALIDATION_DRAFT_CONFIRM,
        "notes": "Draft notes",
        "risk_mode": "conservative",
    }
    payload.update(overrides)
    return payload


def _set_review_status(
    client: TestClient,
    headers: dict[str, str],
    alert_id: uuid.UUID,
    review_status: SetupAlertReviewStatus,
) -> None:
    response = client.patch(
        f"/alerts/setup-review/{alert_id}",
        headers=headers,
        json={"review_status": review_status.value},
    )
    assert response.status_code == 200, response.text


@pytest.mark.parametrize(
    "review_status",
    [
        SetupAlertReviewStatus.UNREVIEWED,
        SetupAlertReviewStatus.IGNORED,
    ],
)
def test_cannot_draft_non_draftable_review_status(
    client: tuple[TestClient, sessionmaker[Session]],
    review_status: SetupAlertReviewStatus,
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "draft-a@test.example")
    alert_id = _create_market_watcher_alert(factory, review_status=review_status.value)

    response = test_client.post(
        f"/alerts/setup-review/{alert_id}/draft",
        headers=headers,
        json=_draft_payload(),
    )
    assert response.status_code == 422
    assert "watching or important" in response.json()["error"]["message"].lower()


@pytest.mark.parametrize(
    "review_status",
    [
        SetupAlertReviewStatus.WATCHING,
        SetupAlertReviewStatus.IMPORTANT,
    ],
)
def test_can_draft_watching_or_important_alert(
    client: tuple[TestClient, sessionmaker[Session]],
    review_status: SetupAlertReviewStatus,
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "draft-a@test.example")
    alert_id = _create_market_watcher_alert(factory, review_status=review_status.value)

    response = test_client.post(
        f"/alerts/setup-review/{alert_id}/draft",
        headers=headers,
        json=_draft_payload(),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["already_exists"] is False
    assert body["draft"]["source_alert_id"] == str(alert_id)
    assert body["draft"]["status"] == "draft"
    assert body["draft"]["condition"] == "order_block"
    assert body["draft"]["risk_mode"] == "conservative"


def test_exact_confirmation_required(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "draft-a@test.example")
    alert_id = _create_market_watcher_alert(
        factory, review_status=SetupAlertReviewStatus.WATCHING.value
    )

    response = test_client.post(
        f"/alerts/setup-review/{alert_id}/draft",
        headers=headers,
        json=_draft_payload(confirm="WRONG"),
    )
    assert response.status_code == 422
    assert "confirmation required" in response.json()["error"]["message"].lower()


def test_non_market_watcher_alert_rejected(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "draft-a@test.example")
    alert_id = _create_runtime_alert(factory)

    response = test_client.post(
        f"/alerts/setup-review/{alert_id}/draft",
        headers=headers,
        json=_draft_payload(),
    )
    assert response.status_code == 422
    assert "scanner-created setup alerts" in response.json()["error"]["message"].lower()


def test_duplicate_draft_returns_existing(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "draft-a@test.example")
    alert_id = _create_market_watcher_alert(
        factory, review_status=SetupAlertReviewStatus.IMPORTANT.value
    )

    first = test_client.post(
        f"/alerts/setup-review/{alert_id}/draft",
        headers=headers,
        json=_draft_payload(),
    )
    assert first.status_code == 200
    draft_id = first.json()["draft"]["draft_id"]

    second = test_client.post(
        f"/alerts/setup-review/{alert_id}/draft",
        headers=headers,
        json=_draft_payload(notes="Different notes"),
    )
    assert second.status_code == 200
    body = second.json()
    assert body["already_exists"] is True
    assert body["draft"]["draft_id"] == draft_id


def test_draft_list_and_read_tenant_scoped(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers_a = _auth(test_client, "draft-a@test.example")
    headers_b = _auth(test_client, "draft-b@test.example")
    alert_id = _create_market_watcher_alert(
        factory, review_status=SetupAlertReviewStatus.WATCHING.value
    )

    created = test_client.post(
        f"/alerts/setup-review/{alert_id}/draft",
        headers=headers_a,
        json=_draft_payload(),
    )
    draft_id = created.json()["draft"]["draft_id"]

    listing = test_client.get("/paper-validation/drafts", headers=headers_a)
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["draft_id"] == draft_id

    read = test_client.get(f"/paper-validation/drafts/{draft_id}", headers=headers_a)
    assert read.status_code == 200
    assert read.json()["symbol"] == "BTCUSDT"

    other_list = test_client.get("/paper-validation/drafts", headers=headers_b)
    assert other_list.status_code == 200
    assert other_list.json()["total"] == 0

    other_read = test_client.get(f"/paper-validation/drafts/{draft_id}", headers=headers_b)
    assert other_read.status_code == 404


def test_draft_summary_endpoint(client: tuple[TestClient, sessionmaker[Session]]) -> None:
    test_client, factory = client
    headers = _auth(test_client, "draft-a@test.example")
    alert_id = _create_market_watcher_alert(
        factory,
        review_status=SetupAlertReviewStatus.WATCHING.value,
        condition="breakout_retest",
    )
    test_client.post(
        f"/alerts/setup-review/{alert_id}/draft",
        headers=headers,
        json=_draft_payload(),
    )

    summary = test_client.get("/paper-validation/drafts/summary", headers=headers)
    assert summary.status_code == 200
    body = summary.json()
    assert body["total_drafts"] == 1
    assert body["latest_condition"] == "breakout_retest"


@patch("app.services.telegram_alert_delivery_service.TelegramAlertDeliveryService.deliver_alert")
@patch("app.services.alert_delivery_service.AlertDeliveryService.deliver_alert")
@patch("app.services.execution_service.ExecutionService.place_paper_order")
@patch("app.services.proposal_service.ProposalService.create")
@patch("app.services.approval_service.ApprovalService.create_for_proposal")
def test_draft_creation_does_not_execute_or_deliver(
    mock_approval: object,
    mock_proposal: object,
    mock_execute: object,
    mock_deliver: object,
    mock_telegram: object,
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "draft-a@test.example")
    alert_id = _create_market_watcher_alert(
        factory, review_status=SetupAlertReviewStatus.WATCHING.value
    )

    response = test_client.post(
        f"/alerts/setup-review/{alert_id}/draft",
        headers=headers,
        json=_draft_payload(),
    )
    assert response.status_code == 200

    mock_execute.assert_not_called()
    mock_proposal.assert_not_called()
    mock_approval.assert_not_called()
    mock_deliver.assert_not_called()
    mock_telegram.assert_not_called()


def test_draft_creation_emits_audit_events(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "draft-a@test.example")
    alert_id = _create_market_watcher_alert(
        factory, review_status=SetupAlertReviewStatus.IMPORTANT.value
    )

    response = test_client.post(
        f"/alerts/setup-review/{alert_id}/draft",
        headers=headers,
        json=_draft_payload(),
    )
    assert response.status_code == 200

    audit = test_client.get(
        "/audit/events?event_type=paper_validation_runtime",
        headers=headers,
    )
    assert audit.status_code == 200
    actions = [item.get("redacted_metadata", {}).get("action") for item in audit.json()["items"]]
    assert "setup_alert_draft_requested" in actions
    assert "setup_alert_draft_created" in actions


def test_duplicate_draft_emits_already_exists_audit(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "draft-a@test.example")
    alert_id = _create_market_watcher_alert(
        factory, review_status=SetupAlertReviewStatus.WATCHING.value
    )
    test_client.post(
        f"/alerts/setup-review/{alert_id}/draft",
        headers=headers,
        json=_draft_payload(),
    )
    test_client.post(
        f"/alerts/setup-review/{alert_id}/draft",
        headers=headers,
        json=_draft_payload(),
    )

    audit = test_client.get(
        "/audit/events?event_type=paper_validation_runtime",
        headers=headers,
    )
    actions = [item.get("redacted_metadata", {}).get("action") for item in audit.json()["items"]]
    assert "setup_alert_draft_already_exists" in actions


def test_blocked_draft_emits_blocked_audit(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "draft-a@test.example")
    alert_id = _create_market_watcher_alert(factory)

    test_client.post(
        f"/alerts/setup-review/{alert_id}/draft",
        headers=headers,
        json=_draft_payload(),
    )

    audit = test_client.get(
        "/audit/events?event_type=paper_validation_runtime",
        headers=headers,
    )
    actions = [item.get("redacted_metadata", {}).get("action") for item in audit.json()["items"]]
    assert "setup_alert_draft_blocked" in actions


def test_no_order_proposal_or_approval_rows_created(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "draft-a@test.example")
    alert_id = _create_market_watcher_alert(
        factory, review_status=SetupAlertReviewStatus.WATCHING.value
    )

    before = _count_rows(factory, PaperValidationDraft)
    response = test_client.post(
        f"/alerts/setup-review/{alert_id}/draft",
        headers=headers,
        json=_draft_payload(),
    )
    assert response.status_code == 200
    after = _count_rows(factory, PaperValidationDraft)
    assert after == before + 1


def _count_rows(factory: sessionmaker[Session], model: type[object]) -> int:
    with factory() as session:
        return int(session.scalar(select(func.count()).select_from(model)) or 0)

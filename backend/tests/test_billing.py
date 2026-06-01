"""Slice 26 — billing scaffold, mock provider, usage export, webhooks."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from collections.abc import Iterator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db.models import Membership, Organization, OrganizationQuota, User
from app.db.session import get_session
from app.guardrails.redaction import redact_text
from app.main import create_app
from app.providers.billing.factory import reset_billing_provider_for_tests
from app.schemas.common import CostSource, MembershipRole
from app.schemas.usage import UsageEventCreate
from app.services.billing_service import BillingService
from app.services.usage_service import UsageService

_PASSWORD = "secure-password-1"


@pytest.fixture
def db_session() -> Iterator[Session]:
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
    with factory() as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def api_client(db_session: Session) -> Iterator[TestClient]:
    settings = Settings(
        execution_mode="paper",
        enable_real_trading=False,
        log_json=False,
        billing_enabled=False,
    )
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_session] = lambda: db_session
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    get_settings.cache_clear()
    reset_billing_provider_for_tests()


def _register(client: TestClient, email: str) -> str:
    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": _PASSWORD,
            "organization_name": f"Org-{email.split('@')[0]}",
        },
    )
    assert response.status_code in (200, 201), response.text
    return response.json()["tokens"]["access_token"]


def test_mock_billing_provider_status(api_client: TestClient) -> None:
    response = api_client.get("/providers/status")
    assert response.status_code == 200
    billing = next(p for p in response.json()["providers"] if p["kind"] == "billing")
    assert billing["name"] == "mock-billing"
    assert billing["is_mock"] is True


def test_billing_disabled_by_default(api_client: TestClient) -> None:
    token = _register(api_client, "billing-status@example.com")
    response = api_client.get("/billing/status", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["billing_enabled"] is False
    assert body["is_mock"] is True
    assert body["live_checkout_available"] is False


def test_plans_list(api_client: TestClient) -> None:
    token = _register(api_client, "billing-plans@example.com")
    response = api_client.get("/billing/plans", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    plan_ids = {p["plan_id"] for p in response.json()}
    assert plan_ids == {"free", "pro", "team"}


def test_owner_can_create_mock_customer(api_client: TestClient) -> None:
    token = _register(api_client, "billing-owner@example.com")
    response = api_client.post(
        "/billing/customer",
        headers={"Authorization": f"Bearer {token}"},
        json={"billing_email": "billing-owner@example.com"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["provider"] == "mock"
    assert response.json()["provider_customer_id"].startswith("mock_cus_")


def test_viewer_cannot_create_billing_customer(api_client: TestClient, db_session: Session) -> None:
    from app.security.passwords import hash_password

    settings = Settings()
    owner_token = _register(api_client, "billing-owner2@example.com")
    me = api_client.get("/auth/me", headers={"Authorization": f"Bearer {owner_token}"}).json()
    org_id = uuid.UUID(me["organization"]["id"])

    viewer = User(
        email="billing-viewer@example.com",
        hashed_password=hash_password(_PASSWORD, settings),
    )
    db_session.add(viewer)
    db_session.flush()
    db_session.add(
        Membership(user_id=viewer.id, organization_id=org_id, role=MembershipRole.VIEWER)
    )
    db_session.commit()

    login = api_client.post(
        "/auth/login",
        json={"email": "billing-viewer@example.com", "password": _PASSWORD},
    )
    viewer_token = login.json()["tokens"]["access_token"]

    response = api_client.post(
        "/billing/customer",
        headers={"Authorization": f"Bearer {viewer_token}"},
        json={},
    )
    assert response.status_code == 403


def test_mock_checkout_returns_safe_url(api_client: TestClient) -> None:
    token = _register(api_client, "billing-checkout@example.com")
    api_client.post(
        "/billing/customer",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    response = api_client.post(
        "/billing/checkout",
        headers={"Authorization": f"Bearer {token}"},
        json={"plan_id": "pro"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["is_mock"] is True
    assert "mock.billing.local" in body["checkout_url"]


def test_mock_portal_returns_safe_url(api_client: TestClient) -> None:
    token = _register(api_client, "billing-portal@example.com")
    api_client.post(
        "/billing/customer",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    response = api_client.post(
        "/billing/portal",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert "mock.billing.local" in response.json()["portal_url"]


def test_usage_export_aggregates_usage(db_session: Session) -> None:
    org = Organization(name="Export Org")
    db_session.add(org)
    db_session.flush()

    usage = UsageService(db_session)
    usage.record(
        UsageEventCreate(
            request_id="exp-1",
            organization_id=org.id,
            feature="agent_chat",
            provider="openai",
            input_tokens=100,
            output_tokens=50,
            provider_metadata={
                "cost_source": CostSource.PROVIDER_REPORTED.value,
                "provider_reported_cost": "0.05",
            },
        )
    )
    usage.record(
        UsageEventCreate(
            request_id="exp-2",
            organization_id=org.id,
            feature="rag_ingest",
            provider="mock",
            input_tokens=10,
            output_tokens=0,
            provider_metadata={"cost_source": CostSource.STATIC_ESTIMATED.value},
        )
    )
    db_session.commit()

    from app.schemas.billing import UsageExportRequest

    settings = Settings(billing_enabled=False)
    service = BillingService(db_session, settings)
    result = service.export_usage(org.id, UsageExportRequest())
    assert result.total_events >= 2
    assert result.provider_reported_cost >= Decimal("0.05")


def test_estimated_costs_marked_non_billing_grade(db_session: Session) -> None:
    org = Organization(name="Estimate Org")
    db_session.add(org)
    db_session.flush()

    UsageService(db_session).record(
        UsageEventCreate(
            request_id="est-1",
            organization_id=org.id,
            feature="agent_chat",
            provider="mock",
            input_tokens=500,
            output_tokens=100,
            provider_metadata={"cost_source": CostSource.STATIC_ESTIMATED.value},
        )
    )
    db_session.commit()

    settings = Settings(billing_enabled=False)
    from app.schemas.billing import UsageExportRequest

    result = BillingService(db_session, settings).export_usage(org.id, UsageExportRequest())
    assert result.cost_is_billing_grade is False


def test_plan_change_updates_organization_quota(db_session: Session) -> None:
    org = Organization(name="Plan Org")
    db_session.add(org)
    db_session.flush()

    settings = Settings(billing_enabled=False)
    service = BillingService(db_session, settings)
    service.apply_plan(org.id, "pro")

    quota = db_session.scalar(
        select(OrganizationQuota).where(OrganizationQuota.organization_id == org.id)
    )
    assert quota is not None
    assert quota.monthly_token_limit == 2_000_000
    assert quota.plan_id == "pro"


def test_stripe_secrets_redacted() -> None:
    secret = "sk_test_" + "a" * 24
    webhook = "whsec_" + "b" * 24
    text = f"key={secret} sig={webhook}"
    redacted = redact_text(text)
    assert secret not in redacted
    assert webhook not in redacted


def test_webhook_invalid_signature_rejected_stripe_mode(
    db_session: Session,
) -> None:
    settings = Settings(
        billing_enabled=True,
        stripe_secret_key="sk_test_" + "x" * 24,
        stripe_webhook_secret="whsec_" + "y" * 24,
    )
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_session] = lambda: db_session
    reset_billing_provider_for_tests()

    with TestClient(app) as client:
        response = client.post(
            "/billing/webhook",
            content=b'{"id":"evt_bad","type":"invoice.paid","data":{}}',
            headers={"Stripe-Signature": "invalid"},
        )
    assert response.status_code == 422


def test_duplicate_webhook_ignored(db_session: Session) -> None:
    settings = Settings(billing_enabled=True, stripe_webhook_secret="")
    service = BillingService(db_session, settings)

    payload = json.dumps({"id": "evt_dup_1", "type": "unknown.event", "data": {}}).encode()
    first = service.handle_webhook(payload, "mock-signature-valid")
    second = service.handle_webhook(payload, "mock-signature-valid")
    assert first["status"] == "ok"
    assert second["status"] == "duplicate_ignored"


def test_real_trading_remains_disabled(api_client: TestClient) -> None:
    from app.core.deployment_safety import deployment_posture

    settings = Settings(execution_mode="paper", enable_real_trading=False)
    assert deployment_posture(settings)["real_trading_enabled"] is False
    response = api_client.get("/providers/status")
    exchange = next(p for p in response.json()["providers"] if p["kind"] == "exchange")
    assert "disabled" in (exchange.get("detail") or "").lower() or exchange["is_mock"]


def _stripe_signature(payload: bytes, secret: str) -> str:
    timestamp = str(int(time.time()))
    signed = f"{timestamp}.{payload.decode()}".encode()
    sig = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={sig}"

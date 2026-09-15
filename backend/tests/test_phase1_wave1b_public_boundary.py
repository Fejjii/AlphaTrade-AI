"""Public-boundary regressions for fail-closed Wave 1B plan construction."""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.db.base import Base
from app.db.models import ApprovalAuthorization, TradePlanRevision
from app.db.session import get_session
from app.main import create_app


@pytest.fixture
def authenticated_client() -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_conn: object, _record: object) -> None:
        cursor = dbapi_conn.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def _override_session() -> Iterator[Session]:
        with factory() as session:
            yield session

    settings = Settings(
        environment="local",
        log_json=False,
        execution_mode="paper",
        enable_real_trading=False,
        database_url="sqlite+pysqlite:///:memory:",
        jwt_secret="wave-1b-public-boundary-secret",
        rate_limit_use_redis=False,
        access_token_denylist_use_redis=False,
    )
    app = create_app(settings=settings)
    app.dependency_overrides[get_session] = _override_session
    with TestClient(app) as client:
        response = client.post(
            "/auth/register",
            json={
                "email": "wave-1b-boundary@example.com",
                "password": "secure-password-1",
                "organization_name": "Wave 1B Boundary",
            },
        )
        assert response.status_code == 201
        token = response.json()["tokens"]["access_token"]
        client.headers.update({"Authorization": f"Bearer {token}"})
        yield client, factory
    engine.dispose()


def test_authenticated_caller_cannot_create_executable_revision(
    authenticated_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = authenticated_client
    proposal_id = uuid.uuid4()
    response = client.post(
        f"/proposals/{proposal_id}/revisions",
        json={
            "permission_attestation_id": str(uuid.uuid4()),
            "permission_attestation_version": "caller-invented",
            "quantity": {"value": "999999", "unit": "CONTRACTS"},
            "evidence_is_live": True,
        },
    )
    assert response.status_code == 405
    assert "post" not in client.app.openapi()["paths"]["/proposals/{proposal_id}/revisions"]
    with factory() as session:
        assert session.query(TradePlanRevision).count() == 0


def test_caller_permission_attestation_cannot_enter_authorization_assertion(
    authenticated_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = authenticated_client
    response = client.post(
        f"/approvals/{uuid.uuid4()}/approve",
        json={
            "authorization_assertion": {
                "organization_id": str(uuid.uuid4()),
                "user_id": str(uuid.uuid4()),
                "account_id": str(uuid.uuid4()),
                "exchange_account_id": None,
                "operation": "SUBMIT_ENTRY",
                "plan_id": str(uuid.uuid4()),
                "revision_id": str(uuid.uuid4()),
                "plan_content_hash": "f" * 64,
                "permission_attestation_id": str(uuid.uuid4()),
                "permission_attestation_version": "caller-invented",
            }
        },
    )
    assert response.status_code == 422
    with factory() as session:
        assert session.query(ApprovalAuthorization).count() == 0

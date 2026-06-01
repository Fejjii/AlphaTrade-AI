"""RBAC enforcement tests."""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db.models import Membership
from app.db.session import get_session
from app.main import create_app
from app.schemas.common import MembershipRole
from app.security.rate_limit import reset_rate_limiter


@pytest.fixture(autouse=True)
def _reset_limiter() -> None:
    reset_rate_limiter()


@pytest.fixture
def rbac_settings() -> Settings:
    return Settings(
        environment="local",
        log_json=False,
        database_url="sqlite+pysqlite:///:memory:",
        jwt_secret="test-rbac-secret-key-32-bytes-minimum",
        rate_limit_use_redis=False,
        access_token_denylist_use_redis=False,
    )


@pytest.fixture
def rbac_client(rbac_settings: Settings) -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
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
    app = create_app(settings=rbac_settings)
    app.dependency_overrides[get_session] = _override_session

    with TestClient(app) as client:
        yield client, factory

    app.dependency_overrides.clear()
    get_settings.cache_clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def _register(client: TestClient, *, email: str) -> dict:
    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "secure-password-1",
            "organization_name": "RBAC Org",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _set_membership_role(
    factory: sessionmaker[Session],
    *,
    user_id: uuid.UUID,
    role: MembershipRole,
) -> None:
    with factory() as session:
        membership = session.query(Membership).filter(Membership.user_id == user_id).one()
        membership.role = role
        session.commit()


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_viewer_can_read_proposals(rbac_client: tuple[TestClient, sessionmaker[Session]]) -> None:
    client, factory = rbac_client
    registered = _register(client, email="viewer@example.com")
    _set_membership_role(
        factory,
        user_id=uuid.UUID(registered["user"]["id"]),
        role=MembershipRole.VIEWER,
    )
    token = registered["tokens"]["access_token"]

    listed = client.get("/proposals", headers=_auth_headers(token))
    assert listed.status_code == 200


def test_viewer_cannot_create_proposal(
    rbac_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = rbac_client
    registered = _register(client, email="viewer-block@example.com")
    _set_membership_role(
        factory, user_id=uuid.UUID(registered["user"]["id"]), role=MembershipRole.VIEWER
    )
    token = registered["tokens"]["access_token"]

    response = client.post(
        "/proposals",
        headers=_auth_headers(token),
        json={
            "organization_id": str(uuid.uuid4()),
            "user_id": str(uuid.uuid4()),
            "strategy_id": "htf_trend_pullback",
            "symbol": "BTCUSDT",
            "timeframe": "4h",
            "direction": "long",
            "entry_price": "60000",
            "position_size": "0.01",
            "leverage": "3",
            "exit": {
                "invalidation": "Close below stop.",
                "stop_loss": "58000",
                "take_profits": [{"price": "62000", "size_fraction": 0.5}],
            },
            "confidence": 0.7,
            "risk_level": "medium",
            "rationale": "test",
            "approval_required": True,
        },
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_trader_can_create_watchlist_item(
    rbac_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = rbac_client
    registered = _register(client, email="trader@example.com")
    _set_membership_role(
        factory,
        user_id=uuid.UUID(registered["user"]["id"]),
        role=MembershipRole.TRADER,
    )
    token = registered["tokens"]["access_token"]

    response = client.post(
        "/market/watchlist",
        headers=_auth_headers(token),
        json={
            "organization_id": str(uuid.uuid4()),
            "user_id": str(uuid.uuid4()),
            "symbol": "ETHUSDT",
            "exchange": "binance",
            "timeframes": ["4h"],
            "strategy_ids": ["htf_trend_pullback"],
        },
    )
    assert response.status_code == 200


def test_owner_can_mutate_journal(rbac_client: tuple[TestClient, sessionmaker[Session]]) -> None:
    client, _factory = rbac_client
    registered = _register(client, email="owner@example.com")
    token = registered["tokens"]["access_token"]

    response = client.post(
        "/journal/entries",
        headers=_auth_headers(token),
        json={
            "organization_id": str(uuid.uuid4()),
            "user_id": str(uuid.uuid4()),
            "symbol": "BTCUSDT",
            "timeframe": "4h",
            "direction": "long",
            "entry_rationale": "Owner note",
            "lessons": "Allowed",
            "tags": ["review"],
        },
    )
    assert response.status_code == 200

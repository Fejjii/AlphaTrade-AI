"""End-to-end API smoke flow for authenticated MVP paths."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db.session import get_session
from app.main import create_app
from app.security.rate_limit import reset_rate_limiter


@pytest.fixture(autouse=True)
def _reset_limiter() -> None:
    reset_rate_limiter()


@pytest.fixture
def smoke_settings() -> Settings:
    return Settings(
        environment="local",
        log_json=False,
        database_url="sqlite+pysqlite:///:memory:",
        jwt_secret="smoke-test-secret-key-32-bytes-minimum",
        rate_limit_use_redis=False,
        access_token_denylist_use_redis=False,
    )


@pytest.fixture
def smoke_client(smoke_settings: Settings) -> Iterator[TestClient]:
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
    app = create_app(settings=smoke_settings)
    app.dependency_overrides[get_session] = _override_session

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
    get_settings.cache_clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_smoke_register_login_chat_logout(smoke_client: TestClient) -> None:
    register = smoke_client.post(
        "/auth/register",
        json={
            "email": "smoke@example.com",
            "password": "secure-password-1",
            "organization_name": "Smoke Org",
        },
    )
    assert register.status_code == 201
    tokens = register.json()["tokens"]
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    me = smoke_client.get("/auth/me", headers=headers)
    assert me.status_code == 200

    chat = smoke_client.post(
        "/chat/message",
        headers=headers,
        json={"message": "Summarize paper mode safety posture."},
    )
    assert chat.status_code == 200

    proposals = smoke_client.get("/proposals", headers=headers)
    assert proposals.status_code == 200

    logout = smoke_client.post("/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert logout.status_code == 200

    blocked = smoke_client.get("/proposals")
    assert blocked.status_code == 401

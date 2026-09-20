"""Canonical evidence HTTP: auth, tenant isolation, honesty, fail-closed symbols."""

from __future__ import annotations

from collections.abc import Iterator
from uuid import UUID

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
def _reset_rate_limiter() -> None:
    reset_rate_limiter()


@pytest.fixture
def evidence_settings() -> Settings:
    return Settings(
        environment="local",
        log_json=False,
        execution_mode="paper",
        enable_real_trading=False,
        database_url="sqlite+pysqlite:///:memory:",
        jwt_secret="test-secret-key-for-evidence-pipeline-32b",
        access_token_denylist_use_redis=False,
        market_data_cache_use_redis=False,
        rate_limit_use_redis=False,
        perpetual_evidence_source="replay",
        watcher_orchestration_enabled=False,
    )


@pytest.fixture
def evidence_client(evidence_settings: Settings) -> Iterator[TestClient]:
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
    app = create_app(settings=evidence_settings)
    app.dependency_overrides[get_session] = _override_session
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    get_settings.cache_clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def _register(client: TestClient, *, email: str, org: str) -> dict[str, object]:
    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "secure-password-1",
            "organization_name": org,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _auth_header(payload: dict[str, object]) -> dict[str, str]:
    tokens = payload["tokens"]
    assert isinstance(tokens, dict)
    token = tokens["access_token"]
    assert isinstance(token, str)
    return {"Authorization": f"Bearer {token}"}


def test_canonical_evidence_requires_auth(evidence_client: TestClient) -> None:
    response = evidence_client.get("/canonical/evidence")
    assert response.status_code == 401


def test_replay_evidence_is_not_a_live_mark(evidence_client: TestClient) -> None:
    registered = _register(evidence_client, email="trader@example.com", org="Evidence Org")
    response = evidence_client.get("/canonical/evidence", headers=_auth_header(registered))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["authority"] == "canonical"
    assert body["live_executable"] is False
    assert body["watcher_activated"] is False
    assert body["symbol"] == "BTCUSDT"
    price = body["current_price"]
    assert price["usable_as_current_market_price"] is False
    assert price["presentation"] == "replay_fixture"
    assert price["is_mock"] is True
    assert price["is_live"] is False
    assert price["fallback_used"] is False
    assert price["price"] not in {"47326", "65000", 47326, 65000}
    setup = body["setup_evidence"]
    assert setup["available"] is True
    assert setup["evidence_window_hash"]
    assert len(setup["evidence_window_hash"]) == 64
    assert setup["completeness"]["cvd"] == "complete"
    assert body["source"]["source_family"] == "replay_fixture"
    assert body["source"]["market_type"] == "perpetual"
    assert "BTCUSDT" in body["source"]["instrument_id"]
    assert body["source"]["fallback_used"] is False


def test_wrong_symbol_is_rejected(evidence_client: TestClient) -> None:
    registered = _register(evidence_client, email="trader@example.com", org="Evidence Org")
    response = evidence_client.get(
        "/canonical/evidence",
        params={"symbol": "ETHUSDT"},
        headers=_auth_header(registered),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unknown_perpetual_instrument"


def test_tenant_boundaries_fork_window_hash(evidence_client: TestClient) -> None:
    first = _register(evidence_client, email="a@example.com", org="Org A")
    second = _register(evidence_client, email="b@example.com", org="Org B")
    left = evidence_client.get("/canonical/evidence", headers=_auth_header(first))
    right = evidence_client.get("/canonical/evidence", headers=_auth_header(second))
    assert left.status_code == 200
    assert right.status_code == 200
    left_hash = left.json()["setup_evidence"]["evidence_window_hash"]
    right_hash = right.json()["setup_evidence"]["evidence_window_hash"]
    assert left_hash != right_hash
    left_org = UUID(left.json()["organization_id"])
    right_org = UUID(right.json()["organization_id"])
    assert left_org != right_org


def test_same_tenant_restart_converges(evidence_client: TestClient) -> None:
    registered = _register(evidence_client, email="trader@example.com", org="Evidence Org")
    first = evidence_client.get("/canonical/evidence", headers=_auth_header(registered))
    second = evidence_client.get("/canonical/evidence", headers=_auth_header(registered))
    assert (
        first.json()["setup_evidence"]["evidence_window_hash"]
        == second.json()["setup_evidence"]["evidence_window_hash"]
    )

"""P0 paper-close exit-price honesty regression tests.

Staging evidence (close audit event 4442c6ac-9fac-4e5f-ae0a-8f66697bbc31):
an explicit paper close submitted ``91234.56`` but the audit event recorded
``exit_price=64524.01`` (the market ticker) and PnL was derived from the
ticker instead of the submitted price.

Contract under test:
- An explicit user-submitted paper close price is authoritative: the exact
  decimal drives persistence, realized PnL, and the audit event.
- Market ticker data never silently replaces an explicit price, regardless of
  provider mode, staleness, or availability.
- Malformed explicit prices fail closed; no price is ever fabricated.
- Closes without an explicit price (future system/automated closes) still bind
  to fresh server market data and fail closed when it is degraded or missing.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.core.dependencies import get_market_data_service
from app.core.errors import TradingPolicyError, ValidationAppError
from app.db.base import Base
from app.db.models import AuditLog, Membership, Organization, Position, User
from app.db.session import get_session
from app.main import create_app
from app.schemas.common import (
    MembershipRole,
    PositionStatus,
    StrategyId,
    TradeDirection,
)
from app.schemas.position import ClosePaperPositionRequest
from app.security.passwords import hash_password
from app.security.rate_limit import reset_rate_limiter
from app.services.audit_service import AuditService
from app.services.position_service import PositionService

ORG_ID = uuid.UUID("00000000-0000-0000-0000-0000000000e1")
USER_ID = uuid.UUID("00000000-0000-0000-0000-0000000000e2")

# Staging-observed values (audit event 4442c6ac-9fac-4e5f-ae0a-8f66697bbc31).
SUBMITTED_EXIT = Decimal("91234.56")
TICKER_PRICE = Decimal("64524.01")

_BASE_SETTINGS: dict[str, object] = {
    "environment": "local",
    "log_json": False,
    "execution_mode": "paper",
    "enable_real_trading": False,
    "exchange_mode": "paper_internal",
    "database_url": "sqlite+pysqlite:///:memory:",
    "jwt_secret": "exit-price-honesty-secret-32-bytes!!",
    "rate_limit_use_redis": False,
    "access_token_denylist_use_redis": False,
    "alert_delivery_enabled": False,
    "telegram_alerts_enabled": False,
    "worker_enabled": False,
    "market_watcher_enabled": False,
}


def _settings(**overrides: object) -> Settings:
    return Settings(**{**_BASE_SETTINGS, **overrides})  # type: ignore[arg-type]


def _staging_like_settings() -> Settings:
    """Non-mock market provider posture, as observed on staging."""
    return _settings(provider_mode="fallback", market_data_provider="binance")


def _mock_provider_settings() -> Settings:
    return _settings(provider_mode="mock", market_data_provider="mock")


def _fresh_ticker(last_price: Decimal = TICKER_PRICE) -> MagicMock:
    """Market data service returning a fresh (non-stale, non-fallback) ticker."""
    market_data = MagicMock()
    ticker = MagicMock()
    ticker.last_price = last_price
    ticker.meta.is_stale = False
    ticker.meta.fallback_used = False
    market_data.get_ticker.return_value = ticker
    return market_data


def _stale_ticker() -> MagicMock:
    market_data = MagicMock()
    ticker = MagicMock()
    ticker.last_price = TICKER_PRICE
    ticker.meta.is_stale = True
    ticker.meta.fallback_used = False
    market_data.get_ticker.return_value = ticker
    return market_data


@pytest.fixture
def db(request: pytest.FixtureRequest) -> Iterator[sessionmaker[Session]]:
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
        session.add(Organization(id=ORG_ID, name="Exit Price Org"))
        session.add(
            User(
                id=USER_ID,
                email="exit-price@test.example",
                hashed_password=hash_password("SecurePass123!", _mock_provider_settings()),
                email_verified=True,
            )
        )
        session.flush()
        session.add(Membership(user_id=USER_ID, organization_id=ORG_ID, role=MembershipRole.OWNER))
        session.commit()
    yield factory
    engine.dispose()


def _seed_open_position(
    session: Session,
    *,
    direction: TradeDirection = TradeDirection.LONG,
    entry_price: Decimal = Decimal("64508.1"),
    size: Decimal = Decimal("0.005"),
) -> Position:
    position = Position(
        organization_id=ORG_ID,
        user_id=USER_ID,
        strategy_id=StrategyId.HTF_TREND_PULLBACK,
        symbol="BTCUSDT",
        direction=direction,
        size=size,
        entry_price=entry_price,
        leverage=Decimal("3"),
        stop_loss=Decimal("60000"),
        take_profits=[],
        status=PositionStatus.OPEN,
        opened_at=datetime.now(UTC),
    )
    session.add(position)
    session.commit()
    return position


def _service(
    session: Session,
    settings: Settings,
    market_data: MagicMock | None,
) -> PositionService:
    return PositionService(
        session,
        AuditService(session),
        settings=settings,
        market_data_service=market_data,
    )


def _close_audit_metadata(session: Session, position_id: uuid.UUID) -> dict[str, Any]:
    rows = session.scalars(select(AuditLog).where(AuditLog.resource_id == str(position_id))).all()
    close_events = [
        row for row in rows if (row.redacted_metadata or {}).get("action") == "close_paper"
    ]
    assert len(close_events) == 1
    return dict(close_events[0].redacted_metadata)


# --------------------------------------------------------------------------- #
# Explicit submitted price is authoritative
# --------------------------------------------------------------------------- #


def test_explicit_close_with_non_mock_provider_uses_submitted_price(
    db: sessionmaker[Session],
) -> None:
    """Staging reproduction: submitted price differs materially from the ticker."""
    settings = _staging_like_settings()
    market_data = _fresh_ticker()
    with db() as session:
        position = _seed_open_position(session)
        closed = _service(session, settings, market_data).close_paper(
            position.id,
            ClosePaperPositionRequest(exit_price=SUBMITTED_EXIT, reason="drill"),
        )
        session.commit()

        # PnL from the submitted price: (91234.56 - 64508.1) * 0.005 = 133.6323.
        assert closed.realized_pnl == Decimal("133.6323")
        assert closed.status is PositionStatus.CLOSED

        meta = _close_audit_metadata(session, position.id)
        assert meta["exit_price"] == "91234.56"
        assert meta["requested_exit_price"] == "91234.56"
        assert meta["exit_price"] == meta["requested_exit_price"]
        assert meta["exit_price_source"] == "user_submitted"
        # (91234.56 - 64508.1) * 0.005, exact Decimal math (5 fractional digits).
        assert meta["realized_pnl"] == "133.63230"

        # The ticker must not even be consulted for an explicit paper close —
        # stale or unavailable market data can never replace the price.
        assert market_data.get_ticker.called is False
        # No exchange/live-execution call paths on the market data service.
        assert market_data.method_calls == []


def test_explicit_close_with_mock_provider_uses_submitted_price(
    db: sessionmaker[Session],
) -> None:
    settings = _mock_provider_settings()
    with db() as session:
        position = _seed_open_position(session)
        closed = _service(session, settings, _fresh_ticker()).close_paper(
            position.id,
            ClosePaperPositionRequest(exit_price=SUBMITTED_EXIT, reason="mock drill"),
        )
        session.commit()
        assert closed.realized_pnl == Decimal("133.6323")
        meta = _close_audit_metadata(session, position.id)
        assert meta["exit_price"] == "91234.56"
        assert meta["requested_exit_price"] == "91234.56"


def test_explicit_close_honest_even_when_market_data_stale(
    db: sessionmaker[Session],
) -> None:
    """Stale market data must not replace or refuse an explicit paper close."""
    settings = _staging_like_settings()
    market_data = _stale_ticker()
    with db() as session:
        position = _seed_open_position(session)
        closed = _service(session, settings, market_data).close_paper(
            position.id,
            ClosePaperPositionRequest(exit_price=SUBMITTED_EXIT, reason="stale md"),
        )
        session.commit()
        assert closed.realized_pnl == Decimal("133.6323")
        assert market_data.get_ticker.called is False


def test_explicit_close_short_direction_pnl_from_submitted_price(
    db: sessionmaker[Session],
) -> None:
    settings = _staging_like_settings()
    with db() as session:
        position = _seed_open_position(
            session,
            direction=TradeDirection.SHORT,
            entry_price=Decimal("65000"),
            size=Decimal("0.01"),
        )
        closed = _service(session, settings, _fresh_ticker()).close_paper(
            position.id,
            ClosePaperPositionRequest(exit_price=Decimal("64000"), reason="short win"),
        )
        session.commit()
        # Short: (65000 - 64000) * 0.01 = +10.
        assert closed.realized_pnl == Decimal("10.00")


def test_explicit_close_preserves_high_decimal_precision(
    db: sessionmaker[Session],
) -> None:
    """The exact submitted decimal reaches the audit trail; PnL is exact math."""
    settings = _staging_like_settings()
    with db() as session:
        position = _seed_open_position(
            session,
            entry_price=Decimal("0.00012000"),
            size=Decimal("1000000"),
        )
        submitted = Decimal("0.00012345")
        closed = _service(session, settings, _fresh_ticker()).close_paper(
            position.id,
            ClosePaperPositionRequest(exit_price=submitted, reason="precision"),
        )
        session.commit()
        meta = _close_audit_metadata(session, position.id)
        assert meta["exit_price"] == "0.00012345"
        assert meta["requested_exit_price"] == "0.00012345"
        # (0.00012345 - 0.00012000) * 1000000 = 3.45
        assert closed.realized_pnl == Decimal("3.45")


# --------------------------------------------------------------------------- #
# Fail-closed validation of explicit prices
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("bad_price", ["0", "-1", "NaN", "Infinity", "-Infinity"])
def test_request_schema_rejects_invalid_exit_prices(bad_price: str) -> None:
    with pytest.raises(ValidationError):
        ClosePaperPositionRequest(exit_price=Decimal(bad_price), reason="bad")


def test_request_schema_requires_exit_price() -> None:
    """Missing explicit price is rejected at the boundary (existing contract)."""
    with pytest.raises(ValidationError):
        ClosePaperPositionRequest(reason="no price")  # type: ignore[call-arg]


@pytest.mark.parametrize("bad_price", ["0", "-5", "NaN", "Infinity"])
def test_service_fails_closed_on_malformed_explicit_price(
    db: sessionmaker[Session], bad_price: str
) -> None:
    """Defense in depth: direct service calls with malformed decimals fail closed."""
    settings = _staging_like_settings()
    with db() as session:
        position = _seed_open_position(session)
        request = ClosePaperPositionRequest.model_construct(
            exit_price=Decimal(bad_price), reason="malformed"
        )
        with pytest.raises(ValidationAppError):
            _service(session, settings, _fresh_ticker()).close_paper(position.id, request)
        session.rollback()
        refreshed = session.get(Position, position.id)
        assert refreshed is not None
        assert refreshed.status is PositionStatus.OPEN


# --------------------------------------------------------------------------- #
# Missing explicit price (system/automated close path) stays market-bound
# --------------------------------------------------------------------------- #


def test_system_close_without_explicit_price_binds_to_fresh_ticker(
    db: sessionmaker[Session],
) -> None:
    settings = _staging_like_settings()
    market_data = _fresh_ticker(Decimal("64524.01"))
    with db() as session:
        service = _service(session, settings, market_data)
        resolved = service._resolve_close_exit_price("BTCUSDT", requested=None)
        assert resolved == Decimal("64524.01")
        assert market_data.get_ticker.called is True


def test_system_close_refuses_stale_market_data(db: sessionmaker[Session]) -> None:
    settings = _staging_like_settings()
    with db() as session:
        service = _service(session, settings, _stale_ticker())
        with pytest.raises(TradingPolicyError) as exc:
            service._resolve_close_exit_price("BTCUSDT", requested=None)
        assert exc.value.details.get("reason") == "market_data_degraded"


def test_system_close_refuses_unavailable_market_data(db: sessionmaker[Session]) -> None:
    settings = _staging_like_settings()
    market_data = MagicMock()
    market_data.get_ticker.side_effect = RuntimeError("provider down")
    with db() as session:
        service = _service(session, settings, market_data)
        with pytest.raises(TradingPolicyError) as exc:
            service._resolve_close_exit_price("BTCUSDT", requested=None)
        assert exc.value.details.get("reason") == "market_data_unavailable"


def test_system_close_never_fabricates_price_without_market_data(
    db: sessionmaker[Session],
) -> None:
    """No market data service + no explicit price → refuse; never invent a value."""
    settings = _staging_like_settings()
    with db() as session:
        service = _service(session, settings, None)
        with pytest.raises(TradingPolicyError) as exc:
            service._resolve_close_exit_price("BTCUSDT", requested=None)
        assert exc.value.details.get("reason") == "market_data_unavailable"


# --------------------------------------------------------------------------- #
# End-to-end via the close-paper endpoint (route + schema + service + audit)
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def _reset_limiter() -> None:
    reset_rate_limiter()


@contextmanager
def _client(
    factory: sessionmaker[Session], settings: Settings, market_data: MagicMock
) -> Iterator[TestClient]:
    app = create_app(settings=settings)

    def _override_session() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[get_market_data_service] = lambda: market_data
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_close_paper_endpoint_persists_exact_submitted_price(
    db: sessionmaker[Session],
) -> None:
    settings = _staging_like_settings()
    market_data = _fresh_ticker()
    with db() as session:
        position = _seed_open_position(session)
        position_id = position.id

    with _client(db, settings, market_data) as client:
        login = client.post(
            "/auth/login",
            json={"email": "exit-price@test.example", "password": "SecurePass123!"},
        )
        assert login.status_code == 200, login.text
        headers = {"Authorization": f"Bearer {login.json()['tokens']['access_token']}"}

        response = client.post(
            f"/positions/{position_id}/close-paper",
            json={"exit_price": "91234.56", "reason": "staging drill"},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "closed"
        assert Decimal(body["realized_pnl"]) == Decimal("133.6323")

    with db() as session:
        refreshed = session.get(Position, position_id)
        assert refreshed is not None
        assert refreshed.status is PositionStatus.CLOSED
        assert refreshed.realized_pnl == Decimal("133.6323")

        meta = _close_audit_metadata(session, position_id)
        assert meta["exit_price"] == "91234.56"
        assert meta["requested_exit_price"] == "91234.56"
        assert meta["exit_price_source"] == "user_submitted"

    # Paper-only safety posture: explicit close touched no market/exchange path.
    assert market_data.get_ticker.called is False
    assert settings.enable_real_trading is False
    assert settings.execution_mode.value == "paper"
    assert settings.exchange_mode.value == "paper_internal"


def test_close_paper_endpoint_rejects_invalid_price(db: sessionmaker[Session]) -> None:
    settings = _staging_like_settings()
    with db() as session:
        position = _seed_open_position(session)
        position_id = position.id

    with _client(db, settings, _fresh_ticker()) as client:
        login = client.post(
            "/auth/login",
            json={"email": "exit-price@test.example", "password": "SecurePass123!"},
        )
        assert login.status_code == 200, login.text
        headers = {"Authorization": f"Bearer {login.json()['tokens']['access_token']}"}

        for bad in ["0", "-1", "NaN"]:
            response = client.post(
                f"/positions/{position_id}/close-paper",
                json={"exit_price": bad, "reason": "invalid"},
                headers=headers,
            )
            assert response.status_code == 422, response.text

    with db() as session:
        refreshed = session.get(Position, position_id)
        assert refreshed is not None
        assert refreshed.status is PositionStatus.OPEN

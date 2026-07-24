"""AT-033 — opt-in auto-journal hooks (position close, paper-validation close)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.db.base import Base
from app.db.models import (
    AuditLog,
    JournalTrade,
    Membership,
    Organization,
    PaperTrade,
    PaperValidationRun,
    Position,
    User,
    UserStrategy,
    UserStrategyVersion,
)
from app.db.session import get_session
from app.main import create_app
from app.schemas.common import (
    AuditEventType,
    JournalEntryMethod,
    JournalTradeSource,
    JournalTradeStatus,
    MembershipRole,
    PaperTradeStatus,
    PositionStatus,
    StrategyId,
    TradeDirection,
)
from app.security.passwords import hash_password
from app.security.rate_limit import reset_rate_limiter
from app.services.journal_trade_service import JournalTradeService
from app.services.paper_validation_runtime_service import PaperValidationRuntimeService

ORG_A = uuid.UUID("00000000-0000-0000-0000-000000033301")
USER_A = uuid.UUID("00000000-0000-0000-0000-000000033311")

_BASE = {
    "environment": "local",
    "log_json": False,
    "execution_mode": "paper",
    "enable_real_trading": False,
    "database_url": "sqlite+pysqlite:///:memory:",
    "jwt_secret": "auto-journal-test-secret-abc-32char",
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


@contextmanager
def _build_client(
    **settings_overrides: object,
) -> Iterator[tuple[TestClient, sessionmaker[Session], Settings]]:
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
    settings = Settings(**{**_BASE, **settings_overrides})

    with factory() as session:
        session.add(Organization(id=ORG_A, name="Auto Journal Org"))
        session.add(
            User(
                id=USER_A,
                email="auto-a@test.example",
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
        yield test_client, factory, settings

    app.dependency_overrides.clear()
    engine.dispose()


def _auth(client: TestClient, email: str = "auto-a@test.example") -> dict[str, str]:
    login = client.post("/auth/login", json={"email": email, "password": "SecurePass123!"})
    assert login.status_code == 200, login.text
    token = login.json()["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _seed_open_position(factory: sessionmaker[Session]) -> uuid.UUID:
    with factory() as session:
        position = Position(
            organization_id=ORG_A,
            user_id=USER_A,
            strategy_id=StrategyId.HTF_TREND_PULLBACK,
            symbol="ETHUSDT",
            direction=TradeDirection.LONG,
            size=Decimal("1"),
            entry_price=Decimal("3000"),
            leverage=Decimal("2"),
            stop_loss=Decimal("2900"),
            status=PositionStatus.OPEN,
            opened_at=datetime(2026, 7, 1, 10, 0, tzinfo=UTC),
        )
        session.add(position)
        session.commit()
        return position.id


def _seed_closed_paper_trade(
    factory: sessionmaker[Session],
) -> tuple[uuid.UUID, uuid.UUID]:
    """Returns (paper_trade_id, run_id)."""
    with factory() as session:
        strategy = UserStrategy(
            organization_id=ORG_A,
            user_id=USER_A,
            name=f"Sweep reversal {uuid.uuid4().hex[:6]}",
            setup_type=StrategyId.LIQUIDITY_SWEEP_REVERSAL,
        )
        session.add(strategy)
        session.flush()
        version = UserStrategyVersion(
            strategy_id=strategy.id, version=1, card={"name": strategy.name}
        )
        session.add(version)
        session.flush()
        run = PaperValidationRun(
            strategy_id=strategy.id,
            strategy_version_id=version.id,
            organization_id=ORG_A,
            user_id=USER_A,
        )
        session.add(run)
        session.flush()
        trade = PaperTrade(
            paper_validation_run_id=run.id,
            strategy_id=strategy.id,
            strategy_version_id=version.id,
            organization_id=ORG_A,
            user_id=USER_A,
            symbol="SOLUSDT",
            exchange="binance",
            timeframe="15m",
            direction=TradeDirection.SHORT,
            entry_price=Decimal("150"),
            entry_time=datetime(2026, 7, 3, 9, 0, tzinfo=UTC),
            size=Decimal("10"),
            stop_loss=Decimal("155"),
            invalidation="15m close above 155.",
            status=PaperTradeStatus.CLOSED,
            exit_price=Decimal("145"),
            exit_time=datetime(2026, 7, 3, 14, 0, tzinfo=UTC),
            exit_reason="tp_hit",
            gross_pnl=Decimal("50"),
            net_pnl=Decimal("48"),
            fees=Decimal("1.5"),
            slippage=Decimal("0.5"),
        )
        session.add(trade)
        session.commit()
        return trade.id, run.id


def _close_position(client: TestClient, headers: dict[str, str], position_id: uuid.UUID) -> None:
    resp = client.post(
        f"/positions/{position_id}/close-paper",
        json={"exit_price": "3150", "reason": "target reached"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "closed"


# --------------------------------------------------------------------------- #
# Position close hook
# --------------------------------------------------------------------------- #


def test_flag_off_by_default_no_auto_journal() -> None:
    with _build_client() as (client, factory, settings):
        assert settings.journal_auto_from_position_close is False
        assert settings.journal_auto_from_paper_validation is False
        headers = _auth(client)
        position_id = _seed_open_position(factory)
        _close_position(client, headers, position_id)
        with factory() as session:
            assert session.scalars(select(JournalTrade)).all() == []


def test_flag_on_close_creates_auto_journal_trade() -> None:
    with _build_client(journal_auto_from_position_close=True) as (client, factory, _):
        headers = _auth(client)
        position_id = _seed_open_position(factory)
        _close_position(client, headers, position_id)
        with factory() as session:
            trade = session.scalars(select(JournalTrade)).one()
            assert trade.source is JournalTradeSource.PAPER_EXECUTION
            assert trade.entry_method is JournalEntryMethod.AUTO
            assert trade.status is JournalTradeStatus.CLOSED
            assert trade.linked_position_id == position_id
            assert trade.organization_id == ORG_A
            assert trade.user_id == USER_A
            assert trade.net_pnl == Decimal("150")


def test_manual_journal_first_prevents_duplicate_auto_entry() -> None:
    with _build_client(journal_auto_from_position_close=True) as (client, factory, _):
        headers = _auth(client)
        position_id = _seed_open_position(factory)
        manual = client.post(f"/journal/trades/from-position/{position_id}", headers=headers)
        assert manual.status_code == 201, manual.text

        _close_position(client, headers, position_id)
        with factory() as session:
            trades = session.scalars(select(JournalTrade)).all()
            assert len(trades) == 1
            # The pre-existing manual record is untouched.
            assert trades[0].entry_method is JournalEntryMethod.MANUAL


def test_journaling_failure_never_blocks_position_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _build_client(journal_auto_from_position_close=True) as (client, factory, _):
        headers = _auth(client)
        position_id = _seed_open_position(factory)

        def _boom(self: object, *args: object, **kwargs: object) -> object:
            raise RuntimeError("journal write failed")

        monkeypatch.setattr(JournalTradeService, "create_from_position", _boom)
        _close_position(client, headers, position_id)

        with factory() as session:
            position = session.get(Position, position_id)
            assert position is not None
            assert position.status is PositionStatus.CLOSED
            assert position.realized_pnl == Decimal("150")
            assert session.scalars(select(JournalTrade)).all() == []


# --------------------------------------------------------------------------- #
# Paper-validation close hook
# --------------------------------------------------------------------------- #


def test_paper_validation_hook_flag_off_creates_nothing() -> None:
    with _build_client() as (_client, factory, settings):
        trade_id, run_id = _seed_closed_paper_trade(factory)
        with factory() as session:
            service = PaperValidationRuntimeService(session, settings)
            run = session.get(PaperValidationRun, run_id)
            trade = session.get(PaperTrade, trade_id)
            assert run is not None and trade is not None
            service._auto_journal_closed_trades([(trade, object())], run)
            session.commit()
        with factory() as session:
            assert session.scalars(select(JournalTrade)).all() == []


def test_paper_validation_hook_journals_run_owner() -> None:
    with _build_client(journal_auto_from_paper_validation=True) as (
        _client,
        factory,
        settings,
    ):
        trade_id, run_id = _seed_closed_paper_trade(factory)
        with factory() as session:
            service = PaperValidationRuntimeService(session, settings)
            run = session.get(PaperValidationRun, run_id)
            trade = session.get(PaperTrade, trade_id)
            assert run is not None and trade is not None
            service._auto_journal_closed_trades([(trade, object())], run)
            # Idempotent: a second invocation must not duplicate.
            service._auto_journal_closed_trades([(trade, object())], run)
            session.commit()
        with factory() as session:
            journal = session.scalars(select(JournalTrade)).one()
            assert journal.source is JournalTradeSource.PAPER_VALIDATION
            assert journal.entry_method is JournalEntryMethod.AUTO
            assert journal.linked_paper_trade_id == trade_id
            assert journal.linked_paper_validation_run_id == run_id
            assert journal.user_id == USER_A
            assert journal.net_pnl == Decimal("48")


def test_paper_validation_hook_failure_is_isolated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _build_client(journal_auto_from_paper_validation=True) as (
        _client,
        factory,
        settings,
    ):
        trade_id, run_id = _seed_closed_paper_trade(factory)

        def _boom(self: object, *args: object, **kwargs: object) -> object:
            raise RuntimeError("journal write failed")

        monkeypatch.setattr(JournalTradeService, "create_from_paper_trade", _boom)
        with factory() as session:
            service = PaperValidationRuntimeService(session, settings)
            run = session.get(PaperValidationRun, run_id)
            trade = session.get(PaperTrade, trade_id)
            assert run is not None and trade is not None
            # Must not raise; the runtime loop continues.
            service._auto_journal_closed_trades([(trade, object())], run)
            session.commit()
        with factory() as session:
            assert session.scalars(select(JournalTrade)).all() == []


# --------------------------------------------------------------------------- #
# Statistics readiness
# --------------------------------------------------------------------------- #


def test_auto_journaled_close_visible_in_entry_method_statistics() -> None:
    with _build_client(journal_auto_from_position_close=True) as (client, factory, _):
        headers = _auth(client)
        position_id = _seed_open_position(factory)
        _close_position(client, headers, position_id)

        resp = client.get(
            "/journal/statistics", params={"group_by": "entry_method"}, headers=headers
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["overall"]["trade_count"] == 1
        assert {bucket["key"] for bucket in body["buckets"]} == {"auto"}


def test_auto_journal_records_audit_event() -> None:
    """The hook records the standard JOURNAL_TRADE_CREATED audit event."""
    with _build_client(journal_auto_from_position_close=True) as (client, factory, _):
        headers = _auth(client)
        position_id = _seed_open_position(factory)
        _close_position(client, headers, position_id)
        with factory() as session:
            audit = session.scalars(
                select(AuditLog).where(AuditLog.action == AuditEventType.JOURNAL_TRADE_CREATED)
            ).all()
            assert len(audit) == 1

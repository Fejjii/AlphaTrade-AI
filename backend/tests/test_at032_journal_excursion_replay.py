"""AT-032 — deterministic journal excursion replay (MFE/MAE / profit-capture)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
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
    HistoricalCandle,
    JournalTrade,
    Membership,
    Organization,
    User,
)
from app.db.session import get_session
from app.main import create_app
from app.schemas.common import (
    AuditEventType,
    JournalTradeSource,
    JournalTradeStatus,
    MarketRegime,
    MembershipRole,
    TradeDirection,
    TradeResult,
)
from app.schemas.journal_excursion_replay import ExcursionOverwritePolicy
from app.security.passwords import hash_password
from app.security.rate_limit import reset_rate_limiter
from app.services.journal_excursion_calculator import (
    CandleBar,
    compute_trade_excursions,
    filter_bars_in_window,
)

ORG_A = uuid.UUID("00000000-0000-0000-0000-000000009201")
ORG_B = uuid.UUID("00000000-0000-0000-0000-000000009202")
USER_A = uuid.UUID("00000000-0000-0000-0000-000000009211")
USER_B = uuid.UUID("00000000-0000-0000-0000-000000009212")
VIEWER_A = uuid.UUID("00000000-0000-0000-0000-000000009213")

_BASE = {
    "environment": "local",
    "log_json": False,
    "execution_mode": "paper",
    "enable_real_trading": False,
    "database_url": "sqlite+pysqlite:///:memory:",
    "jwt_secret": "journal-replay-test-secret-abc-32ch",
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
        session.add(Organization(id=ORG_A, name="Replay Org A"))
        session.add(Organization(id=ORG_B, name="Replay Org B"))
        for user_id, email in (
            (USER_A, "replay-a@test.example"),
            (USER_B, "replay-b@test.example"),
            (VIEWER_A, "replay-viewer@test.example"),
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
        session.add(Membership(user_id=VIEWER_A, organization_id=ORG_A, role=MembershipRole.VIEWER))
        session.commit()

    app = create_app(settings=settings)

    def _override_session() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = _override_session
    with TestClient(app) as test_client:
        yield test_client, factory


def _auth(client: TestClient, email: str) -> dict[str, str]:
    login = client.post("/auth/login", json={"email": email, "password": "SecurePass123!"})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['tokens']['access_token']}"}


def _bar(
    open_time: datetime,
    high: str,
    low: str,
    *,
    source: str = "mock",
    is_stale: bool = False,
) -> CandleBar:
    return CandleBar(
        open_time=open_time,
        close_time=open_time + timedelta(hours=1),
        high=Decimal(high),
        low=Decimal(low),
        source=source,
        is_stale=is_stale,
    )


# ---------------------------------------------------------------------------
# Pure calculator
# ---------------------------------------------------------------------------


def test_calculator_long_mfe_mae_and_capture() -> None:
    t0 = datetime(2026, 7, 10, 8, 0, tzinfo=UTC)
    bars = [
        _bar(t0, "102", "99"),
        _bar(t0 + timedelta(hours=1), "110", "100"),
        _bar(t0 + timedelta(hours=2), "108", "95"),
    ]
    result = compute_trade_excursions(
        direction=TradeDirection.LONG,
        entry_price=Decimal("100"),
        size=Decimal("2"),
        net_pnl=Decimal("10"),
        bars=bars,
    )
    assert result.mfe_price == Decimal("110")
    assert result.mae_price == Decimal("95")
    assert result.mfe_amount == Decimal("20")  # (110-100)*2
    assert result.mae_amount == Decimal("-10")  # (95-100)*2
    assert result.available_profit == Decimal("20")
    assert result.realized_vs_available_pct == pytest.approx(50.0)


def test_calculator_short_mfe_mae() -> None:
    t0 = datetime(2026, 7, 10, 8, 0, tzinfo=UTC)
    bars = [
        _bar(t0, "101", "98"),
        _bar(t0 + timedelta(hours=1), "105", "90"),
    ]
    result = compute_trade_excursions(
        direction=TradeDirection.SHORT,
        entry_price=Decimal("100"),
        size=Decimal("1"),
        net_pnl=Decimal("5"),
        bars=bars,
    )
    assert result.mfe_price == Decimal("90")
    assert result.mae_price == Decimal("105")
    assert result.mfe_amount == Decimal("10")  # (100-90)*1
    assert result.mae_amount == Decimal("-5")  # (100-105)*1
    assert result.available_profit == Decimal("10")
    assert result.realized_vs_available_pct == pytest.approx(50.0)


def test_calculator_missing_size_prices_only() -> None:
    t0 = datetime(2026, 7, 10, 8, 0, tzinfo=UTC)
    result = compute_trade_excursions(
        direction=TradeDirection.LONG,
        entry_price=Decimal("100"),
        size=None,
        net_pnl=Decimal("5"),
        bars=[_bar(t0, "120", "90")],
    )
    assert result.mfe_price == Decimal("120")
    assert result.mae_price == Decimal("90")
    assert result.mfe_amount is None
    assert result.available_profit is None
    assert result.realized_vs_available_pct is None
    assert any("size missing" in lim.lower() for lim in result.limitations)


def test_calculator_empty_bars() -> None:
    result = compute_trade_excursions(
        direction=TradeDirection.LONG,
        entry_price=Decimal("100"),
        size=Decimal("1"),
        net_pnl=Decimal("1"),
        bars=[],
    )
    assert result.candle_count == 0
    assert result.mfe_amount is None
    assert result.limitations


def test_filter_bars_in_window_excludes_outside() -> None:
    entry = datetime(2026, 7, 10, 10, 0, tzinfo=UTC)
    exit_ = datetime(2026, 7, 10, 12, 0, tzinfo=UTC)
    bars = [
        _bar(datetime(2026, 7, 10, 8, 0, tzinfo=UTC), "1", "1"),  # ends before entry
        _bar(datetime(2026, 7, 10, 10, 0, tzinfo=UTC), "2", "2"),
        _bar(datetime(2026, 7, 10, 11, 0, tzinfo=UTC), "3", "3"),
        _bar(datetime(2026, 7, 10, 12, 0, tzinfo=UTC), "5", "5"),  # opens at exit
        _bar(datetime(2026, 7, 10, 13, 0, tzinfo=UTC), "4", "4"),  # starts after exit
    ]
    kept = filter_bars_in_window(bars, entry_time=entry, exit_time=exit_)
    assert [b.high for b in kept] == [Decimal("2"), Decimal("3")]


# ---------------------------------------------------------------------------
# Helpers for API tests
# ---------------------------------------------------------------------------


def _seed_candles(
    factory: sessionmaker[Session],
    *,
    symbol: str = "BTCUSDT",
    exchange: str = "binance",
    timeframe: str = "1h",
    start: datetime,
    highs: list[str],
    lows: list[str],
    gap_after_index: int | None = None,
) -> None:
    with factory() as session:
        t = start
        for i, (high, low) in enumerate(zip(highs, lows, strict=True)):
            if gap_after_index is not None and i == gap_after_index + 1:
                t = t + timedelta(hours=3)  # skip bars → gap
            session.add(
                HistoricalCandle(
                    symbol=symbol,
                    exchange=exchange,
                    timeframe=timeframe,
                    open_time=t,
                    close_time=t + timedelta(hours=1),
                    open=Decimal(low),
                    high=Decimal(high),
                    low=Decimal(low),
                    close=Decimal(high),
                    volume=Decimal("10"),
                    source="mock",
                    is_stale=False,
                )
            )
            t = t + timedelta(hours=1)
        session.commit()


def _seed_trade(
    factory: sessionmaker[Session],
    *,
    organization_id: uuid.UUID = ORG_A,
    user_id: uuid.UUID = USER_A,
    direction: TradeDirection = TradeDirection.LONG,
    entry_price: str = "100",
    exit_price: str = "105",
    size: str = "2",
    net_pnl: str = "10",
    excursion_source: str | None = None,
    mfe_amount: str | None = None,
    exchange: str | None = "binance",
    entry_time: datetime | None = None,
    exit_time: datetime | None = None,
    status: JournalTradeStatus = JournalTradeStatus.CLOSED,
) -> uuid.UUID:
    entry_time = entry_time or datetime(2026, 7, 10, 8, 0, tzinfo=UTC)
    exit_time = exit_time or datetime(2026, 7, 10, 11, 0, tzinfo=UTC)
    with factory() as session:
        row = JournalTrade(
            organization_id=organization_id,
            user_id=user_id,
            source=JournalTradeSource.MANUAL,
            status=status,
            symbol="BTCUSDT",
            exchange=exchange,
            timeframe="1h",
            market_regime=MarketRegime.UNKNOWN,
            direction=direction,
            entry_price=Decimal(entry_price),
            entry_time=entry_time,
            exit_price=Decimal(exit_price),
            exit_time=exit_time,
            size=Decimal(size) if size else None,
            net_pnl=Decimal(net_pnl),
            result=TradeResult.WIN,
            excursion_source=excursion_source,
            mfe_amount=Decimal(mfe_amount) if mfe_amount else None,
            tags=[],
            planned_targets=[{"price": "120", "size_fraction": 1.0}],
            runner_enabled=True,
        )
        session.add(row)
        session.commit()
        return row.id


# ---------------------------------------------------------------------------
# API / integration
# ---------------------------------------------------------------------------


def test_replay_requires_auth(client: tuple[TestClient, sessionmaker[Session]]) -> None:
    test_client, _ = client
    fake = uuid.uuid4()
    assert test_client.post(f"/journal/trades/{fake}/replay-excursions", json={}).status_code == 401


def test_viewer_cannot_replay(client: tuple[TestClient, sessionmaker[Session]]) -> None:
    test_client, factory = client
    trade_id = _seed_trade(factory)
    headers = _auth(test_client, "replay-viewer@test.example")
    resp = test_client.post(
        f"/journal/trades/{trade_id}/replay-excursions",
        headers=headers,
        json={},
    )
    assert resp.status_code == 403


def test_replay_long_trade_persists_and_audits(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    start = datetime(2026, 7, 10, 8, 0, tzinfo=UTC)
    _seed_candles(
        factory,
        start=start,
        highs=["102", "110", "108"],
        lows=["99", "100", "95"],
    )
    # Also seed a post-exit bar for runner analyzer.
    _seed_candles(
        factory,
        start=datetime(2026, 7, 10, 11, 0, tzinfo=UTC),
        highs=["115", "112"],
        lows=["107", "106"],
    )
    trade_id = _seed_trade(factory)
    headers = _auth(test_client, "replay-a@test.example")

    resp = test_client.post(
        f"/journal/trades/{trade_id}/replay-excursions",
        headers=headers,
        json={"persist": True, "include_post_exit_runner": True},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["applied"] is True
    assert Decimal(body["metrics"]["mfe_price"]) == Decimal("110")
    assert Decimal(body["metrics"]["mae_price"]) == Decimal("95")
    assert Decimal(body["metrics"]["mfe_amount"]) == Decimal("20")
    assert Decimal(body["metrics"]["mae_amount"]) == Decimal("-10")
    assert Decimal(body["metrics"]["available_profit"]) == Decimal("20")
    assert body["metrics"]["realized_vs_available_pct"] == pytest.approx(50.0)
    assert body["provenance"]["excursion_source"] == "replay"
    assert body["provenance"]["data_source"] == "mock"
    assert body["provenance"]["candle_count"] >= 3
    assert body["trade"]["excursion_source"] == "replay"
    assert body["post_exit_runner"] is not None

    with factory() as session:
        row = session.get(JournalTrade, trade_id)
        assert row is not None
        assert row.excursion_source == "replay"
        assert row.mfe_amount == Decimal("20")
        assert row.excursion_data_source == "mock"
        assert row.excursion_computed_at is not None
        audits = list(
            session.scalars(
                select(AuditLog).where(
                    AuditLog.action == AuditEventType.JOURNAL_TRADE_EXCURSION_REPLAYED
                )
            )
        )
        assert len(audits) == 1


def test_replay_short_trade(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    start = datetime(2026, 7, 10, 8, 0, tzinfo=UTC)
    _seed_candles(factory, start=start, highs=["101", "105"], lows=["98", "90"])
    trade_id = _seed_trade(
        factory,
        direction=TradeDirection.SHORT,
        entry_price="100",
        exit_price="95",
        size="1",
        net_pnl="5",
        exit_time=datetime(2026, 7, 10, 10, 0, tzinfo=UTC),
    )
    headers = _auth(test_client, "replay-a@test.example")
    resp = test_client.post(
        f"/journal/trades/{trade_id}/replay-excursions",
        headers=headers,
        json={"include_post_exit_runner": False},
    )
    assert resp.status_code == 200, resp.text
    metrics = resp.json()["metrics"]
    assert Decimal(metrics["mfe_price"]) == Decimal("90")
    assert Decimal(metrics["mae_price"]) == Decimal("105")
    assert Decimal(metrics["mfe_amount"]) == Decimal("10")
    assert Decimal(metrics["mae_amount"]) == Decimal("-5")


def test_manual_excursion_not_overwritten_without_force(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    start = datetime(2026, 7, 10, 8, 0, tzinfo=UTC)
    _seed_candles(factory, start=start, highs=["110"], lows=["90"])
    trade_id = _seed_trade(
        factory,
        excursion_source="manual",
        mfe_amount="999",
        exit_time=datetime(2026, 7, 10, 9, 0, tzinfo=UTC),
    )
    headers = _auth(test_client, "replay-a@test.example")
    resp = test_client.post(
        f"/journal/trades/{trade_id}/replay-excursions",
        headers=headers,
        json={"overwrite_policy": ExcursionOverwritePolicy.SKIP_PROTECTED.value},
    )
    assert resp.status_code == 200
    assert resp.json()["applied"] is False
    assert "Protected" in (resp.json()["skipped_reason"] or "")

    with factory() as session:
        row = session.get(JournalTrade, trade_id)
        assert row is not None
        assert row.excursion_source == "manual"
        assert row.mfe_amount == Decimal("999")


def test_force_overwrites_manual(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    start = datetime(2026, 7, 10, 8, 0, tzinfo=UTC)
    _seed_candles(factory, start=start, highs=["110"], lows=["90"])
    trade_id = _seed_trade(
        factory,
        excursion_source="manual",
        mfe_amount="999",
        exit_time=datetime(2026, 7, 10, 9, 0, tzinfo=UTC),
    )
    headers = _auth(test_client, "replay-a@test.example")
    resp = test_client.post(
        f"/journal/trades/{trade_id}/replay-excursions",
        headers=headers,
        json={"overwrite_policy": "force"},
    )
    assert resp.status_code == 200
    assert resp.json()["applied"] is True
    with factory() as session:
        row = session.get(JournalTrade, trade_id)
        assert row is not None
        assert row.excursion_source == "replay"
        assert row.mfe_amount == Decimal("20")  # (110-100)*2


def test_missing_candles_safe_skip(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    trade_id = _seed_trade(factory)
    headers = _auth(test_client, "replay-a@test.example")
    resp = test_client.post(
        f"/journal/trades/{trade_id}/replay-excursions",
        headers=headers,
        json={},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["applied"] is False
    assert body["skipped_reason"] == "missing_candles"
    assert body["metrics"] is None


def test_invalid_window_and_open_trade(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "replay-a@test.example")
    bad_window = _seed_trade(
        factory,
        entry_time=datetime(2026, 7, 10, 12, 0, tzinfo=UTC),
        exit_time=datetime(2026, 7, 10, 10, 0, tzinfo=UTC),
    )
    resp = test_client.post(
        f"/journal/trades/{bad_window}/replay-excursions",
        headers=headers,
        json={},
    )
    assert resp.status_code == 200
    assert "Invalid trade window" in (resp.json()["skipped_reason"] or "")

    open_id = _seed_trade(factory, status=JournalTradeStatus.OPEN)
    resp2 = test_client.post(
        f"/journal/trades/{open_id}/replay-excursions",
        headers=headers,
        json={},
    )
    assert resp2.status_code == 200
    assert "closed" in (resp2.json()["skipped_reason"] or "").lower()


def test_gap_flags_incomplete_provenance(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    start = datetime(2026, 7, 10, 8, 0, tzinfo=UTC)
    _seed_candles(
        factory,
        start=start,
        highs=["102", "110", "108", "107"],
        lows=["99", "100", "95", "96"],
        gap_after_index=0,
    )
    trade_id = _seed_trade(
        factory,
        exit_time=datetime(2026, 7, 10, 14, 0, tzinfo=UTC),
    )
    headers = _auth(test_client, "replay-a@test.example")
    resp = test_client.post(
        f"/journal/trades/{trade_id}/replay-excursions",
        headers=headers,
        json={},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["applied"] is True
    assert body["provenance"]["gaps_detected"] >= 1
    assert body["provenance"]["window_complete"] is False
    assert body["provenance"]["is_stale"] is True


def test_tenant_isolation(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    start = datetime(2026, 7, 10, 8, 0, tzinfo=UTC)
    _seed_candles(factory, start=start, highs=["110"], lows=["90"])
    trade_a = _seed_trade(factory, exit_time=datetime(2026, 7, 10, 9, 0, tzinfo=UTC))
    headers_b = _auth(test_client, "replay-b@test.example")
    resp = test_client.post(
        f"/journal/trades/{trade_a}/replay-excursions",
        headers=headers_b,
        json={},
    )
    assert resp.status_code == 404


def test_batch_replay_and_stats_integration(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    start = datetime(2026, 7, 10, 8, 0, tzinfo=UTC)
    _seed_candles(
        factory,
        start=start,
        highs=["102", "110", "108"],
        lows=["99", "100", "95"],
    )
    t1 = _seed_trade(factory)
    t2 = _seed_trade(
        factory,
        excursion_source="manual",
        mfe_amount="50",
        exit_time=datetime(2026, 7, 10, 11, 30, tzinfo=UTC),
    )
    headers = _auth(test_client, "replay-a@test.example")

    batch = test_client.post(
        "/journal/trades/replay-excursions",
        headers=headers,
        json={"limit": 10, "include_post_exit_runner": False},
    )
    assert batch.status_code == 200, batch.text
    body = batch.json()
    assert body["applied"] == 1
    assert body["skipped"] + body["failed"] >= 0
    applied_ids = {r["journal_trade_id"] for r in body["results"] if r["applied"]}
    assert str(t1) in applied_ids
    assert str(t2) not in applied_ids  # manual protected

    stats = test_client.get("/journal/statistics", headers=headers)
    assert stats.status_code == 200
    overall = stats.json()["overall"]
    # Replay wrote MFE=20 for t1; manual t2 still has mfe_amount=50
    assert overall["mfe_sample_count"] == 2
    assert Decimal(overall["average_mfe_amount"]) == Decimal("35")  # (20+50)/2


def test_missing_exchange_skipped(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    trade_id = _seed_trade(factory, exchange=None)
    headers = _auth(test_client, "replay-a@test.example")
    resp = test_client.post(
        f"/journal/trades/{trade_id}/replay-excursions",
        headers=headers,
        json={},
    )
    assert resp.status_code == 200
    assert "Exchange required" in (resp.json()["skipped_reason"] or "")

    # Override via request
    start = datetime(2026, 7, 10, 8, 0, tzinfo=UTC)
    _seed_candles(factory, start=start, highs=["110"], lows=["90"])
    resp2 = test_client.post(
        f"/journal/trades/{trade_id}/replay-excursions",
        headers=headers,
        json={"exchange": "binance", "include_post_exit_runner": False},
    )
    assert resp2.status_code == 200
    assert resp2.json()["applied"] is True

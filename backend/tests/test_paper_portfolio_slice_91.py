"""Tests for Slice 91A — unified paper portfolio performance (read-only)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db.models import (
    Membership,
    Organization,
    PaperTrade,
    PaperValidationRun,
    PerformanceSnapshot,
    Position,
    User,
    UserRiskSettings,
    UserStrategy,
    UserStrategyVersion,
)
from app.db.session import get_session
from app.main import create_app
from app.schemas.common import (
    BacktestStatus,
    MembershipRole,
    PaperTradeStatus,
    PaperValidationStatus,
    PositionStatus,
    StrategyId,
    StrategyValidationStatus,
    TradeDirection,
)
from app.security.passwords import hash_password
from app.security.rate_limit import reset_rate_limiter
from app.services.paper_portfolio_service import PaperPortfolioService
from app.services.performance.equity_calculator import PortfolioEquityCalculator
from app.services.performance.unified_trade import (
    PortfolioSourceFilter,
    PortfolioTradeFilters,
    UnifiedTradeLoader,
)

ORG_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a0")
USER_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a1")
ORG_B = uuid.UUID("00000000-0000-0000-0000-0000000000b0")
USER_B = uuid.UUID("00000000-0000-0000-0000-0000000000b1")
STRATEGY_ID = uuid.UUID("00000000-0000-0000-0000-0000000000c0")
VERSION_ID = uuid.UUID("00000000-0000-0000-0000-0000000000c1")
RUN_ID = uuid.UUID("00000000-0000-0000-0000-0000000000d0")

_BASE = {
    "environment": "local",
    "log_json": False,
    "execution_mode": "paper",
    "enable_real_trading": False,
    "database_url": "sqlite+pysqlite:///:memory:",
    "jwt_secret": "paper-portfolio-test-secret-min-32-chars",
    "rate_limit_use_redis": False,
    "access_token_denylist_use_redis": False,
    "provider_mode": "mock",
    "market_data_provider": "mock",
    "worker_enabled": False,
    "market_watcher_enabled": False,
    "market_watcher_bridge_enabled": False,
}


@dataclass
class Harness:
    client: TestClient
    factory: sessionmaker[Session]


@pytest.fixture(autouse=True)
def _reset_limiter() -> None:
    reset_rate_limiter()


_TEST_PASSWORD = "TestPassword123!"


@pytest.fixture
def db() -> Iterator[sessionmaker[Session]]:
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
    settings = Settings(
        environment="local",
        log_json=False,
        execution_mode="paper",
        enable_real_trading=False,
        database_url="sqlite+pysqlite:///:memory:",
        jwt_secret="paper-portfolio-test-secret-min-32-chars",
        rate_limit_use_redis=False,
        access_token_denylist_use_redis=False,
        provider_mode="mock",
        market_data_provider="mock",
    )
    with factory() as session:
        session.add(Organization(id=ORG_ID, name="Portfolio Org"))
        session.add(Organization(id=ORG_B, name="Other Org"))
        session.flush()
        session.add(
            User(
                id=USER_ID,
                email="portfolio@test.example",
                hashed_password=hash_password(_TEST_PASSWORD, settings),
            )
        )
        session.add(
            User(
                id=USER_B,
                email="other@test.example",
                hashed_password=hash_password(_TEST_PASSWORD, settings),
            )
        )
        session.flush()
        session.add(Membership(user_id=USER_ID, organization_id=ORG_ID, role=MembershipRole.OWNER))
        session.add(Membership(user_id=USER_B, organization_id=ORG_B, role=MembershipRole.OWNER))
        _seed_strategy_stack(session)
        session.commit()
    yield factory
    engine.dispose()


@pytest.fixture
def harness(db: sessionmaker[Session]) -> Iterator[Harness]:
    def _override_session() -> Iterator[Session]:
        with db() as session:
            yield session

    get_settings.cache_clear()
    app = create_app(settings=Settings(**_BASE))
    app.dependency_overrides[get_session] = _override_session

    with TestClient(app) as client:
        yield Harness(client=client, factory=db)

    app.dependency_overrides.clear()
    get_settings.cache_clear()


def _seed_strategy_stack(session: Session) -> None:
    session.add(
        UserStrategy(
            id=STRATEGY_ID,
            organization_id=ORG_ID,
            user_id=USER_ID,
            name="Breakout Alpha",
            setup_type=StrategyId.HTF_TREND_PULLBACK,
        )
    )
    session.flush()
    session.add(
        UserStrategyVersion(
            id=VERSION_ID,
            strategy_id=STRATEGY_ID,
            version=1,
            card={"strategy_name": "Breakout Alpha"},
            validation_status=StrategyValidationStatus.DRAFT,
            backtest_status=BacktestStatus.NOT_RUN,
            paper_validation_status=PaperValidationStatus.IN_PROGRESS,
        )
    )
    session.flush()
    session.add(
        PaperValidationRun(
            id=RUN_ID,
            strategy_id=STRATEGY_ID,
            strategy_version_id=VERSION_ID,
            organization_id=ORG_ID,
            user_id=USER_ID,
            status=PaperValidationStatus.IN_PROGRESS,
            config={"condition": "liquidity_sweep"},
        )
    )


def _closed_position(
    *,
    pnl: str,
    closed_at: datetime,
    symbol: str = "BTCUSDT",
    position_id: uuid.UUID | None = None,
) -> Position:
    return Position(
        id=position_id or uuid.uuid4(),
        organization_id=ORG_ID,
        user_id=USER_ID,
        strategy_id=StrategyId.HTF_TREND_PULLBACK,
        symbol=symbol,
        direction=TradeDirection.LONG,
        size=Decimal("1"),
        entry_price=Decimal("100"),
        leverage=Decimal("1"),
        stop_loss=Decimal("90"),
        realized_pnl=Decimal(pnl),
        status=PositionStatus.CLOSED,
        opened_at=closed_at - timedelta(hours=1),
        closed_at=closed_at,
    )


def _closed_paper_trade(*, pnl: str, exit_time: datetime, symbol: str = "ETHUSDT") -> PaperTrade:
    return PaperTrade(
        paper_validation_run_id=RUN_ID,
        strategy_id=STRATEGY_ID,
        strategy_version_id=VERSION_ID,
        organization_id=ORG_ID,
        user_id=USER_ID,
        symbol=symbol,
        exchange="binance",
        timeframe="4h",
        direction=TradeDirection.LONG,
        entry_price=Decimal("2000"),
        entry_time=exit_time - timedelta(hours=2),
        size=Decimal("0.5"),
        stop_loss=Decimal("1900"),
        status=PaperTradeStatus.CLOSED,
        exit_price=Decimal("2100"),
        exit_time=exit_time,
        net_pnl=Decimal(pnl),
        gross_pnl=Decimal(pnl),
    )


def _auth_headers(client: TestClient, email: str, password: str = _TEST_PASSWORD) -> dict[str, str]:
    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    token = login.json()["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_unified_loader_merges_sources_without_duplicates(db: sessionmaker[Session]) -> None:
    day = datetime(2026, 3, 1, 12, tzinfo=UTC)
    with db() as session:
        session.add(_closed_position(pnl="100", closed_at=day))
        session.add(_closed_paper_trade(pnl="50", exit_time=day + timedelta(hours=1)))
        session.commit()
        records = UnifiedTradeLoader(session).load(
            organization_id=ORG_ID,
            user_id=USER_ID,
        )
    assert len(records) == 2
    lanes = {r.execution_lane for r in records}
    assert lanes == {PortfolioSourceFilter.PROPOSAL_FLOW, PortfolioSourceFilter.PAPER_VALIDATION}
    assert len({r.trade_id for r in records}) == 2


def test_source_filter_limits_execution_lane(db: sessionmaker[Session]) -> None:
    day = datetime(2026, 3, 2, 12, tzinfo=UTC)
    with db() as session:
        session.add(_closed_position(pnl="100", closed_at=day))
        session.add(_closed_paper_trade(pnl="50", exit_time=day))
        session.commit()
        records = UnifiedTradeLoader(session).load(
            organization_id=ORG_ID,
            user_id=USER_ID,
            filters=PortfolioTradeFilters(source=PortfolioSourceFilter.PROPOSAL_FLOW),
        )
    assert len(records) == 1
    assert records[0].execution_lane is PortfolioSourceFilter.PROPOSAL_FLOW


def test_date_filter_on_closed_timestamp(db: sessionmaker[Session]) -> None:
    early = datetime(2026, 3, 1, 12, tzinfo=UTC)
    late = datetime(2026, 3, 10, 12, tzinfo=UTC)
    with db() as session:
        session.add(_closed_position(pnl="100", closed_at=early))
        session.add(_closed_position(pnl="50", closed_at=late))
        session.commit()
        records = UnifiedTradeLoader(session).load(
            organization_id=ORG_ID,
            user_id=USER_ID,
            filters=PortfolioTradeFilters(
                start_date=date(2026, 3, 5),
                end_date=date(2026, 3, 31),
                timezone="UTC",
            ),
        )
    assert len(records) == 1
    assert records[0].realized_pnl == Decimal("50")


def test_starting_balance_fallback(db: sessionmaker[Session]) -> None:
    with db() as session:
        portfolio = PaperPortfolioService(session, clock=lambda: datetime(2026, 3, 1, tzinfo=UTC))
        report = portfolio.build_portfolio(organization_id=ORG_ID, user_id=USER_ID)
    assert report.account.starting_balance == Decimal("10000")


def test_starting_balance_from_risk_settings(db: sessionmaker[Session]) -> None:
    with db() as session:
        session.add(
            UserRiskSettings(
                organization_id=ORG_ID,
                user_id=USER_ID,
                default_account_balance=Decimal("25000"),
            )
        )
        session.commit()
        report = PaperPortfolioService(session).build_portfolio(
            organization_id=ORG_ID,
            user_id=USER_ID,
        )
    assert report.account.starting_balance == Decimal("25000")


def test_current_equity_math(db: sessionmaker[Session]) -> None:
    day = datetime(2026, 3, 3, 12, tzinfo=UTC)
    with db() as session:
        session.add(_closed_position(pnl="100", closed_at=day))
        session.add(
            Position(
                organization_id=ORG_ID,
                user_id=USER_ID,
                symbol="BTCUSDT",
                direction=TradeDirection.LONG,
                size=Decimal("1"),
                entry_price=Decimal("100"),
                leverage=Decimal("1"),
                unrealized_pnl=Decimal("25"),
                status=PositionStatus.OPEN,
                opened_at=day,
            )
        )
        session.commit()
        report = PaperPortfolioService(
            session,
            clock=lambda: datetime(2026, 3, 3, 18, tzinfo=UTC),
        ).build_portfolio(organization_id=ORG_ID, user_id=USER_ID)
    assert report.account.cumulative_realized_pnl == Decimal("100")
    assert report.account.unrealized_pnl == Decimal("25")
    assert report.account.current_equity == Decimal("10125")


def test_equity_curve_starts_at_starting_balance(db: sessionmaker[Session]) -> None:
    day = datetime(2026, 3, 4, 12, tzinfo=UTC)
    with db() as session:
        session.add(_closed_position(pnl="100", closed_at=day))
        session.commit()
        report = PaperPortfolioService(
            session,
            clock=lambda: datetime(2026, 3, 4, 18, tzinfo=UTC),
        ).build_portfolio(organization_id=ORG_ID, user_id=USER_ID)
    assert report.equity_curve[0].event == "start"
    assert report.equity_curve[0].equity == Decimal("10000")


def test_equity_curve_includes_closed_trade_and_live_points(db: sessionmaker[Session]) -> None:
    day = datetime(2026, 3, 5, 12, tzinfo=UTC)
    with db() as session:
        session.add(_closed_position(pnl="100", closed_at=day))
        session.add(_closed_position(pnl="-40", closed_at=day + timedelta(hours=1)))
        session.commit()
        report = PaperPortfolioService(
            session,
            clock=lambda: datetime(2026, 3, 5, 18, tzinfo=UTC),
        ).build_portfolio(organization_id=ORG_ID, user_id=USER_ID)
    events = [p.event for p in report.equity_curve]
    assert events == ["start", "trade_close", "trade_close", "live"]
    assert report.equity_curve[-1].equity == Decimal("10060")


def test_daily_pnl_and_drawdown(db: sessionmaker[Session]) -> None:
    day = datetime(2026, 3, 6, 10, tzinfo=UTC)
    with db() as session:
        session.add(_closed_position(pnl="100", closed_at=day))
        session.add(_closed_position(pnl="-60", closed_at=day + timedelta(hours=2)))
        session.commit()
        report = PaperPortfolioService(
            session,
            clock=lambda: datetime(2026, 3, 6, 18, tzinfo=UTC),
        ).build_portfolio(organization_id=ORG_ID, user_id=USER_ID)
    assert len(report.daily_series) == 1
    point = report.daily_series[0]
    assert point.daily_pnl == Decimal("40")
    assert point.daily_drawdown == Decimal("60")


def test_max_drawdown_on_dollar_equity(db: sessionmaker[Session]) -> None:
    t0 = datetime(2026, 3, 7, 10, tzinfo=UTC)
    with db() as session:
        session.add(_closed_position(pnl="100", closed_at=t0))
        session.add(_closed_position(pnl="-150", closed_at=t0 + timedelta(hours=1)))
        session.add(_closed_position(pnl="50", closed_at=t0 + timedelta(hours=2)))
        session.commit()
        report = PaperPortfolioService(
            session,
            clock=lambda: datetime(2026, 3, 7, 18, tzinfo=UTC),
        ).build_portfolio(organization_id=ORG_ID, user_id=USER_ID)
    # Equity: 10000 -> 10100 -> 9950 -> 10000. Peak 10100, trough 9950 => DD 150.
    assert report.metrics.max_drawdown == Decimal("150")


def test_open_paper_trade_unrealized_limitation(db: sessionmaker[Session]) -> None:
    day = datetime(2026, 3, 8, 12, tzinfo=UTC)
    with db() as session:
        session.add(
            PaperTrade(
                paper_validation_run_id=RUN_ID,
                strategy_id=STRATEGY_ID,
                strategy_version_id=VERSION_ID,
                organization_id=ORG_ID,
                user_id=USER_ID,
                symbol="ETHUSDT",
                exchange="binance",
                timeframe="4h",
                direction=TradeDirection.LONG,
                status=PaperTradeStatus.OPEN,
                entry_time=day,
            )
        )
        session.commit()
        report = PaperPortfolioService(
            session,
            clock=lambda: datetime(2026, 3, 8, 18, tzinfo=UTC),
        ).build_portfolio(organization_id=ORG_ID, user_id=USER_ID)
    joined = " ".join(report.account.limitations + report.open_exposure.limitations)
    assert "mark-to-market" in joined.lower()
    assert report.account.unrealized_pnl is None


def test_equity_calculator_daily_series_empty_without_trades() -> None:
    result = PortfolioEquityCalculator().build(
        starting_balance=Decimal("10000"),
        records=[],
        unrealized_pnl=None,
        as_of=datetime(2026, 3, 1, tzinfo=UTC),
        timezone="UTC",
    )
    assert result.equity_curve[0].equity == Decimal("10000")
    assert result.daily_series == ()


def test_portfolio_api_requires_auth(harness: Harness) -> None:
    resp = harness.client.get("/performance/portfolio")
    assert resp.status_code == 401


def test_viewer_can_read_portfolio(harness: Harness, db: sessionmaker[Session]) -> None:
    viewer_id = uuid.uuid4()
    settings = Settings(**_BASE)
    with db() as session:
        session.add(
            User(
                id=viewer_id,
                email="viewer@test.example",
                hashed_password=hash_password(_TEST_PASSWORD, settings),
            )
        )
        session.flush()
        session.add(
            Membership(user_id=viewer_id, organization_id=ORG_ID, role=MembershipRole.VIEWER)
        )
        session.commit()

    headers = _auth_headers(harness.client, "viewer@test.example")
    resp = harness.client.get("/performance/portfolio", headers=headers)
    assert resp.status_code == 200


def test_tenant_isolation_on_portfolio_api(harness: Harness, db: sessionmaker[Session]) -> None:
    day = datetime(2026, 3, 9, 12, tzinfo=UTC)
    with db() as session:
        session.add(_closed_position(pnl="500", closed_at=day))
        session.add(
            Position(
                organization_id=ORG_B,
                user_id=USER_B,
                symbol="BTCUSDT",
                direction=TradeDirection.LONG,
                size=Decimal("1"),
                entry_price=Decimal("100"),
                leverage=Decimal("1"),
                realized_pnl=Decimal("999"),
                status=PositionStatus.CLOSED,
                opened_at=day - timedelta(hours=1),
                closed_at=day,
            )
        )
        session.commit()

    headers = _auth_headers(harness.client, "portfolio@test.example")

    body = harness.client.get("/performance/portfolio", headers=headers).json()
    assert body["account"]["cumulative_realized_pnl"].startswith("500")
    assert body["account"]["cumulative_realized_pnl"] != "999"


def test_portfolio_response_has_safety_banner(harness: Harness) -> None:
    headers = _auth_headers(harness.client, "portfolio@test.example")
    body = harness.client.get("/performance/portfolio", headers=headers).json()
    assert body["safety"]["paper_only"] is True
    assert body["safety"]["real_trading_enabled"] is False
    dumped = str(body).lower()
    assert "real money" in dumped
    assert "investment advice" in dumped
    assert "ready for live" not in dumped
    assert "enable trading" not in dumped


def test_list_snapshots_endpoint(harness: Harness, db: sessionmaker[Session]) -> None:
    with db() as session:
        session.add(
            PerformanceSnapshot(
                organization_id=ORG_ID,
                user_id=USER_ID,
                scope="account",
                as_of=datetime(2026, 3, 1, tzinfo=UTC),
                trade_count=2,
                net_pnl=Decimal("70"),
                gross_profit=Decimal("100"),
                gross_loss=Decimal("-30"),
                win_rate=0.5,
                max_drawdown=Decimal("30"),
                metrics={},
            )
        )
        session.commit()
    headers = _auth_headers(harness.client, "portfolio@test.example")

    resp = harness.client.get("/performance/snapshots", headers=headers)
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["total"] == 1
    assert payload["items"][0]["net_pnl"].startswith("70")


def test_legacy_performance_report_still_works(db: sessionmaker[Session]) -> None:
    day = datetime(2026, 3, 10, 12, tzinfo=UTC)
    with db() as session:
        session.add(_closed_position(pnl="100", closed_at=day))
        session.add(_closed_paper_trade(pnl="50", exit_time=day))
        session.commit()
        from app.services.performance_service import PerformanceService

        report = PerformanceService(session).build_report(organization_id=ORG_ID)
    assert report.account.trade_count == 1
    assert report.account.net_pnl == Decimal("100")

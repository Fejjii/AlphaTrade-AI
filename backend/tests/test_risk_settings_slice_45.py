"""Slice 45 — risk settings API and discipline score dashboard integration."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
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
    DailyRiskState,
    Membership,
    Organization,
    PaperTrade,
    PaperValidationRun,
    Position,
    User,
    UserRiskSettings,
    UserStrategy,
    UserStrategyVersion,
)
from app.db.session import get_session
from app.main import create_app
from app.schemas.common import (
    AuditEventType,
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
from app.services.dashboard.daily_discipline import build_daily_discipline_snapshot
from app.services.dashboard_summary_service import DashboardSummaryService
from app.tools.registry import build_default_registry

ORG_A = uuid.UUID("00000000-0000-0000-0000-000000000060")
USER_A = uuid.UUID("00000000-0000-0000-0000-000000000061")
STRATEGY_A = uuid.UUID("00000000-0000-0000-0000-000000000062")
RUN_A = uuid.UUID("00000000-0000-0000-0000-000000000063")
VERSION_A = uuid.UUID("00000000-0000-0000-0000-000000000064")


@pytest.fixture
def risk_db() -> Iterator[tuple[sessionmaker[Session], Settings]]:
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
        jwt_secret="risk-slice45-test-secret-key-32b",
        rate_limit_use_redis=False,
        access_token_denylist_use_redis=False,
        provider_mode="mock",
        market_data_provider="mock",
    )
    with factory() as session:
        session.add(Organization(id=ORG_A, name="Risk Org"))
        session.add(
            User(
                id=USER_A,
                email="risk-a@test.example",
                hashed_password=hash_password("TestPassword123!", settings),
                timezone="UTC",
            )
        )
        session.flush()
        session.add(Membership(user_id=USER_A, organization_id=ORG_A, role=MembershipRole.OWNER))
        session.commit()
    yield factory, settings
    engine.dispose()


@pytest.fixture
def risk_client(risk_db: tuple[sessionmaker[Session], Settings]) -> TestClient:
    factory, settings = risk_db
    app = create_app(settings)

    def _override_session() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = _override_session
    return TestClient(app)


def _auth_headers(client: TestClient) -> dict[str, str]:
    login = client.post(
        "/auth/login",
        json={"email": "risk-a@test.example", "password": "TestPassword123!"},
    )
    assert login.status_code == 200
    token = login.json()["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _seed_strategy_stack(session: Session) -> None:
    session.add(
        UserStrategy(
            id=STRATEGY_A,
            organization_id=ORG_A,
            user_id=USER_A,
            name="Risk Strategy",
            setup_type=StrategyId.HTF_TREND_PULLBACK,
            current_version=1,
        )
    )
    session.flush()
    session.add(
        UserStrategyVersion(
            id=VERSION_A,
            strategy_id=STRATEGY_A,
            version=1,
            card={
                "strategy_name": "Risk Strategy",
                "market_type": "crypto_perp",
                "asset_universe": ["BTCUSDT"],
                "timeframes": ["15m"],
                "entry_conditions": ["Pullback"],
                "confirmation_conditions": ["RSI"],
                "invalidation": ["Break low"],
                "stop_loss": ["2%"],
                "take_profit_plan": ["1R"],
                "runner_plan": ["Trail"],
                "position_sizing": ["1%"],
                "validation_status": "draft",
            },
            validation_status=StrategyValidationStatus.DRAFT,
            backtest_status=BacktestStatus.NOT_RUN,
            paper_validation_status=PaperValidationStatus.IN_PROGRESS,
        )
    )
    session.flush()
    session.add(
        PaperValidationRun(
            id=RUN_A,
            strategy_id=STRATEGY_A,
            strategy_version_id=VERSION_A,
            organization_id=ORG_A,
            user_id=USER_A,
            status=PaperValidationStatus.IN_PROGRESS,
            paper_eligible=True,
        )
    )
    session.flush()


def _seed_open_paper_trade(
    session: Session,
    *,
    status: PaperTradeStatus = PaperTradeStatus.OPEN,
) -> None:
    _seed_strategy_stack(session)
    now = datetime.now(UTC)
    session.add(
        PaperTrade(
            paper_validation_run_id=RUN_A,
            strategy_id=STRATEGY_A,
            strategy_version_id=VERSION_A,
            organization_id=ORG_A,
            user_id=USER_A,
            symbol="BTCUSDT",
            exchange="binance",
            timeframe="15m",
            direction=TradeDirection.LONG,
            entry_price=Decimal("60000"),
            entry_time=now,
            size=Decimal("0.01"),
            status=status,
            exit_time=now if status == PaperTradeStatus.CLOSED else None,
            net_pnl=Decimal("42") if status == PaperTradeStatus.CLOSED else None,
            gross_pnl=Decimal("42") if status == PaperTradeStatus.CLOSED else None,
        )
    )


def test_get_risk_settings_returns_defaults(risk_client: TestClient, risk_db) -> None:
    headers = _auth_headers(risk_client)
    resp = risk_client.get("/risk/settings", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["using_defaults"] is True
    assert body["max_trades_per_day"] == 20


def test_patch_risk_settings_validates_positive_limits(risk_client: TestClient) -> None:
    headers = _auth_headers(risk_client)
    bad = risk_client.patch(
        "/risk/settings",
        headers=headers,
        json={"daily_loss_limit": "-5"},
    )
    assert bad.status_code == 422

    good = risk_client.patch(
        "/risk/settings",
        headers=headers,
        json={
            "daily_loss_limit": "50",
            "daily_target": "100",
            "max_trades_per_day": 3,
            "max_risk_per_trade_percent": "2",
        },
    )
    assert good.status_code == 200
    assert good.json()["daily_loss_limit"] == "50"
    assert good.json()["max_trades_per_day"] == 3
    assert good.json()["using_defaults"] is False


def test_patch_risk_settings_audit_logged(
    risk_client: TestClient, risk_db: tuple[sessionmaker[Session], Settings]
) -> None:
    factory, _ = risk_db
    headers = _auth_headers(risk_client)
    resp = risk_client.patch(
        "/risk/settings",
        headers=headers,
        json={"max_trades_per_day": 5},
    )
    assert resp.status_code == 200
    with factory() as session:
        rows = session.scalars(
            select(AuditLog).where(AuditLog.action == AuditEventType.RISK_SETTINGS_UPDATED)
        ).all()
    assert len(rows) >= 1


def test_invalid_timezone_falls_back(risk_client: TestClient) -> None:
    headers = _auth_headers(risk_client)
    resp = risk_client.patch(
        "/risk/settings",
        headers=headers,
        json={"timezone": "Not/A/Timezone"},
    )
    assert resp.status_code == 200
    assert resp.json()["timezone"] == "UTC"
    assert resp.json()["timezone_fallback"] is True


def test_dashboard_uses_risk_settings_when_daily_state_missing(
    risk_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, _settings = risk_db
    with factory() as session:
        session.add(
            UserRiskSettings(
                organization_id=ORG_A,
                user_id=USER_A,
                daily_loss_limit=Decimal("40"),
                daily_target=Decimal("80"),
                max_trades_per_day=4,
            )
        )
        session.commit()
        snapshot = build_daily_discipline_snapshot(session, organization_id=ORG_A, user_id=USER_A)
    assert snapshot.risk_settings_source == "user_risk_settings"
    assert snapshot.daily_loss_limit == Decimal("40")
    assert snapshot.max_trades_per_day == 4


def test_dashboard_prefers_daily_state_when_present(
    risk_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, _ = risk_db
    today = datetime.now(UTC).date()
    with factory() as session:
        session.add(
            UserRiskSettings(
                organization_id=ORG_A,
                user_id=USER_A,
                daily_loss_limit=Decimal("40"),
                max_trades_per_day=4,
            )
        )
        session.add(
            DailyRiskState(
                organization_id=ORG_A,
                user_id=USER_A,
                day=today,
                daily_loss_limit=Decimal("100"),
                max_trades_per_day=2,
            )
        )
        session.commit()
        snapshot = build_daily_discipline_snapshot(session, organization_id=ORG_A, user_id=USER_A)
    assert snapshot.risk_settings_source == "configured_daily_state"
    assert snapshot.daily_loss_limit == Decimal("100")
    assert snapshot.max_trades_per_day == 2


def test_loss_lock_uses_configured_settings(
    risk_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, _ = risk_db
    now = datetime.now(UTC)
    with factory() as session:
        session.add(
            UserRiskSettings(
                organization_id=ORG_A,
                user_id=USER_A,
                daily_loss_limit=Decimal("25"),
            )
        )
        _seed_strategy_stack(session)
        session.add(
            PaperTrade(
                paper_validation_run_id=RUN_A,
                strategy_id=STRATEGY_A,
                strategy_version_id=VERSION_A,
                organization_id=ORG_A,
                user_id=USER_A,
                symbol="BTCUSDT",
                exchange="binance",
                timeframe="15m",
                direction=TradeDirection.LONG,
                entry_price=Decimal("60000"),
                entry_time=now,
                size=Decimal("0.01"),
                status=PaperTradeStatus.CLOSED,
                exit_time=now,
                net_pnl=Decimal("-30"),
                gross_pnl=Decimal("-30"),
            )
        )
        session.commit()
        snapshot = build_daily_discipline_snapshot(session, organization_id=ORG_A, user_id=USER_A)
    assert snapshot.loss_lock_active is True


def test_green_day_uses_configured_settings(
    risk_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, _ = risk_db
    now = datetime.now(UTC)
    with factory() as session:
        session.add(
            UserRiskSettings(
                organization_id=ORG_A,
                user_id=USER_A,
                daily_target=Decimal("10"),
                green_day_protection_enabled=True,
            )
        )
        _seed_strategy_stack(session)
        session.add(
            PaperTrade(
                paper_validation_run_id=RUN_A,
                strategy_id=STRATEGY_A,
                strategy_version_id=VERSION_A,
                organization_id=ORG_A,
                user_id=USER_A,
                symbol="BTCUSDT",
                exchange="binance",
                timeframe="15m",
                direction=TradeDirection.LONG,
                entry_price=Decimal("60000"),
                entry_time=now,
                size=Decimal("0.01"),
                status=PaperTradeStatus.CLOSED,
                exit_time=now,
                net_pnl=Decimal("15"),
                gross_pnl=Decimal("15"),
            )
        )
        session.commit()
        snapshot = build_daily_discipline_snapshot(session, organization_id=ORG_A, user_id=USER_A)
    assert snapshot.green_day_protection_active is True


def test_overtrading_uses_max_trades_per_day(
    risk_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, _ = risk_db
    now = datetime.now(UTC)
    with factory() as session:
        session.add(
            UserRiskSettings(
                organization_id=ORG_A,
                user_id=USER_A,
                max_trades_per_day=1,
                overtrading_guard_enabled=True,
            )
        )
        _seed_strategy_stack(session)
        for idx in range(2):
            session.add(
                PaperTrade(
                    paper_validation_run_id=RUN_A,
                    strategy_id=STRATEGY_A,
                    strategy_version_id=VERSION_A,
                    organization_id=ORG_A,
                    user_id=USER_A,
                    symbol="BTCUSDT",
                    exchange="binance",
                    timeframe="15m",
                    direction=TradeDirection.LONG,
                    entry_price=Decimal("60000"),
                    entry_time=now,
                    size=Decimal("0.01"),
                    status=PaperTradeStatus.CLOSED if idx else PaperTradeStatus.OPEN,
                    exit_time=now if idx else None,
                    net_pnl=Decimal("1") if idx else None,
                    gross_pnl=Decimal("1") if idx else None,
                )
            )
        session.commit()
        snapshot = build_daily_discipline_snapshot(session, organization_id=ORG_A, user_id=USER_A)
    assert snapshot.overtrading_warning_active is True


def test_dashboard_includes_discipline_score(
    risk_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, settings = risk_db
    with factory() as session:
        summary = DashboardSummaryService(session, settings).summarize(
            organization_id=ORG_A,
            user_id=USER_A,
        )
    assert summary.discipline_score is not None
    assert summary.discipline_score.score is not None


def test_open_paper_trades_includes_paper_trade_open_rows(
    risk_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, settings = risk_db
    now = datetime.now(UTC)
    with factory() as session:
        _seed_strategy_stack(session)
        now = datetime.now(UTC)
        session.add(
            PaperTrade(
                paper_validation_run_id=RUN_A,
                strategy_id=STRATEGY_A,
                strategy_version_id=VERSION_A,
                organization_id=ORG_A,
                user_id=USER_A,
                symbol="ETHUSDT",
                exchange="binance",
                timeframe="15m",
                direction=TradeDirection.SHORT,
                entry_price=Decimal("3000"),
                entry_time=now,
                size=Decimal("0.1"),
                status=PaperTradeStatus.OPEN,
            )
        )
        session.add(
            Position(
                organization_id=ORG_A,
                user_id=USER_A,
                symbol="BTCUSDT",
                direction=TradeDirection.LONG,
                size=Decimal("0.01"),
                entry_price=Decimal("60000"),
                leverage=Decimal("1"),
                unrealized_pnl=Decimal("5"),
                status=PositionStatus.OPEN,
                opened_at=now,
            )
        )
        session.commit()
        summary = DashboardSummaryService(session, settings).summarize(
            organization_id=ORG_A,
            user_id=USER_A,
        )
    assert summary.open_paper_trades_summary is not None
    assert summary.open_paper_trades_summary.paper_validation_count == 1
    assert summary.open_paper_trades_summary.proposal_flow_count == 1


def test_daily_pnl_includes_closed_paper_trade_rows(
    risk_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, _ = risk_db
    with factory() as session:
        _seed_open_paper_trade(session, status=PaperTradeStatus.CLOSED)
        session.commit()
        snapshot = build_daily_discipline_snapshot(session, organization_id=ORG_A, user_id=USER_A)
    assert snapshot.realized_pnl_today_paper == Decimal("42")
    assert snapshot.pnl_sources["paper_validation_closed"] == Decimal("42")


def test_agent_risk_settings_update_requires_confirmation(
    risk_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, settings = risk_db
    with factory() as session:
        registry = build_default_registry(settings, db_session=session)
        blocked = registry.execute(
            "risk_settings_tool",
            {
                "action": "update",
                "organization_id": str(ORG_A),
                "user_id": str(USER_A),
                "max_trades_per_day": 3,
            },
        )
        assert blocked.success is False
        allowed = registry.execute(
            "risk_settings_tool",
            {
                "action": "update",
                "organization_id": str(ORG_A),
                "user_id": str(USER_A),
                "max_trades_per_day": 3,
                "confirm": True,
            },
        )
        assert allowed.success is True


def test_no_real_trading_path_added(risk_client: TestClient) -> None:
    headers = _auth_headers(risk_client)
    summary = risk_client.get("/dashboard/summary", headers=headers).json()
    assert summary["safety"]["real_trading_enabled"] is False
    assert summary["safety"]["paper_only"] is True

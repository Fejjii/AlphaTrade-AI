"""Slice 44 — dashboard summary and daily discipline snapshot."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.db.base import Base
from app.db.models import (
    DailyRiskState,
    LessonCandidate,
    Membership,
    Organization,
    PaperTrade,
    PaperValidationAlert,
    PaperValidationRun,
    User,
    UserStrategy,
    UserStrategyVersion,
)
from app.db.session import get_session
from app.main import create_app
from app.schemas.common import (
    BacktestStatus,
    LessonCandidateStatus,
    LessonSeverity,
    LessonSourceType,
    MembershipRole,
    PaperAlertSeverity,
    PaperAlertType,
    PaperTradeStatus,
    PaperValidationStatus,
    StrategyId,
    StrategyValidationStatus,
    TradeDirection,
)
from app.schemas.dashboard import (
    AlertsLessonsSummary,
    DailyDisciplineSnapshot,
    StrategyReadinessCounts,
    StrategyReadinessSummary,
)
from app.security.passwords import hash_password
from app.services.dashboard.daily_discipline import build_daily_discipline_snapshot
from app.services.dashboard.next_action import resolve_next_recommended_action
from app.services.dashboard_summary_service import DashboardSummaryService

ORG_A = uuid.UUID("00000000-0000-0000-0000-000000000050")
USER_A = uuid.UUID("00000000-0000-0000-0000-000000000051")
ORG_B = uuid.UUID("00000000-0000-0000-0000-000000000052")
USER_B = uuid.UUID("00000000-0000-0000-0000-000000000053")
STRATEGY_A = uuid.UUID("00000000-0000-0000-0000-000000000054")
RUN_A = uuid.UUID("00000000-0000-0000-0000-000000000055")
VERSION_A = uuid.UUID("00000000-0000-0000-0000-000000000056")


@pytest.fixture
def dashboard_db() -> Iterator[tuple[sessionmaker[Session], Settings]]:
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
        jwt_secret="dashboard-slice44-test-secret",
        rate_limit_use_redis=False,
        access_token_denylist_use_redis=False,
        provider_mode="mock",
        market_data_provider="mock",
    )
    with factory() as session:
        for org_id, user_id, email in (
            (ORG_A, USER_A, "dashboard-a@test.example"),
            (ORG_B, USER_B, "dashboard-b@test.example"),
        ):
            session.add(Organization(id=org_id, name=f"Org {org_id}"))
            session.add(
                User(
                    id=user_id,
                    email=email,
                    hashed_password=hash_password("TestPassword123!", settings),
                    timezone="UTC",
                )
            )
            session.flush()
            session.add(
                Membership(user_id=user_id, organization_id=org_id, role=MembershipRole.OWNER)
            )
        session.commit()
    yield factory, settings
    engine.dispose()


@pytest.fixture
def dashboard_client(dashboard_db: tuple[sessionmaker[Session], Settings]) -> TestClient:
    factory, settings = dashboard_db
    app = create_app(settings)

    def _override_session() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = _override_session
    return TestClient(app)


def _auth_headers(client: TestClient, email: str) -> dict[str, str]:
    login = client.post(
        "/auth/login",
        json={"email": email, "password": "TestPassword123!"},
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
            name="Dashboard Strategy",
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
                "strategy_name": "Dashboard Strategy",
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


def _seed_closed_trade(session: Session, *, net_pnl: Decimal, exit_time: datetime) -> None:
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
            entry_time=exit_time,
            size=Decimal("0.01"),
            status=PaperTradeStatus.CLOSED,
            exit_price=Decimal("61000"),
            exit_time=exit_time,
            net_pnl=net_pnl,
            gross_pnl=net_pnl,
        )
    )


def test_dashboard_summary_requires_auth(dashboard_client: TestClient) -> None:
    resp = dashboard_client.get("/dashboard/summary")
    assert resp.status_code == 401


def test_dashboard_summary_tenant_scoped(
    dashboard_db: tuple[sessionmaker[Session], Settings],
    dashboard_client: TestClient,
) -> None:
    factory, _ = dashboard_db
    with factory() as session:
        session.add(
            PaperValidationAlert(
                organization_id=ORG_A,
                user_id=USER_A,
                alert_type=PaperAlertType.SETUP_SIGNAL_DETECTED,
                severity=PaperAlertSeverity.WARNING,
                message="Org A alert",
            )
        )
        session.add(
            PaperValidationAlert(
                organization_id=ORG_B,
                user_id=USER_B,
                alert_type=PaperAlertType.SETUP_SIGNAL_DETECTED,
                severity=PaperAlertSeverity.CRITICAL,
                message="Org B alert",
            )
        )
        session.commit()

    headers_a = _auth_headers(dashboard_client, "dashboard-a@test.example")
    headers_b = _auth_headers(dashboard_client, "dashboard-b@test.example")
    body_a = dashboard_client.get("/dashboard/summary", headers=headers_a).json()
    body_b = dashboard_client.get("/dashboard/summary", headers=headers_b).json()

    assert body_a["safety"]["real_trading_enabled"] is False
    assert body_b["safety"]["real_trading_enabled"] is False
    assert body_a["alerts_lessons"]["unread_alerts"] == 1
    assert body_b["alerts_lessons"]["unread_alerts"] == 1
    assert body_a["alerts_lessons"]["latest_high_priority"][0]["message"] == "Org A alert"
    assert body_b["alerts_lessons"]["latest_high_priority"][0]["message"] == "Org B alert"


def test_summary_returns_paper_safety_status(dashboard_client: TestClient) -> None:
    headers = _auth_headers(dashboard_client, "dashboard-a@test.example")
    body = dashboard_client.get("/dashboard/summary", headers=headers).json()
    assert body["safety"]["execution_mode"] == "paper"
    assert body["safety"]["paper_only"] is True
    assert body["safety"]["real_trading_disabled"] is True


def test_daily_snapshot_counts_trades_today(
    dashboard_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, _ = dashboard_db
    now = datetime.now(UTC)
    with factory() as session:
        _seed_closed_trade(session, net_pnl=Decimal("10"), exit_time=now)
        session.commit()
        snapshot = build_daily_discipline_snapshot(session, organization_id=ORG_A, user_id=USER_A)
    assert snapshot.trades_today == 1
    assert snapshot.paper_trades_opened_today == 1
    assert snapshot.paper_trades_closed_today == 1


def test_daily_pnl_uses_closed_paper_trades(
    dashboard_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, _ = dashboard_db
    now = datetime.now(UTC)
    with factory() as session:
        _seed_closed_trade(session, net_pnl=Decimal("-75"), exit_time=now)
        session.commit()
        snapshot = build_daily_discipline_snapshot(session, organization_id=ORG_A, user_id=USER_A)
    assert snapshot.realized_pnl_today_paper == Decimal("-75")
    assert snapshot.net_pnl_today_paper == Decimal("-75")


def test_loss_lock_at_configured_limit(
    dashboard_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, _ = dashboard_db
    today = datetime.now(UTC).date()
    now = datetime.now(UTC)
    with factory() as session:
        session.add(
            DailyRiskState(
                organization_id=ORG_A,
                user_id=USER_A,
                day=today,
                daily_loss_limit=Decimal("50"),
                realized_pnl=Decimal("-60"),
            )
        )
        _seed_closed_trade(session, net_pnl=Decimal("-60"), exit_time=now)
        session.commit()
        snapshot = build_daily_discipline_snapshot(session, organization_id=ORG_A, user_id=USER_A)
    assert snapshot.loss_lock_active is True
    assert snapshot.discipline_status == "locked"


def test_green_day_at_configured_target(
    dashboard_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, _ = dashboard_db
    today = datetime.now(UTC).date()
    now = datetime.now(UTC)
    with factory() as session:
        session.add(
            DailyRiskState(
                organization_id=ORG_A,
                user_id=USER_A,
                day=today,
                daily_loss_limit=Decimal("100"),
                daily_target=Decimal("40"),
            )
        )
        _seed_closed_trade(session, net_pnl=Decimal("45"), exit_time=now)
        session.commit()
        snapshot = build_daily_discipline_snapshot(session, organization_id=ORG_A, user_id=USER_A)
    assert snapshot.green_day_protection_active is True


def test_overtrading_warning_at_threshold(
    dashboard_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, _ = dashboard_db
    today = datetime.now(UTC).date()
    now = datetime.now(UTC)
    with factory() as session:
        _seed_strategy_stack(session)
        session.add(
            DailyRiskState(
                organization_id=ORG_A,
                user_id=USER_A,
                day=today,
                daily_loss_limit=Decimal("100"),
                max_trades_per_day=2,
            )
        )
        for _ in range(2):
            session.add(
                PaperTrade(
                    paper_validation_run_id=RUN_A,
                    strategy_id=STRATEGY_A,
                    organization_id=ORG_A,
                    user_id=USER_A,
                    symbol="BTCUSDT",
                    exchange="binance",
                    timeframe="15m",
                    direction=TradeDirection.LONG,
                    entry_time=now,
                    status=PaperTradeStatus.OPEN,
                )
            )
        session.commit()
        snapshot = build_daily_discipline_snapshot(session, organization_id=ORG_A, user_id=USER_A)
    assert snapshot.overtrading_warning_active is True
    assert snapshot.remaining_trades_allowed == 0


def test_missing_settings_produce_limitations(
    dashboard_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, _ = dashboard_db
    with factory() as session:
        snapshot = build_daily_discipline_snapshot(session, organization_id=ORG_A, user_id=USER_A)
    assert snapshot.daily_loss_limit is None
    assert snapshot.daily_target is None
    assert any("not configured" in item.lower() for item in snapshot.limitations)


def test_strategy_readiness_counts(dashboard_db: tuple[sessionmaker[Session], Settings]) -> None:
    factory, settings = dashboard_db
    with factory() as session:
        service = DashboardSummaryService(session, settings)
        _seed_strategy_stack(session)
        session.commit()
        summary = service.summarize(organization_id=ORG_A, user_id=USER_A)
    counts = summary.strategy_readiness.counts
    assert counts.paper_validation_running >= 1
    assert len(summary.active_paper_validations) >= 1


def test_unread_alerts_and_pending_lessons_in_summary(
    dashboard_db: tuple[sessionmaker[Session], Settings],
    dashboard_client: TestClient,
) -> None:
    factory, _ = dashboard_db
    with factory() as session:
        session.add(
            PaperValidationAlert(
                organization_id=ORG_A,
                user_id=USER_A,
                alert_type=PaperAlertType.OVERTRADING_WARNING,
                severity=PaperAlertSeverity.WARNING,
                message="Slow down",
            )
        )
        session.add(
            LessonCandidate(
                organization_id=ORG_A,
                user_id=USER_A,
                source_type=LessonSourceType.JOURNAL,
                lesson_text="Wait for confirmation.",
                mistake_type="early_entry",
                severity=LessonSeverity.HIGH,
                status=LessonCandidateStatus.PENDING_REVIEW,
            )
        )
        session.commit()

    headers = _auth_headers(dashboard_client, "dashboard-a@test.example")
    body = dashboard_client.get("/dashboard/summary", headers=headers).json()
    assert body["alerts_lessons"]["unread_alerts"] == 1
    assert body["alerts_lessons"]["pending_lessons"] == 1


def test_next_action_priority_order() -> None:
    loss_lock = DailyDisciplineSnapshot(
        date=datetime.now(UTC).date(),
        timezone="UTC",
        loss_lock_active=True,
    )
    action = resolve_next_recommended_action(
        real_trading_enabled=False,
        daily=loss_lock,
        alerts_lessons=AlertsLessonsSummary(unread_alerts=5, pending_lessons=3),
        strategy_readiness=StrategyReadinessSummary(
            counts=StrategyReadinessCounts(needs_structure=2)
        ),
        market_watcher=None,
        bridge=None,
    )
    assert action.priority == 2
    assert "loss" in action.action.lower()

    green_day = DailyDisciplineSnapshot(
        date=datetime.now(UTC).date(),
        timezone="UTC",
        green_day_protection_active=True,
    )
    action_green = resolve_next_recommended_action(
        real_trading_enabled=False,
        daily=green_day,
        alerts_lessons=None,
        strategy_readiness=None,
        market_watcher=None,
        bridge=None,
    )
    assert action_green.priority == 3


def test_no_real_trading_path_added(dashboard_client: TestClient) -> None:
    headers = _auth_headers(dashboard_client, "dashboard-a@test.example")
    summary = dashboard_client.get("/dashboard/summary", headers=headers)
    health = dashboard_client.get("/health")
    assert summary.status_code == 200
    assert health.json()["real_trading_enabled"] is False
    assert summary.json()["safety"]["real_trading_enabled"] is False

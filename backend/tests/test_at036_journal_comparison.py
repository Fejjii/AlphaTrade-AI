"""AT-036 — human-vs-system journal comparison (decision quality + cohort scorecards)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.db.base import Base
from app.db.models import (
    JournalTrade,
    Membership,
    Organization,
    SetupDefinition,
    User,
)
from app.db.session import get_session
from app.main import create_app
from app.schemas.common import (
    JournalEntryMethod,
    JournalTradeSource,
    JournalTradeStatus,
    MarketRegime,
    MembershipRole,
    StrategyId,
    TradeDirection,
    TradeResult,
)
from app.security.passwords import hash_password
from app.security.rate_limit import reset_rate_limiter

ORG_A = uuid.UUID("00000000-0000-0000-0000-000000003601")
ORG_B = uuid.UUID("00000000-0000-0000-0000-000000003602")
USER_A = uuid.UUID("00000000-0000-0000-0000-000000003611")
USER_B = uuid.UUID("00000000-0000-0000-0000-000000003612")
VIEWER_A = uuid.UUID("00000000-0000-0000-0000-000000003613")

_BASE = {
    "environment": "local",
    "log_json": False,
    "execution_mode": "paper",
    "enable_real_trading": False,
    "database_url": "sqlite+pysqlite:///:memory:",
    "jwt_secret": "at036-comparison-test-secret-32ch!",
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


def _build_env(
    settings_overrides: dict[str, object] | None = None,
) -> tuple[TestClient, sessionmaker[Session]]:
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
    settings = Settings(**{**_BASE, **(settings_overrides or {})})  # type: ignore[arg-type]

    with factory() as session:
        session.add(Organization(id=ORG_A, name="AT036 Org A"))
        session.add(Organization(id=ORG_B, name="AT036 Org B"))
        for user_id, email in (
            (USER_A, "at036-a@test.example"),
            (USER_B, "at036-b@test.example"),
            (VIEWER_A, "at036-viewer@test.example"),
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
    return TestClient(app), factory


@pytest.fixture
def client() -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    test_client, factory = _build_env()
    with test_client:
        yield test_client, factory


def _auth(client: TestClient, email: str, password: str = "SecurePass123!") -> dict[str, str]:
    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    token = login.json()["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _closed_trade(
    factory: sessionmaker[Session],
    *,
    organization_id: uuid.UUID = ORG_A,
    user_id: uuid.UUID = USER_A,
    symbol: str = "BTCUSDT",
    timeframe: str = "1h",
    source: JournalTradeSource = JournalTradeSource.MANUAL,
    entry_method: JournalEntryMethod = JournalEntryMethod.MANUAL,
    status: JournalTradeStatus = JournalTradeStatus.CLOSED,
    market_regime: MarketRegime = MarketRegime.TRENDING_UP,
    direction: TradeDirection = TradeDirection.LONG,
    result: TradeResult = TradeResult.OPEN,
    net_pnl: str | None = None,
    available_profit: str | None = None,
    realized_vs_available_pct: float | None = None,
    planned_entry_price: str | None = None,
    entry_price: str | None = None,
    setup_id: uuid.UUID | None = None,
    exit_time: datetime | None = datetime(2026, 7, 10, 12, 0, tzinfo=UTC),
) -> uuid.UUID:
    def _dec(value: str | None) -> Decimal | None:
        return Decimal(value) if value is not None else None

    with factory() as session:
        row = JournalTrade(
            organization_id=organization_id,
            user_id=user_id,
            source=source,
            entry_method=entry_method,
            status=status,
            symbol=symbol,
            timeframe=timeframe,
            market_regime=market_regime,
            direction=direction,
            result=result,
            net_pnl=_dec(net_pnl),
            available_profit=_dec(available_profit),
            realized_vs_available_pct=realized_vs_available_pct,
            planned_entry_price=_dec(planned_entry_price),
            entry_price=_dec(entry_price),
            entry_time=datetime(2026, 7, 10, 8, 0, tzinfo=UTC),
            exit_time=exit_time,
            setup_id=setup_id,
            tags=[],
            planned_targets=[],
        )
        session.add(row)
        session.commit()
        return row.id


def _comparison(
    client: TestClient,
    headers: dict[str, str],
    **params: object,
) -> dict[str, Any]:
    response = client.get("/journal/comparison", headers=headers, params=params)  # type: ignore[arg-type]
    assert response.status_code == 200, response.text
    payload: dict[str, Any] = response.json()
    return payload


def _add_rule_check(
    client: TestClient,
    headers: dict[str, str],
    trade_id: uuid.UUID,
    status: str,
    rule_key: str = "respect-stop",
) -> None:
    response = client.post(
        f"/journal/trades/{trade_id}/rule-checks",
        headers=headers,
        json={"rule_key": rule_key, "status": status},
    )
    assert response.status_code == 201, response.text


def _seed_setup(factory: sessionmaker[Session], *, name: str) -> uuid.UUID:
    with factory() as session:
        setup = SetupDefinition(
            name=name,
            strategy_id=StrategyId.HTF_TREND_PULLBACK,
            category="trend",
            version=1,
        )
        session.add(setup)
        session.commit()
        return setup.id


# --------------------------------------------------------------------------- #
# Auth & RBAC
# --------------------------------------------------------------------------- #


def test_comparison_requires_auth(client: tuple[TestClient, sessionmaker[Session]]) -> None:
    test_client, _ = client
    assert test_client.get("/journal/comparison").status_code == 401


def test_viewer_can_read_comparison(client: tuple[TestClient, sessionmaker[Session]]) -> None:
    test_client, _ = client
    headers = _auth(test_client, "at036-viewer@test.example")
    body = _comparison(test_client, headers)
    assert len(body["cohorts"]) == 3


# --------------------------------------------------------------------------- #
# Empty & AT-034 backward compatibility
# --------------------------------------------------------------------------- #


def test_empty_comparison_is_explicit(client: tuple[TestClient, sessionmaker[Session]]) -> None:
    test_client, _ = client
    headers = _auth(test_client, "at036-a@test.example")
    body = _comparison(test_client, headers)

    cohort_keys = {c["cohort"] for c in body["cohorts"]}
    assert cohort_keys == {"human", "paper_system", "backtest"}
    assert all(c["sample_count"] == 0 for c in body["cohorts"])

    scorecard_actors = {s["actor"] for s in body["scorecards"]}
    assert scorecard_actors == {"human", "system"}
    assert all(s["sample_count"] == 0 for s in body["scorecards"])

    dq = body["decision_quality"]
    assert dq["timing_sample_count"] == 0
    assert dq["average_entry_timing_pct"] is None
    assert "no_closed_trades" in [w["code"] for w in dq["warnings"]]
    assert body["confidence"] == "insufficient"
    assert "AT-036" in body["note"]


def test_invalid_date_range_rejected(client: tuple[TestClient, sessionmaker[Session]]) -> None:
    test_client, _ = client
    headers = _auth(test_client, "at036-a@test.example")
    response = test_client.get(
        "/journal/comparison",
        headers=headers,
        params={"date_from": "2026-07-20T00:00:00Z", "date_to": "2026-07-01T00:00:00Z"},
    )
    assert response.status_code == 422


# --------------------------------------------------------------------------- #
# Decision-quality metric correctness
# --------------------------------------------------------------------------- #


def test_entry_timing_long_and_short(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "at036-a@test.example")
    # Long: (105-100)/100*100 = 5%
    _closed_trade(
        factory,
        direction=TradeDirection.LONG,
        planned_entry_price="100",
        entry_price="105",
        result=TradeResult.WIN,
        net_pnl="50",
    )
    # Short: (100-95)/100*100 = 5%
    _closed_trade(
        factory,
        direction=TradeDirection.SHORT,
        planned_entry_price="100",
        entry_price="95",
        result=TradeResult.WIN,
        net_pnl="50",
    )

    dq = _comparison(test_client, headers)["decision_quality"]
    assert dq["timing_sample_count"] == 2
    assert dq["average_entry_timing_pct"] == pytest.approx(5.0)


def test_entry_timing_skips_missing_or_zero_planned(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "at036-a@test.example")
    _closed_trade(
        factory,
        planned_entry_price="100",
        entry_price="110",
        result=TradeResult.WIN,
        net_pnl="50",
    )
    _closed_trade(
        factory,
        planned_entry_price=None,
        entry_price="100",
        result=TradeResult.WIN,
        net_pnl="10",
    )
    _closed_trade(
        factory,
        planned_entry_price="0",
        entry_price="100",
        result=TradeResult.WIN,
        net_pnl="10",
    )

    dq = _comparison(test_client, headers)["decision_quality"]
    assert dq["timing_sample_count"] == 1
    assert dq["average_entry_timing_pct"] == pytest.approx(10.0)
    assert "partial_timing_data" in [w["code"] for w in dq["warnings"]]


def test_early_exit_and_capture_metrics(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "at036-a@test.example")
    # 100/500 = 20% capture -> early exit
    _closed_trade(
        factory,
        result=TradeResult.WIN,
        net_pnl="100",
        available_profit="500",
    )
    # 300/500 = 60% capture -> not early exit
    _closed_trade(
        factory,
        result=TradeResult.WIN,
        net_pnl="300",
        available_profit="500",
    )

    dq = _comparison(test_client, headers)["decision_quality"]
    assert dq["early_exit_sample_count"] == 2
    assert dq["early_exit_count"] == 1
    assert dq["early_exit_rate"] == pytest.approx(0.5)
    assert dq["average_capture_pct"] == pytest.approx(40.0)


def test_missed_profit_metrics(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "at036-a@test.example")
    # available 500 - net 100 = 400 missed
    _closed_trade(factory, result=TradeResult.WIN, net_pnl="100", available_profit="500")
    # available <= net -> not in missed sample
    _closed_trade(factory, result=TradeResult.WIN, net_pnl="200", available_profit="200")

    dq = _comparison(test_client, headers)["decision_quality"]
    assert dq["missed_profit_sample_count"] == 1
    assert Decimal(dq["average_missed_profit"]) == Decimal("400")
    assert "partial_missed_profit_data" in [w["code"] for w in dq["warnings"]]


def test_low_sample_warning_on_decision_quality(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "at036-a@test.example")
    for i in range(10):
        _closed_trade(
            factory,
            planned_entry_price="100",
            entry_price="101",
            result=TradeResult.WIN,
            net_pnl="10",
            exit_time=datetime(2026, 7, 10, 12, i, tzinfo=UTC),
        )

    body = _comparison(test_client, headers)
    assert body["confidence"] == "low"
    dq_codes = [w["code"] for w in body["decision_quality"]["warnings"]]
    assert "low_sample" in dq_codes


# --------------------------------------------------------------------------- #
# Cohort / scorecard source mapping & source filter
# --------------------------------------------------------------------------- #


def test_cohort_and_scorecard_source_mapping(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "at036-a@test.example")
    for source in (
        JournalTradeSource.MANUAL,
        JournalTradeSource.IMPORTED,
        JournalTradeSource.PAPER_EXECUTION,
    ):
        _closed_trade(factory, source=source, result=TradeResult.WIN, net_pnl="10")
    _closed_trade(
        factory,
        source=JournalTradeSource.PAPER_VALIDATION,
        result=TradeResult.LOSS,
        net_pnl="-10",
    )
    _closed_trade(
        factory,
        source=JournalTradeSource.BACKTEST,
        result=TradeResult.LOSS,
        net_pnl="-5",
    )
    _closed_trade(
        factory,
        source=JournalTradeSource.SYSTEM,
        result=TradeResult.LOSS,
        net_pnl="-3",
    )

    body = _comparison(test_client, headers)
    cohort_counts = {c["cohort"]: c["sample_count"] for c in body["cohorts"]}
    assert cohort_counts == {"human": 3, "paper_system": 1, "backtest": 1}

    scorecard_counts = {s["actor"]: s["sample_count"] for s in body["scorecards"]}
    assert scorecard_counts == {"human": 3, "system": 3}

    source_counts = {b["key"]: b["sample_count"] for b in body["by_source"]}
    assert source_counts["manual"] == 1
    assert source_counts["system"] == 1


def test_source_filter_intersects_all_dimensions(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "at036-a@test.example")
    _closed_trade(factory, source=JournalTradeSource.MANUAL, result=TradeResult.WIN, net_pnl="100")
    _closed_trade(
        factory,
        source=JournalTradeSource.BACKTEST,
        result=TradeResult.LOSS,
        net_pnl="-50",
    )

    body = _comparison(test_client, headers, source="manual")
    assert body["filters"]["source"] == "manual"
    cohort_counts = {c["cohort"]: c["sample_count"] for c in body["cohorts"]}
    assert cohort_counts == {"human": 1, "paper_system": 0, "backtest": 0}
    assert body["decision_quality"]["timing_sample_count"] == 0
    assert len(body["by_source"]) == 1
    assert body["by_source"][0]["key"] == "manual"


# --------------------------------------------------------------------------- #
# Rule compliance buckets
# --------------------------------------------------------------------------- #


def test_rule_compliance_worst_assessment_buckets(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "at036-a@test.example")
    compliant = _closed_trade(factory, result=TradeResult.WIN, net_pnl="100")
    violated = _closed_trade(factory, result=TradeResult.LOSS, net_pnl="-80")
    partial = _closed_trade(factory, result=TradeResult.WIN, net_pnl="40")
    _closed_trade(factory, result=TradeResult.WIN, net_pnl="10")  # unassessed

    _add_rule_check(test_client, headers, compliant, "followed")
    _add_rule_check(test_client, headers, violated, "followed", rule_key="wait-for-close")
    _add_rule_check(test_client, headers, violated, "violated")
    _add_rule_check(test_client, headers, partial, "partial")

    counts = {
        b["key"]: b["sample_count"] for b in _comparison(test_client, headers)["rule_compliance"]
    }
    assert counts == {"compliant": 1, "violated": 1, "partial": 1, "unassessed": 1}


# --------------------------------------------------------------------------- #
# Breakdown limit + sort
# --------------------------------------------------------------------------- #


def test_breakdown_limit_and_sort(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "at036-a@test.example")
    setup_a = _seed_setup(factory, name="Alpha setup")
    setup_b = _seed_setup(factory, name="Beta setup")
    setup_c = _seed_setup(factory, name="Gamma setup")

    for _ in range(3):
        _closed_trade(factory, setup_id=setup_a, result=TradeResult.WIN, net_pnl="10")
    for _ in range(2):
        _closed_trade(factory, setup_id=setup_b, result=TradeResult.WIN, net_pnl="10")
    _closed_trade(factory, setup_id=setup_c, result=TradeResult.WIN, net_pnl="10")

    body = _comparison(test_client, headers, breakdown_limit=2)
    setup_breakdown = next(b for b in body["breakdowns"] if b["dimension"] == "setup")
    assert len(setup_breakdown["buckets"]) == 2
    assert setup_breakdown["buckets"][0]["label"] == "Alpha setup v1"
    assert setup_breakdown["buckets"][0]["sample_count"] == 3
    assert setup_breakdown["buckets"][1]["sample_count"] == 2


def test_entry_method_buckets_only_present_keys(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "at036-a@test.example")
    _closed_trade(
        factory,
        entry_method=JournalEntryMethod.MANUAL,
        result=TradeResult.WIN,
        net_pnl="10",
    )
    _closed_trade(
        factory,
        entry_method=JournalEntryMethod.IMPORT,
        result=TradeResult.WIN,
        net_pnl="20",
    )

    keys = {b["key"] for b in _comparison(test_client, headers)["by_entry_method"]}
    assert keys == {"manual", "import"}


# --------------------------------------------------------------------------- #
# Links & filters echo
# --------------------------------------------------------------------------- #


def test_comparison_links_echo_filters(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, _ = client
    headers = _auth(test_client, "at036-a@test.example")
    body = _comparison(test_client, headers, symbol="ETHUSDT", market_regime="ranging")
    links = body["links"]
    assert links["journal_trades_path"] == "/journal"
    assert "symbol=ETHUSDT" in links["journal_comparison_path"]
    assert "market_regime=ranging" in links["journal_comparison_path"]
    assert "symbol=ETHUSDT" in links["journal_statistics_path"]
    assert links["research_validation_path"] == "/research-validation"
    assert links["paper_validation_candidates_path"] == "/paper-validation/candidates"


# --------------------------------------------------------------------------- #
# Tenant isolation
# --------------------------------------------------------------------------- #


def test_tenant_isolation(client: tuple[TestClient, sessionmaker[Session]]) -> None:
    test_client, factory = client
    headers_a = _auth(test_client, "at036-a@test.example")
    headers_b = _auth(test_client, "at036-b@test.example")
    _closed_trade(factory, result=TradeResult.WIN, net_pnl="100")
    _closed_trade(
        factory,
        organization_id=ORG_B,
        user_id=USER_B,
        result=TradeResult.LOSS,
        net_pnl="-999",
    )

    body_a = _comparison(test_client, headers_a)
    human_a = next(c for c in body_a["cohorts"] if c["cohort"] == "human")
    assert human_a["sample_count"] == 1
    assert Decimal(human_a["metrics"]["net_pnl_total"]) == Decimal("100")

    body_b = _comparison(test_client, headers_b)
    human_b = next(c for c in body_b["cohorts"] if c["cohort"] == "human")
    assert human_b["sample_count"] == 1
    assert Decimal(human_b["metrics"]["net_pnl_total"]) == Decimal("-999")

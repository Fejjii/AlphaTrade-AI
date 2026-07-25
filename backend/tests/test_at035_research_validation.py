"""AT-035 — research validation loop (advisory backtest → paper candidate promotion)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.db.base import Base
from app.db.models import (
    BacktestDataset,
    BacktestRun,
    JournalTrade,
    Membership,
    Organization,
    PaperValidationAlert,
    PaperValidationCandidate,
    PaperValidationDraft,
    User,
    UserStrategy,
    UserStrategyVersion,
)
from app.db.session import get_session
from app.main import create_app
from app.schemas.common import (
    JournalTradeSource,
    MembershipRole,
    PaperAlertSource,
    PaperAlertType,
    SetupAlertReviewStatus,
    StrategyId,
    TradeDirection,
)
from app.schemas.paper_validation_candidate import QUEUE_PAPER_VALIDATION_CANDIDATE_CONFIRM
from app.schemas.paper_validation_draft import CREATE_PAPER_VALIDATION_DRAFT_CONFIRM
from app.schemas.research_validation import PROMOTE_RESEARCH_VALIDATION_CANDIDATE_CONFIRM
from app.services.paper_alert_service import PaperAlertService

ORG_A = uuid.UUID("00000000-0000-0000-0000-000000035101")
ORG_B = uuid.UUID("00000000-0000-0000-0000-000000035102")
USER_A = uuid.UUID("00000000-0000-0000-0000-000000035111")
USER_B = uuid.UUID("00000000-0000-0000-0000-000000035112")
VIEWER_A = uuid.UUID("00000000-0000-0000-0000-000000035113")
TRADER_A = uuid.UUID("00000000-0000-0000-0000-000000035114")

_BASE: dict[str, Any] = {
    "environment": "local",
    "log_json": False,
    "execution_mode": "paper",
    "enable_real_trading": False,
    "database_url": "sqlite+pysqlite:///:memory:",
    "jwt_secret": "at035-research-validation-secret-32",
    "rate_limit_use_redis": False,
    "access_token_denylist_use_redis": False,
    "provider_mode": "mock",
    "market_data_provider": "mock",
    "alert_delivery_enabled": False,
    "telegram_alerts_enabled": False,
    "worker_enabled": False,
    "market_watcher_enabled": False,
}

_CARD: dict[str, Any] = {
    "strategy_name": "AT035 Research",
    "market_type": "crypto_perp",
    "asset_universe": ["BTCUSDT"],
    "timeframes": ["4h"],
    "entry_conditions": ["Pullback"],
    "confirmation_conditions": ["RSI reset"],
    "invalidation": ["Close below swing"],
    "stop_loss": ["2% below entry"],
    "take_profit_plan": ["TP1 at 1R"],
    "runner_plan": [],
    "position_sizing": ["Max 1%"],
    "add_rules": [],
    "no_trade_rules": [],
    "backtest_rules": [],
    "success_criteria": ["Win rate > 45%"],
    "validation_status": "draft",
}


@pytest.fixture(autouse=True)
def _reset_limiter() -> None:
    from app.security.rate_limit import reset_rate_limiter

    reset_rate_limiter()


@pytest.fixture
def client() -> Iterator[tuple[TestClient, sessionmaker[Session], Settings]]:
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
        session.add(Organization(id=ORG_A, name="AT035 Org A"))
        session.add(Organization(id=ORG_B, name="AT035 Org B"))
        for user_id, email in (
            (USER_A, "at035-a@test.example"),
            (USER_B, "at035-b@test.example"),
            (VIEWER_A, "at035-viewer@test.example"),
            (TRADER_A, "at035-trader@test.example"),
        ):
            session.add(
                User(
                    id=user_id,
                    email=email,
                    hashed_password=__import__(
                        "app.security.passwords", fromlist=["hash_password"]
                    ).hash_password("SecurePass123!", settings),
                    email_verified=True,
                )
            )
        session.flush()
        session.add(Membership(user_id=USER_A, organization_id=ORG_A, role=MembershipRole.OWNER))
        session.add(Membership(user_id=USER_B, organization_id=ORG_B, role=MembershipRole.OWNER))
        session.add(Membership(user_id=VIEWER_A, organization_id=ORG_A, role=MembershipRole.VIEWER))
        session.add(Membership(user_id=TRADER_A, organization_id=ORG_A, role=MembershipRole.TRADER))
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


def _auth(client: TestClient, email: str) -> dict[str, str]:
    login = client.post("/auth/login", json={"email": email, "password": "SecurePass123!"})
    assert login.status_code == 200, login.text
    token = login.json()["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _tier2_result(*, trade_count: int = 40, oos_trade_count: int = 20) -> dict[str, Any]:
    return {
        "metrics": {
            "trade_count": trade_count,
            "win_rate": 0.5,
            "profit_factor": 1.2,
            "expectancy": "5",
            "max_drawdown_pct": 5,
            "average_win": "20",
            "average_loss": "-10",
            "largest_win": "30",
            "largest_loss": "-15",
            "consecutive_losses": 2,
            "average_time_in_trade_bars": 3,
            "total_fees": "1",
            "total_slippage": "1",
            "net_pnl": "50",
            "return_pct": 0.5,
            "ending_equity": "10050",
            "symbol": "BTCUSDT",
            "timeframe": "4h",
        },
        "recommendation": "promising",
        "oos_metrics": {
            "split_label": "out_of_sample",
            "split_index": 0,
            "start_time": "2024-01-01T00:00:00Z",
            "end_time": "2024-02-01T00:00:00Z",
            "trade_count": oos_trade_count,
            "win_rate": 0.5,
            "profit_factor": 1.2,
            "expectancy": "5",
            "net_pnl": "40",
            "max_drawdown_pct": 4,
        },
    }


def _tier3_result() -> dict[str, Any]:
    return {
        "metrics": {
            "trade_count": 5,
            "win_rate": 0.4,
            "profit_factor": 0.8,
            "expectancy": "-2",
            "max_drawdown_pct": 10,
            "average_win": "10",
            "average_loss": "-12",
            "largest_win": "15",
            "largest_loss": "-20",
            "consecutive_losses": 3,
            "average_time_in_trade_bars": 2,
            "total_fees": "1",
            "total_slippage": "1",
            "net_pnl": "-10",
            "return_pct": -0.1,
            "ending_equity": "9990",
            "symbol": "BTCUSDT",
            "timeframe": "4h",
        },
        "recommendation": "weak",
        "oos_metrics": {
            "split_label": "out_of_sample",
            "split_index": 0,
            "start_time": "2024-01-01T00:00:00Z",
            "end_time": "2024-02-01T00:00:00Z",
            "trade_count": 3,
            "win_rate": 0.33,
            "profit_factor": 0.7,
            "expectancy": "-3",
            "net_pnl": "-8",
            "max_drawdown_pct": 8,
        },
    }


def _seed_dataset(session: Session) -> BacktestDataset:
    dataset = BacktestDataset(
        symbol="BTCUSDT",
        exchange="binance",
        timeframe="4h",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 2, 1),
        candle_count=120,
        dataset_hash="a" * 64,
        source_counts={"synthetic": 120},
    )
    session.add(dataset)
    session.flush()
    return dataset


def _seed_strategy(
    session: Session,
    *,
    organization_id: uuid.UUID = ORG_A,
    user_id: uuid.UUID = USER_A,
    name: str = "Research Strat",
) -> tuple[UserStrategy, UserStrategyVersion]:
    strategy = UserStrategy(
        organization_id=organization_id,
        user_id=user_id,
        name=name,
        setup_type=StrategyId.HTF_TREND_PULLBACK,
    )
    session.add(strategy)
    session.flush()
    version = UserStrategyVersion(
        strategy_id=strategy.id,
        version=1,
        card=_CARD,
        structured_rules={"entry_rules": [], "exit_rules": []},
    )
    session.add(version)
    session.flush()
    return strategy, version


def _seed_completed_run(
    session: Session,
    strategy: UserStrategy,
    version: UserStrategyVersion,
    result: dict[str, Any],
    *,
    organization_id: uuid.UUID = ORG_A,
    user_id: uuid.UUID = USER_A,
    status: str = "completed",
    strategy_version_id: uuid.UUID | None = None,
    include_oos: bool = True,
) -> BacktestRun:
    dataset = _seed_dataset(session)
    if not include_oos:
        result = dict(result)
        result.pop("oos_metrics", None)

    run = BacktestRun(
        strategy_id=strategy.id,
        strategy_version_id=strategy_version_id if strategy_version_id is not None else version.id,
        organization_id=organization_id,
        user_id=user_id,
        status=status,
        assumptions={"symbol": "BTCUSDT", "timeframe": "4h", "regime": "trending"},
        config_snapshot={"dataset_hash": dataset.dataset_hash, "regime": "trending"},
        config_hash="b" * 64,
        dataset_id=dataset.id,
        engine_version="at034-2.0.0",
        result_hash="c" * 64,
        result=result,
        finished_at=datetime.now(UTC),
    )
    session.add(run)
    session.flush()
    return run


def _seed_confirm_trades(
    session: Session,
    strategy: UserStrategy,
    version: UserStrategyVersion,
    *,
    count: int,
    organization_id: uuid.UUID = ORG_A,
    user_id: uuid.UUID = USER_A,
) -> None:
    for i in range(count):
        session.add(
            JournalTrade(
                organization_id=organization_id,
                user_id=user_id,
                source=JournalTradeSource.MANUAL,
                status="closed",
                symbol="BTCUSDT",
                timeframe="4h",
                direction=TradeDirection.LONG,
                user_strategy_id=strategy.id,
                strategy_version_id=version.id,
                net_pnl=Decimal("10"),
                result="win",
                entry_time=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=i),
                exit_time=datetime(2024, 1, 1, 4, tzinfo=UTC) + timedelta(days=i),
            )
        )
    session.flush()


_READY_PREP = {
    "prep_status": "ready_for_validation",
    "thesis": "Ready thesis for queue.",
    "entry_criteria": "Entry rules for queue.",
    "invalidation_criteria": "Invalidation rules for queue.",
    "risk_notes": "Conservative queue prep.",
    "checklist": {
        "trend_checked": True,
        "support_resistance_checked": True,
        "volume_checked": True,
        "risk_reward_checked": True,
        "invalidation_checked": True,
        "higher_timeframe_checked": True,
        "news_or_funding_checked": True,
    },
}


def _promote_payload(backtest_run_id: uuid.UUID, *, confirm: str | None = None) -> dict[str, str]:
    return {
        "confirm": confirm or PROMOTE_RESEARCH_VALIDATION_CANDIDATE_CONFIRM,
        "backtest_run_id": str(backtest_run_id),
    }


def _seed_eligible_run(
    factory: sessionmaker[Session],
    *,
    organization_id: uuid.UUID = ORG_A,
    user_id: uuid.UUID = USER_A,
    confirm_trades: int = 5,
) -> BacktestRun:
    with factory() as session:
        strategy, version = _seed_strategy(
            session, organization_id=organization_id, user_id=user_id
        )
        _seed_confirm_trades(
            session,
            strategy,
            version,
            count=confirm_trades,
            organization_id=organization_id,
            user_id=user_id,
        )
        run = _seed_completed_run(
            session,
            strategy,
            version,
            _tier2_result(),
            organization_id=organization_id,
            user_id=user_id,
        )
        session.commit()
        return run


# --------------------------------------------------------------------------- #
# Happy path + idempotency
# --------------------------------------------------------------------------- #


def test_promote_happy_path_creates_alert_draft_candidate_with_provenance(
    client: tuple[TestClient, sessionmaker[Session], Settings],
) -> None:
    test_client, factory, _ = client
    headers = _auth(test_client, "at035-a@test.example")
    run = _seed_eligible_run(factory, confirm_trades=5)

    response = test_client.post(
        "/research-validation/promote",
        headers=headers,
        json=_promote_payload(run.id),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["already_exists"] is False
    assert body["eligibility"]["eligible"] is True
    assert body["eligibility"]["tier"] == "tier2"

    candidate = body["candidate"]
    assert candidate["promotion_source"] == "research_validation"
    assert candidate["backtest_run_id"] == str(run.id)
    assert candidate["strategy_id"] == str(run.strategy_id)
    assert candidate["strategy_version_id"] == str(run.strategy_version_id)
    assert candidate["dataset_hash"] == "a" * 64
    assert candidate["config_hash"] == "b" * 64
    assert candidate["result_hash"] == "c" * 64
    assert candidate["evidence_tier"] == "tier2"
    assert candidate["sample_size"] == 20
    assert candidate["regime"] == "trending"
    assert candidate["evidence_snapshot"] is not None
    assert candidate["evidence_snapshot"]["tier"] == "tier2"
    assert candidate["candidate_status"] == "queued"

    links = body["links"]
    assert links["candidate_id"] == candidate["candidate_id"]
    assert links["draft_id"] == candidate["draft_id"]
    assert links["source_alert_id"] == candidate["source_alert_id"]
    assert links["backtest_run_id"] == str(run.id)
    assert "/journal/comparison?" in (links["journal_comparison_path"] or "")

    with factory() as session:
        alert = session.get(PaperValidationAlert, uuid.UUID(candidate["source_alert_id"]))
        assert alert is not None
        assert alert.alert_type == PaperAlertType.RESEARCH_VALIDATION_PROMOTION.value

        draft = session.get(PaperValidationDraft, uuid.UUID(candidate["draft_id"]))
        assert draft is not None
        assert draft.source_alert_id == alert.id
        assert draft.prep_status == "ready_for_validation"

        row = session.get(PaperValidationCandidate, uuid.UUID(candidate["candidate_id"]))
        assert row is not None
        assert row.promotion_source == "research_validation"
        assert row.backtest_run_id == run.id


def test_promote_idempotent_returns_already_exists(
    client: tuple[TestClient, sessionmaker[Session], Settings],
) -> None:
    test_client, factory, _ = client
    headers = _auth(test_client, "at035-a@test.example")
    run = _seed_eligible_run(factory)

    first = test_client.post(
        "/research-validation/promote",
        headers=headers,
        json=_promote_payload(run.id),
    )
    assert first.status_code == 200
    candidate_id = first.json()["candidate"]["candidate_id"]

    second = test_client.post(
        "/research-validation/promote",
        headers=headers,
        json=_promote_payload(run.id),
    )
    assert second.status_code == 200
    body = second.json()
    assert body["already_exists"] is True
    assert body["candidate"]["candidate_id"] == candidate_id

    with factory() as session:
        rows = list(
            session.scalars(
                select(PaperValidationCandidate).where(
                    PaperValidationCandidate.organization_id == ORG_A,
                    PaperValidationCandidate.backtest_run_id == run.id,
                )
            ).all()
        )
        assert len(rows) == 1


# --------------------------------------------------------------------------- #
# Hard blocks
# --------------------------------------------------------------------------- #


def test_confirm_mismatch_blocked(
    client: tuple[TestClient, sessionmaker[Session], Settings],
) -> None:
    test_client, factory, _ = client
    headers = _auth(test_client, "at035-a@test.example")
    run = _seed_eligible_run(factory)

    response = test_client.post(
        "/research-validation/promote",
        headers=headers,
        json=_promote_payload(run.id, confirm="WRONG"),
    )
    assert response.status_code == 422
    assert "confirmation required" in response.json()["error"]["message"].lower()


def test_incomplete_backtest_blocked(
    client: tuple[TestClient, sessionmaker[Session], Settings],
) -> None:
    test_client, factory, _ = client
    headers = _auth(test_client, "at035-a@test.example")

    with factory() as session:
        strategy, version = _seed_strategy(session)
        run = _seed_completed_run(
            session,
            strategy,
            version,
            _tier2_result(),
            status="queued",
        )
        session.commit()
        run_id = run.id

    response = test_client.post(
        "/research-validation/promote",
        headers=headers,
        json=_promote_payload(run_id),
    )
    assert response.status_code == 422
    assert "not completed" in response.json()["error"]["message"].lower()


def test_missing_oos_metrics_blocked(
    client: tuple[TestClient, sessionmaker[Session], Settings],
) -> None:
    test_client, factory, _ = client
    headers = _auth(test_client, "at035-a@test.example")

    with factory() as session:
        strategy, version = _seed_strategy(session)
        run = _seed_completed_run(
            session,
            strategy,
            version,
            _tier2_result(),
            include_oos=False,
        )
        session.commit()
        run_id = run.id

    response = test_client.post(
        "/research-validation/promote",
        headers=headers,
        json=_promote_payload(run_id),
    )
    assert response.status_code == 422
    assert "out-of-sample" in response.json()["error"]["message"].lower()


def test_tier3_insufficient_evidence_blocked(
    client: tuple[TestClient, sessionmaker[Session], Settings],
) -> None:
    test_client, factory, _ = client
    headers = _auth(test_client, "at035-a@test.example")

    with factory() as session:
        strategy, version = _seed_strategy(session)
        run = _seed_completed_run(session, strategy, version, _tier3_result())
        session.commit()
        run_id = run.id

    response = test_client.post(
        "/research-validation/promote",
        headers=headers,
        json=_promote_payload(run_id),
    )
    assert response.status_code == 422
    message = response.json()["error"]["message"].lower()
    assert "tier3" in message or "insufficient evidence" in message


# --------------------------------------------------------------------------- #
# Tenant isolation + RBAC
# --------------------------------------------------------------------------- #


def test_tenant_isolation(
    client: tuple[TestClient, sessionmaker[Session], Settings],
) -> None:
    test_client, factory, _ = client
    headers_a = _auth(test_client, "at035-a@test.example")
    headers_b = _auth(test_client, "at035-b@test.example")

    with factory() as session:
        strategy, version = _seed_strategy(session, organization_id=ORG_A, user_id=USER_A)
        _seed_confirm_trades(session, strategy, version, count=5)
        run = _seed_completed_run(session, strategy, version, _tier2_result())
        session.commit()
        run_id = run.id

    assert (
        test_client.get(
            f"/research-validation/backtests/{run_id}/status",
            headers=headers_b,
        ).status_code
        == 404
    )
    assert (
        test_client.post(
            "/research-validation/promote",
            headers=headers_b,
            json=_promote_payload(run_id),
        ).status_code
        == 422
    )

    promote = test_client.post(
        "/research-validation/promote",
        headers=headers_a,
        json=_promote_payload(run_id),
    )
    assert promote.status_code == 200


def test_viewer_can_read_trader_can_promote_viewer_cannot_promote(
    client: tuple[TestClient, sessionmaker[Session], Settings],
) -> None:
    test_client, factory, _ = client
    viewer = _auth(test_client, "at035-viewer@test.example")
    trader = _auth(test_client, "at035-trader@test.example")
    run = _seed_eligible_run(factory)

    evidence = test_client.get("/research-validation/evidence", headers=viewer)
    assert evidence.status_code == 200

    status = test_client.get(
        f"/research-validation/backtests/{run.id}/status",
        headers=viewer,
    )
    assert status.status_code == 200

    blocked = test_client.post(
        "/research-validation/promote",
        headers=viewer,
        json=_promote_payload(run.id),
    )
    assert blocked.status_code == 403

    allowed = test_client.post(
        "/research-validation/promote",
        headers=trader,
        json=_promote_payload(run.id),
    )
    assert allowed.status_code == 200


# --------------------------------------------------------------------------- #
# Evidence warnings + candidate provenance display
# --------------------------------------------------------------------------- #


def test_evidence_endpoint_includes_insufficient_confirm_warning(
    client: tuple[TestClient, sessionmaker[Session], Settings],
) -> None:
    test_client, factory, _ = client
    headers = _auth(test_client, "at035-a@test.example")
    run = _seed_eligible_run(factory, confirm_trades=5)

    response = test_client.get(
        "/research-validation/evidence",
        params={"backtest_run_id": str(run.id)},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["note"] == "Advisory only — never feeds execution or risk decisions."
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["eligible_for_promotion"] is True
    assert item["evidence_tier"] == "tier2"
    assert "insufficient_confirm_sample" in item["warnings"]


def test_candidate_list_legacy_null_provenance_research_populated(
    client: tuple[TestClient, sessionmaker[Session], Settings],
) -> None:
    test_client, factory, _ = client
    headers = _auth(test_client, "at035-a@test.example")

    # Research promotion
    run = _seed_eligible_run(factory)
    promoted = test_client.post(
        "/research-validation/promote",
        headers=headers,
        json=_promote_payload(run.id),
    )
    assert promoted.status_code == 200
    research_candidate_id = promoted.json()["candidate"]["candidate_id"]

    # Legacy alert-draft candidate (no research provenance)
    with factory() as session:
        created = PaperAlertService(session).create(
            organization_id=ORG_A,
            user_id=USER_A,
            alert_type=PaperAlertType.SETUP_SIGNAL_DETECTED,
            message="order_block on BTCUSDT 15m",
            metadata={
                "source": PaperAlertSource.MARKET_WATCHER.value,
                "condition": "order_block",
                "symbol": "BTCUSDT",
                "timeframe": "15m",
                "direction": "long",
                "confidence": 0.85,
                "reason": "Clean retest setup.",
                "trigger_level": 65000.0,
                "invalidation_level": 64000.0,
                "metrics": {"latest_price": 65100.0},
            },
            dedup_key=f"test:order_block:{uuid.uuid4()}",
            skip_dedup=True,
            source=PaperAlertSource.MARKET_WATCHER,
        )
        assert created is not None
        row = session.get(PaperValidationAlert, created.id)
        assert row is not None
        row.review_status = SetupAlertReviewStatus.IMPORTANT.value
        alert_id = row.id
        session.commit()

    draft_resp = test_client.post(
        f"/alerts/setup-review/{alert_id}/draft",
        headers=headers,
        json={
            "confirm": CREATE_PAPER_VALIDATION_DRAFT_CONFIRM,
            "notes": "Legacy candidate",
            "risk_mode": "conservative",
        },
    )
    assert draft_resp.status_code == 200
    draft_id = draft_resp.json()["draft"]["draft_id"]
    prep = test_client.patch(
        f"/paper-validation/drafts/{draft_id}/prep",
        headers=headers,
        json=_READY_PREP,
    )
    assert prep.status_code == 200
    queued = test_client.post(
        f"/paper-validation/drafts/{draft_id}/queue",
        headers=headers,
        json={"confirm": QUEUE_PAPER_VALIDATION_CANDIDATE_CONFIRM},
    )
    assert queued.status_code == 200
    legacy_candidate_id = queued.json()["candidate"]["candidate_id"]

    listing = test_client.get("/paper-validation/candidates", headers=headers)
    assert listing.status_code == 200
    by_id = {item["candidate_id"]: item for item in listing.json()["items"]}

    legacy = by_id[legacy_candidate_id]
    assert legacy["promotion_source"] is None
    assert legacy["backtest_run_id"] is None
    assert legacy["evidence_tier"] is None

    research = by_id[research_candidate_id]
    assert research["promotion_source"] == "research_validation"
    assert research["backtest_run_id"] == str(run.id)
    assert research["evidence_tier"] == "tier2"
    assert research["dataset_hash"] == "a" * 64

    detail = test_client.get(
        f"/paper-validation/candidates/{research_candidate_id}",
        headers=headers,
    )
    assert detail.status_code == 200
    assert detail.json()["promotion_source"] == "research_validation"

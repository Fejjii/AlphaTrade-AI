"""Focused HTTP coverage using real authentication, DI and canonical records."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.db.base import Base
from app.db.models import Membership, Organization, User, UserStrategyVersion
from app.db.session import get_session
from app.main import create_app
from app.schemas.common import JournalTradeSource, MarketRegime, MembershipRole
from app.schemas.strategy_analytics import StrategyAnalyticsReport
from app.security.tokens import create_access_token
from app.services.strategy_analytics_service import StrategyAnalyticsService
from tests.test_strategy_analytics_foundation import (
    ORG,
    OTHER_ORG,
    OTHER_USER,
    START,
    USER,
    brain,
    strategy,
    trade,
)

PATH = "/strategy-analytics/report"
VIEWER = UUID(int=203)
TRADER = UUID(int=204)


@dataclass
class _Api:
    app: FastAPI
    factory: sessionmaker[Session]
    settings: Settings
    engine: Engine

    def headers(self, user_id: UUID = USER, organization_id: UUID = ORG) -> dict[str, str]:
        token, _ = create_access_token(
            user_id=user_id,
            organization_id=organization_id,
            email="api@example.test",
            settings=self.settings,
        )
        return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def api() -> Iterator[_Api]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    settings = Settings(
        _env_file=None,
        environment="local",
        log_json=False,
        database_url="sqlite+pysqlite:///:memory:",
        jwt_secret="analytics-api-test-secret-with-32-chars",
        execution_mode="paper",
        enable_real_trading=False,
        provider_mode="mock",
        market_data_provider="mock",
        market_data_enabled=False,
        market_data_cache_use_redis=False,
        rate_limit_use_redis=False,
        access_token_denylist_use_redis=False,
        alert_delivery_enabled=False,
        telegram_alerts_enabled=False,
        telegram_interaction_enabled=False,
        worker_enabled=False,
        market_watcher_enabled=False,
        watcher_orchestration_enabled=False,
        paper_signal_orchestration_enabled=False,
        journal_stats_max_rows=100,
    )
    with factory() as session:
        session.add_all(
            [
                Organization(id=ORG, name="Analytics API tenant"),
                Organization(id=OTHER_ORG, name="Other tenant"),
            ]
        )
        for user_id in (USER, OTHER_USER, VIEWER, TRADER):
            session.add(
                User(
                    id=user_id,
                    email=f"api-{user_id}@example.test",
                    hashed_password="unused",
                    email_verified=True,
                )
            )
        session.flush()
        for user_id, organization_id, role in (
            (USER, ORG, MembershipRole.OWNER),
            (OTHER_USER, OTHER_ORG, MembershipRole.OWNER),
            (VIEWER, ORG, MembershipRole.VIEWER),
            (TRADER, ORG, MembershipRole.TRADER),
        ):
            session.add(Membership(user_id=user_id, organization_id=organization_id, role=role))
        session.commit()
    app = create_app(settings=settings)

    def scoped_session() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = scoped_session
    yield _Api(app, factory, settings, engine)
    engine.dispose()


@pytest.fixture
async def client(api: _Api) -> AsyncIterator[AsyncClient]:
    # Exercise the full mounted app without starting unrelated background workers.
    async with AsyncClient(transport=ASGITransport(app=api.app), base_url="http://test") as http:
        yield http


@pytest.fixture
def records(api: _Api) -> dict[str, str]:
    with api.factory() as session:
        owner, first = strategy(session)
        second = UserStrategyVersion(
            strategy_id=owner.id,
            version=2,
            card={},
            content_hash="b" * 64,
        )
        session.add(second)
        session.commit()
        target = trade(
            session,
            user_strategy_id=owner.id,
            strategy_version_id=first.id,
            market_regime=MarketRegime.TRENDING_UP,
        )
        brain(session, target, owner=owner, version=first)
        revised = trade(
            session,
            user_strategy_id=owner.id,
            strategy_version_id=second.id,
            market_regime=MarketRegime.TRENDING_UP,
            exit_time=START + timedelta(hours=2),
        )
        brain(session, revised, stage="N3", owner=owner, version=second)
        other = trade(
            session,
            timeframe="5m",
            market_regime=MarketRegime.RANGING,
            exit_time=START + timedelta(hours=3),
        )
        brain(session, other, stage="N1")
        trade(
            session,
            symbol="ETHUSDT",
            source=JournalTradeSource.IMPORTED,
            exit_time=START + timedelta(hours=4),
        )
        return {"strategy_id": str(owner.id), "strategy_version_id": str(first.id)}


async def test_report_serializes_all_metrics_and_preserves_service_result(
    api: _Api,
    client: AsyncClient,
) -> None:
    with api.factory() as session:
        trade(session)
        trade(
            session,
            net_pnl=Decimal("-40"),
            gross_pnl=Decimal("-30"),
            exit_time=START + timedelta(hours=2),
        )
        expected = (
            StrategyAnalyticsService(session, max_rows=100)
            .compute(
                organization_id=ORG,
                user_id=USER,
            )
            .model_dump(mode="json")
        )
    response = await client.get(PATH, headers=api.headers())
    assert response.status_code == 200, response.text
    body = response.json()
    expected.pop("generated_at")
    actual = dict(body)
    actual.pop("generated_at")
    assert actual == expected
    assert StrategyAnalyticsReport.model_validate(body).contract_version == "strategy-analytics/v1"
    metrics = body["overall"]
    assert metrics["trade_count"] == 2
    assert metrics["win_rate"] == 0.5
    assert Decimal(metrics["expectancy"]) == 30
    assert metrics["average_r"] == metrics["median_r"] == 3
    assert metrics["profit_factor"] == 2.5
    assert Decimal(metrics["maximum_drawdown"]) == 40
    assert Decimal(metrics["average_mae_amount"]) == 4
    assert Decimal(metrics["average_mfe_amount"]) == 20
    assert metrics["average_holding_period_seconds"] == 5400
    assert Decimal(metrics["fees_total"]) == 6
    assert Decimal(metrics["slippage_total"]) == 10
    assert Decimal(metrics["net_pnl_total"]) == 60
    assert metrics["confidence"] == "insufficient"
    assert "low_sample" in {warning["code"] for warning in metrics["warnings"]}
    assert metrics["metric_samples"]["win_rate"]["sample_count"] == 2
    assert metrics["metric_samples"]["win_rate"]["insufficient_history"]
    assert metrics["missing_fields"]["nested_maturity_stage"] == 2
    assert body["limitations"]


async def test_empty_history_returns_nulls_and_small_sample_warnings(
    api: _Api,
    client: AsyncClient,
) -> None:
    response = await client.get(PATH, headers=api.headers())
    assert response.status_code == 200
    metrics = response.json()["overall"]
    assert metrics["trade_count"] == 0
    for field in (
        "win_rate",
        "expectancy",
        "average_r",
        "median_r",
        "profit_factor",
        "maximum_drawdown",
        "average_mae_amount",
        "average_mfe_amount",
        "average_holding_period_seconds",
        "fees_total",
        "slippage_total",
        "net_pnl_total",
    ):
        assert metrics[field] is None
    assert metrics["insufficient_history"] and metrics["confidence"] == "insufficient"
    assert "no_closed_trades" in {warning["code"] for warning in metrics["warnings"]}
    assert all(
        sample["sample_count"] == 0 and not sample["available"]
        for sample in metrics["metric_samples"].values()
    )


async def test_missing_data_and_recorded_zero_remain_distinct(
    api: _Api, client: AsyncClient
) -> None:
    with api.factory() as session:
        trade(
            session,
            fees=Decimal("0"),
            slippage=None,
            planned_risk_amount=None,
            mae_amount=None,
            mfe_amount=None,
            entry_time=None,
            exit_time=None,
        )
    response = await client.get(PATH, headers=api.headers())
    assert response.status_code == 200
    metrics = response.json()["overall"]
    assert Decimal(metrics["fees_total"]) == 0
    assert metrics["slippage_total"] is None
    assert Decimal(metrics["net_pnl_total"]) == 100
    for field in (
        "average_r",
        "median_r",
        "maximum_drawdown",
        "average_mae_amount",
        "average_mfe_amount",
        "average_holding_period_seconds",
        "cost_reconciled_net_pnl_total",
    ):
        assert metrics[field] is None
    assert metrics["missing_fields"]["slippage"] == 1
    assert "fees" not in metrics["missing_fields"]
    assert "costs_unverified" in {warning["code"] for warning in metrics["analytics_warnings"]}
    assert "low_sample" in {warning["code"] for warning in metrics["warnings"]}


@pytest.mark.parametrize(
    "name,value,count",
    [
        ("strategy_id", "$strategy_id", 2),
        ("strategy_version_id", "$strategy_version_id", 1),
        ("symbol", "BTCUSDT", 3),
        ("timeframe", "15m", 3),
        ("market_regime", "trending_up", 2),
        ("nested_maturity_stage", "N2", 1),
        ("source", "paper_execution", 3),
        ("date_to", (START + timedelta(hours=1)).isoformat(), 1),
        ("date_from", (START + timedelta(hours=4)).isoformat(), 1),
    ],
)
async def test_filters_reach_canonical_service(
    api: _Api,
    client: AsyncClient,
    records: dict[str, str],
    name: str,
    value: str,
    count: int,
) -> None:
    value = records[value[1:]] if value.startswith("$") else value
    response = await client.get(PATH, headers=api.headers(), params={name: value})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["overall"]["trade_count"] == count
    if name in {"date_from", "date_to"}:
        assert datetime.fromisoformat(body["filters"][name]) == datetime.fromisoformat(value)
    else:
        assert body["filters"][name] == value


async def test_combined_filters_and_repeated_grouping_dimensions(
    api: _Api,
    client: AsyncClient,
    records: dict[str, str],
) -> None:
    params = [
        *records.items(),
        ("symbol", "BTCUSDT"),
        ("timeframe", "15m"),
        ("market_regime", "trending_up"),
        ("nested_maturity_stage", "N2"),
        ("date_from", (START + timedelta(hours=1)).isoformat()),
        ("date_to", (START + timedelta(hours=1)).isoformat()),
        ("group_by", "strategy_version"),
        ("group_by", "nested_maturity_stage"),
        ("min_sample_size", "1"),
    ]
    response = await client.get(PATH, headers=api.headers(), params=params)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["overall"]["trade_count"] == 1
    assert body["group_by"] == ["strategy_version", "nested_maturity_stage"]
    assert body["buckets"][0]["dimensions"] == {
        "strategy_version": records["strategy_version_id"],
        "nested_maturity_stage": "N2",
    }
    # Changing the descriptive threshold must not remove canonical small-sample warnings.
    assert not body["overall"]["insufficient_history"]
    assert "low_sample" in {warning["code"] for warning in body["overall"]["warnings"]}


async def test_pagination_changes_only_bucket_page(
    api: _Api,
    client: AsyncClient,
    records: dict[str, str],
) -> None:
    responses = [
        await client.get(
            PATH,
            headers=api.headers(),
            params={
                "group_by": "symbol",
                "limit": 1,
                "offset": offset,
            },
        )
        for offset in (0, 1)
    ]
    assert all(response.status_code == 200 for response in responses)
    first, second = [response.json() for response in responses]
    assert first["overall"] == second["overall"]
    assert first["overall"]["trade_count"] == 4
    assert first["total_buckets"] == second["total_buckets"] == 2
    assert first["buckets"][0]["dimensions"]["symbol"] == "BTCUSDT"
    assert second["buckets"][0]["dimensions"]["symbol"] == "ETHUSDT"


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer invalid-token"}])
async def test_authentication_required(
    api: _Api,
    client: AsyncClient,
    headers: dict[str, str],
) -> None:
    response = await client.get(PATH, headers=headers)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


@pytest.mark.parametrize("user_id", [USER, VIEWER, TRADER])
async def test_canonical_reader_roles_can_read_their_own_history(
    api: _Api,
    client: AsyncClient,
    user_id: UUID,
) -> None:
    with api.factory() as session:
        trade(session, user_id=user_id)
    response = await client.get(PATH, headers=api.headers(user_id))
    assert response.status_code == 200, response.text
    assert response.json()["user_id"] == str(user_id)
    assert response.json()["overall"]["trade_count"] == 1


async def test_tenant_user_scope_cannot_be_overridden_by_query(
    api: _Api,
    client: AsyncClient,
) -> None:
    with api.factory() as session:
        trade(session)
        trade(session, user_id=VIEWER, net_pnl=Decimal("-888"))
        foreign = trade(
            session, organization_id=OTHER_ORG, user_id=OTHER_USER, net_pnl=Decimal("-999")
        )
        # Deliberately inconsistent lineage must not expose another tenant's setup.
        foreign_setup = brain(session, foreign, organization_id=OTHER_ORG)
    response = await client.get(
        PATH,
        headers=api.headers(),
        params={
            "organization_id": str(OTHER_ORG),
            "user_id": str(VIEWER),
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["organization_id"] == str(ORG) and body["user_id"] == str(USER)
    assert body["overall"]["trade_count"] == 1
    assert Decimal(body["overall"]["net_pnl_total"]) == 100
    filtered = await client.get(
        PATH,
        headers=api.headers(),
        params={
            "strategy_id": str(foreign_setup.strategy_id),
            "nested_maturity_stage": "N2",
        },
    )
    assert filtered.status_code == 200
    assert filtered.json()["overall"]["trade_count"] == 0
    invalid_membership = await client.get(PATH, headers=api.headers(USER, OTHER_ORG))
    assert invalid_membership.status_code == 401


async def test_configured_journal_row_cap_and_post_cap_filter_limitations(
    api: _Api,
    client: AsyncClient,
) -> None:
    with api.factory() as session:
        for index in range(101):
            journal = trade(
                session,
                id=UUID(int=5000 + index),
                exit_time=START + timedelta(hours=1, minutes=index),
            )
        last = brain(session, journal)
    response = await client.get(PATH, headers=api.headers())
    assert response.status_code == 200
    body = response.json()
    assert body["max_rows"] == body["scanned_trade_count"] == 100
    assert body["truncated"] and body["overall"]["trade_count"] == 100
    for metrics in (body["overall"], body["buckets"][0]["metrics"]):
        assert "result_truncated" in {warning["code"] for warning in metrics["warnings"]}
    selected = await client.get(
        PATH,
        headers=api.headers(),
        params={
            "strategy_id": str(last.strategy_id),
        },
    )
    assert selected.status_code == 200
    selected_body = selected.json()
    assert selected_body["truncated"] and selected_body["overall"]["trade_count"] == 0
    assert selected_body["overall"]["net_pnl_total"] is None
    assert any("after the row cap" in limitation for limitation in selected_body["limitations"])


async def test_successful_read_executes_only_selects_and_never_commits(
    api: _Api,
    client: AsyncClient,
    records: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    statements: list[str] = []

    def capture(_conn: object, _cursor: object, statement: str, *_args: object) -> None:
        statements.append(statement)

    def forbidden_commit(_session: Session) -> None:
        pytest.fail("Analytics GET must not commit any database mutation.")

    event.listen(api.engine, "before_cursor_execute", capture)
    monkeypatch.setattr(Session, "commit", forbidden_commit)
    try:
        response = await client.get(PATH, headers=api.headers(), params=records)
        assert response.status_code == 200, response.text
        assert statements and all(
            statement.lstrip().upper().startswith("SELECT") for statement in statements
        )
    finally:
        event.remove(api.engine, "before_cursor_execute", capture)


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
async def test_api_has_no_mutation_methods(api: _Api, client: AsyncClient, method: str) -> None:
    response = await client.request(method, PATH, headers=api.headers())
    assert response.status_code == 405
    assert response.headers["allow"] == "GET"


@pytest.mark.parametrize(
    "params",
    [
        {"strategy_id": "invalid"},
        {"strategy_version_id": "invalid"},
        {"market_regime": "invented"},
        {"nested_maturity_stage": "N0"},
        {"group_by": "invented"},
        {"group_by": ["symbol", "symbol"]},
        {"group_by": ["symbol"] * 7},
        {"date_from": "bad-date"},
        {"date_from": "2026-09-01T00:00:00"},
        {"date_from": "2026-09-02T00:00:00Z", "date_to": "2026-09-01T00:00:00Z"},
        {"date_to": "2026-09-01T00:00:00"},
        {"limit": "0"},
        {"limit": "201"},
        {"offset": "-1"},
        {"min_sample_size": "0"},
        {"min_sample_size": "1001"},
        {"symbol": "X" * 31},
        {"timeframe": "X" * 9},
    ],
)
async def test_invalid_queries_return_canonical_422_errors(
    api: _Api,
    client: AsyncClient,
    params: dict[str, Any],
) -> None:
    response = await client.get(PATH, headers=api.headers(), params=params)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "validation_error"


async def test_openapi_documents_filters_and_existing_contract(api: _Api) -> None:
    schema = api.app.openapi()
    assert set(schema["paths"][PATH]) == {"get"}
    operation = schema["paths"][PATH]["get"]
    parameters = {parameter["name"]: parameter for parameter in operation["parameters"]}
    assert set(parameters) >= {
        "strategy_id",
        "strategy_version_id",
        "symbol",
        "timeframe",
        "market_regime",
        "nested_maturity_stage",
        "date_from",
        "date_to",
        "group_by",
        "limit",
        "offset",
    }
    assert "organization_id" not in parameters and "user_id" not in parameters
    assert parameters["group_by"]["schema"]["type"] == "array"
    response = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert response["$ref"].endswith("/StrategyAnalyticsReport")

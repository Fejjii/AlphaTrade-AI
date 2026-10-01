"""Authenticated product adapter preserves the deterministic review contract."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.daily_review.reader import DailyReviewService
from app.daily_review.service import daily_window
from app.db.base import Base
from app.db.models import (
    JournalTrade,
    JournalTradeObservation,
    Membership,
    Organization,
    TradeJournal,
    User,
)
from app.db.session import get_session
from app.main import create_app
from app.paper_evaluation.contracts import PaperEvaluationStage
from app.persistence.paper_evaluation_postgres import PostgresPaperEvaluationStore
from app.schemas.common import (
    JournalObservationCategory,
    JournalTradeSource,
    JournalTradeStatus,
    MembershipRole,
    TradeDirection,
)
from app.security.passwords import hash_password
from tests.support.paper_evaluation import make_observation

ORG, OTHER_ORG, USER, PEER, OUTSIDER = (UUID(int=i) for i in range(1, 6))
AT = datetime(2026, 10, 1, 12, tzinfo=UTC)


@pytest.fixture
def review_api():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    settings = Settings(
        environment="local",
        database_url="sqlite://",
        jwt_secret="daily-review-api-test-secret-at-least-32-bytes",
        provider_mode="mock",
        market_data_provider="mock",
        rate_limit_use_redis=False,
        access_token_denylist_use_redis=False,
        execution_mode="paper",
        enable_real_trading=False,
        worker_enabled=False,
        watcher_orchestration_enabled=False,
        telegram_alerts_enabled=False,
        telegram_interaction_enabled=False,
    )
    with Session(engine) as session:
        session.add_all([Organization(id=ORG, name="A"), Organization(id=OTHER_ORG, name="B")])
        for user, org in [(USER, ORG), (PEER, ORG), (OUTSIDER, OTHER_ORG)]:
            session.add(
                User(
                    id=user,
                    email=f"{user.int}@test.example",
                    hashed_password=hash_password("TestPassword123!", settings),
                )
            )
            session.add(
                Membership(
                    user_id=user,
                    organization_id=org,
                    role=MembershipRole.VIEWER,
                )
            )
            session.add(
                JournalTrade(
                    id=UUID(int=100 + user.int),
                    organization_id=org,
                    user_id=user,
                    source=JournalTradeSource.PAPER_EXECUTION,
                    status=JournalTradeStatus.CLOSED,
                    symbol="BTCUSDT",
                    timeframe="1h",
                    direction=TradeDirection.LONG,
                    entry_time=AT,
                    exit_time=AT,
                    net_pnl=Decimal(user.int),
                )
            )
            session.add(
                TradeJournal(
                    id=UUID(int=200 + user.int),
                    organization_id=org,
                    user_id=user,
                    symbol="BTCUSDT",
                    timeframe="1h",
                    direction=TradeDirection.LONG,
                    entry_rationale="Plan",
                    mistakes=[f"private mistake {user.int}"],
                    lessons=f"private lesson {user.int}",
                    updated_at=AT,
                )
            )
            session.add(
                JournalTradeObservation(
                    organization_id=org,
                    journal_trade_id=UUID(int=100 + user.int),
                    category=JournalObservationCategory.EMOTIONAL,
                    observation=f"private reflection {user.int}",
                    recorded_by=user,
                    created_at=AT,
                )
            )
        store = PostgresPaperEvaluationStore(session)
        for org in [ORG, OTHER_ORG]:
            store.put(
                make_observation(
                    organization_id=org,
                    observation_id=UUID(int=300 + org.int),
                    source_event_id=f"scan-{org.int}",
                    occurred_at=AT,
                    stage=PaperEvaluationStage.WATCHER_SCAN,
                    scan_status="succeeded",
                )
            )
        session.commit()
    app = create_app(settings)

    def db_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = db_session
    yield TestClient(app), engine
    engine.dispose()


def headers(client, user=USER):
    response = client.post(
        "/auth/login",
        json={
            "email": f"{user.int}@test.example",
            "password": "TestPassword123!",
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['tokens']['access_token']}"}


def test_api_preserves_service_contract_and_provenance(review_api):
    client, engine = review_api
    response = client.get(
        "/dashboard/daily-review?date=2026-10-01&timezone=Europe/Berlin",
        headers=headers(client),
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    body = response.json()
    with Session(engine) as session:
        expected = DailyReviewService(session).review(
            organization_id=ORG,
            user_id=USER,
            window=daily_window(date(2026, 10, 1), "Europe/Berlin"),
            generated_at=datetime.fromisoformat(body["generated_at"]),
        )
    assert body == expected.model_dump(mode="json")
    assert Decimal(body["daily_pnl"][0]["recorded_net_pnl"]) == 3
    assert body["daily_pnl"][0]["win_rate"] is None
    assert body["daily_pnl"][0]["expectancy"] is None
    assert all(
        item["sources"][0]["record_id"] and item["sources"][0]["occurred_at"]
        for item in body["facts"]
    )
    assert not body["live_executable"] and not body["telegram_delivery"]


def test_api_scope_cannot_be_overridden_and_peers_keep_private_records(review_api):
    client, _ = review_api
    for user, org in [(USER, ORG), (PEER, ORG), (OUTSIDER, OTHER_ORG)]:
        response = client.get(
            f"/dashboard/daily-review?date=2026-10-01&organization_id={OTHER_ORG}&user_id={PEER}",
            headers=headers(client, user),
        )
        body = response.json()
        assert response.status_code == 200
        assert body["organization_id"] == str(org)
        assert body["user_id"] == str(user)
        assert Decimal(body["daily_pnl"][0]["recorded_net_pnl"]) == user.int
        assert f"private reflection {user.int}" in response.text
        for other in {USER, PEER, OUTSIDER} - {user}:
            assert f"private reflection {other.int}" not in response.text
            assert f"private mistake {other.int}" not in response.text
        watcher = [item for item in body["facts"] if item["topic"] == "watcher_activity"]
        assert [item["sources"][0]["record_id"] for item in watcher] == [
            str(UUID(int=300 + org.int))
        ]


def test_api_requires_valid_token_and_current_membership(review_api):
    client, engine = review_api
    assert client.get("/dashboard/daily-review").status_code == 401
    assert (
        client.get(
            "/dashboard/daily-review", headers={"Authorization": "Bearer invalid"}
        ).status_code
        == 401
    )
    auth = headers(client)
    with Session(engine) as session:
        session.execute(delete(Membership).where(Membership.user_id == USER))
        session.commit()
    assert client.get("/dashboard/daily-review", headers=auth).status_code == 401


@pytest.mark.parametrize(
    "query",
    [
        "date=not-a-date",
        "date=2026-02-30",
        "timezone=Unknown/Zone",
        "timezone=../UTC",
        "timezone=",
        "date=9999-12-31",
    ],
)
def test_invalid_date_timezone_returns_422(review_api, query):
    client, _ = review_api
    assert (
        client.get(f"/dashboard/daily-review?{query}", headers=headers(client)).status_code == 422
    )


@pytest.mark.parametrize("day,hours", [("2026-03-29", 23), ("2026-10-25", 25)])
def test_api_dst_window_and_empty_metrics(review_api, day, hours):
    client, _ = review_api
    body = client.get(
        f"/dashboard/daily-review?date={day}&timezone=Europe/Berlin",
        headers=headers(client),
    ).json()
    assert datetime.fromisoformat(body["window"]["end"]) - datetime.fromisoformat(
        body["window"]["start"]
    ) == timedelta(hours=hours)
    assert body["daily_pnl"] == []


def test_default_day_uses_requested_timezone(review_api, monkeypatch):
    from app.api.routes import dashboard

    class FixedClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 1, 23, 30, tzinfo=UTC)

    monkeypatch.setattr(dashboard, "datetime", FixedClock)
    client, _ = review_api
    body = client.get(
        "/dashboard/daily-review?timezone=Europe/Berlin", headers=headers(client)
    ).json()
    assert body["window"]["day"] == "2026-10-02"
    assert body["window"]["timezone"] == "Europe/Berlin"


def test_service_failure_is_not_an_empty_review(review_api, monkeypatch):
    client, _ = review_api
    auth = headers(client)

    def fail(*args, **kwargs):
        raise ValueError("Conflicting recorded evidence")

    monkeypatch.setattr(DailyReviewService, "review", fail)
    with pytest.raises(ValueError, match="Conflicting recorded evidence"):
        client.get("/dashboard/daily-review", headers=auth)


@pytest.mark.parametrize("role", list(MembershipRole))
def test_reader_roles_can_access_review(review_api, role):
    client, engine = review_api
    with Session(engine) as session:
        membership = session.query(Membership).filter_by(user_id=USER).one()
        membership.role = role
        session.commit()
    assert client.get("/dashboard/daily-review", headers=headers(client)).status_code == 200

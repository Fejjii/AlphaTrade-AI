"""Slice 50 — demo seed idempotency, safety, and dashboard integration."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Environment, Settings
from app.db.base import Base
from app.db.models import LessonCandidate, PaperValidationAlert, UserStrategy
from app.db.session import get_session
from app.main import create_app
from app.schemas.common import LessonCandidateStatus
from app.services.dashboard_summary_service import DashboardSummaryService
from app.services.demo_seed_service import (
    DEMO_EMAIL,
    DemoSeedService,
    assert_demo_seed_allowed,
)

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


@pytest.fixture
def demo_seed_env() -> Iterator[tuple[sessionmaker[Session], Settings]]:
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
        demo_seed_enabled=True,
        log_json=False,
        execution_mode="paper",
        enable_real_trading=False,
        database_url="sqlite+pysqlite:///:memory:",
        jwt_secret="demo-seed-test-secret-key-32bytes",
        rate_limit_use_redis=False,
        access_token_denylist_use_redis=False,
        provider_mode="mock",
        market_data_provider="mock",
        require_email_verified=False,
    )
    yield factory, settings
    engine.dispose()


@pytest.fixture
def demo_client(demo_seed_env: tuple[sessionmaker[Session], Settings]) -> TestClient:
    factory, settings = demo_seed_env
    app = create_app(settings)

    def _override_session() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = _override_session
    return TestClient(app)


def test_demo_seed_refused_on_staging_without_flag() -> None:
    settings = Settings.model_construct(
        environment=Environment.STAGING,
        demo_seed_enabled=False,
        execution_mode="paper",
        enable_real_trading=False,
        real_trading_enabled=False,
    )
    with pytest.raises(Exception, match="DEMO_SEED_ENABLED"):
        assert_demo_seed_allowed(settings)


def test_demo_seed_refused_in_production() -> None:
    settings = Settings.model_construct(
        environment=Environment.PRODUCTION,
        demo_seed_enabled=True,
        execution_mode="paper",
        enable_real_trading=False,
        real_trading_enabled=False,
    )
    with pytest.raises(Exception, match="production"):
        assert_demo_seed_allowed(settings)


def test_demo_seed_idempotent_and_paper_only(
    demo_seed_env: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, settings = demo_seed_env
    with factory() as session:
        service = DemoSeedService(session, settings)
        first = service.seed(password="DemoPaper2026!")
        second = service.seed(password="DemoPaper2026!")
        assert first.email == second.email == DEMO_EMAIL
        assert first.organization_id == second.organization_id

        strategy_count = session.scalar(
            select(func.count())
            .select_from(UserStrategy)
            .where(UserStrategy.organization_id == first.organization_id)
        )
        assert strategy_count == 3

        pending = session.scalar(
            select(func.count())
            .select_from(LessonCandidate)
            .where(
                LessonCandidate.organization_id == first.organization_id,
                LessonCandidate.status == LessonCandidateStatus.PENDING_REVIEW.value,
            )
        )
        accepted = session.scalar(
            select(func.count())
            .select_from(LessonCandidate)
            .where(
                LessonCandidate.organization_id == first.organization_id,
                LessonCandidate.status == LessonCandidateStatus.ACCEPTED.value,
            )
        )
        assert pending == 3
        assert accepted == 2

        alerts = session.scalars(
            select(PaperValidationAlert).where(
                PaperValidationAlert.organization_id == first.organization_id
            )
        ).all()
        assert len(alerts) == 4
        for alert in alerts:
            assert alert.delivery_status.value == "disabled"


def test_dashboard_summary_after_seed(
    demo_seed_env: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, settings = demo_seed_env
    with factory() as session:
        result = DemoSeedService(session, settings).seed(password="DemoPaper2026!")
        summary = DashboardSummaryService(session, settings).summarize(
            organization_id=result.organization_id,
            user_id=result.user_id,
        )
        assert summary.safety.execution_mode == "paper"
        assert summary.safety.real_trading_enabled is False
        assert summary.daily_discipline is not None
        assert summary.strategy_readiness is not None
        assert len(summary.active_paper_validations) >= 1
        assert summary.alerts_lessons is not None


def test_demo_seed_endpoint_owner_only(demo_client: TestClient) -> None:
    register = demo_client.post(
        "/auth/register",
        json={
            "email": "other-owner@test.example",
            "password": "DemoPaper2026!",
            "organization_name": "Other Org",
        },
    )
    assert register.status_code == 201
    token = register.json()["tokens"]["access_token"]
    with demo_client as client:
        seeded = client.post("/demo/seed", headers={"Authorization": f"Bearer {token}"})
        assert seeded.status_code == 200
        body = seeded.json()
        assert body["paper_only"] is True
        assert body["synthetic"] is True
        assert body["strategies_seeded"] == 3


def test_health_exposes_must_verify_email(demo_client: TestClient) -> None:
    health = demo_client.get("/health")
    assert health.status_code == 200
    body = health.json()
    assert body["must_verify_email"] is False
    assert body["real_trading_enabled"] is False

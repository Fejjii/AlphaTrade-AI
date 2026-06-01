"""Model creation, constraints, and repository boundary tests (SQLite).

These tests use an isolated in-memory SQLite database so they are fully
deterministic and require no running PostgreSQL.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import (
    ApprovalRequest,
    DailyRiskState,
    Organization,
    SetupDefinition,
    SetupPerformance,
    TradeProposal,
    User,
)
from app.repositories.users import UserRepository
from app.schemas.common import RiskSeverity, SetupCategory, StrategyId, TradeDirection


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn: object, _record: object) -> None:
        cursor = dbapi_conn.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


def _make_org_and_user(
    session: Session, email: str = "trader@example.com"
) -> tuple[Organization, User]:
    org = Organization(name=f"Org-{email}")
    user = User(email=email, hashed_password="not-a-real-hash")
    session.add_all([org, user])
    session.flush()
    return org, user


def test_create_user_and_lookup_by_email(db_session: Session) -> None:
    _, user = _make_org_and_user(db_session)
    db_session.commit()

    repo = UserRepository(db_session)
    found = repo.get_by_email("trader@example.com")
    assert found is not None
    assert found.id == user.id
    assert found.is_active is True


def test_user_email_unique_constraint(db_session: Session) -> None:
    _make_org_and_user(db_session, email="dup@example.com")
    db_session.commit()

    db_session.add(User(email="dup@example.com", hashed_password="x"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_daily_risk_state_unique_per_org_user_day(db_session: Session) -> None:
    org, user = _make_org_and_user(db_session)
    db_session.commit()

    today = date(2026, 6, 1)
    db_session.add(
        DailyRiskState(
            organization_id=org.id,
            user_id=user.id,
            day=today,
            daily_loss_limit=Decimal("500"),
        )
    )
    db_session.commit()

    db_session.add(
        DailyRiskState(
            organization_id=org.id,
            user_id=user.id,
            day=today,
            daily_loss_limit=Decimal("500"),
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_base_repository_crud(db_session: Session) -> None:
    _, user = _make_org_and_user(db_session)
    db_session.commit()

    repo = UserRepository(db_session)
    fetched = repo.get(user.id)
    assert fetched is not None
    assert repo.list(limit=10)

    repo.delete(fetched)
    db_session.commit()
    assert repo.get(user.id) is None


def test_proposal_and_approval_relationship(db_session: Session) -> None:
    org, user = _make_org_and_user(db_session)
    db_session.flush()

    proposal = TradeProposal(
        organization_id=org.id,
        user_id=user.id,
        strategy_id=StrategyId.HTF_TREND_PULLBACK,
        symbol="BTCUSDT",
        timeframe="4h",
        direction=TradeDirection.LONG,
        entry_price=Decimal("60000"),
        position_size=Decimal("0.1"),
        leverage=Decimal("3"),
        stop_loss=Decimal("58000"),
        take_profits=[{"price": "62000", "size_fraction": 0.5}],
        invalidation="close below 58000",
        confidence=0.7,
        risk_level=RiskSeverity.MEDIUM,
        rationale="pullback to support",
    )
    db_session.add(proposal)
    db_session.flush()

    approval = ApprovalRequest(
        proposal_id=proposal.id,
        organization_id=org.id,
        user_id=user.id,
        risk_level=RiskSeverity.MEDIUM,
        confidence=0.7,
    )
    db_session.add(approval)
    db_session.commit()

    assert approval.proposal_id == proposal.id
    assert proposal.take_profits[0]["price"] == "62000"


def test_setup_definition_and_performance(db_session: Session) -> None:
    setup = SetupDefinition(
        name="HTF Trend Pullback",
        strategy_id=StrategyId.HTF_TREND_PULLBACK,
        category=SetupCategory.TREND,
        version=1,
        rules=["with HTF trend", "wait for confirmation"],
    )
    db_session.add(setup)
    db_session.flush()

    perf = SetupPerformance(setup_id=setup.id, trades=10, wins=6, losses=4, win_rate=0.6)
    db_session.add(perf)
    db_session.commit()

    assert perf.setup_id == setup.id
    assert setup.rules == ["with HTF trend", "wait for confirmation"]


def test_setup_definition_name_version_unique(db_session: Session) -> None:
    common = {
        "strategy_id": StrategyId.LIQUIDITY_SWEEP_REVERSAL,
        "category": SetupCategory.REVERSAL,
        "version": 1,
    }
    db_session.add(SetupDefinition(name="Sweep", **common))
    db_session.commit()

    db_session.add(SetupDefinition(name="Sweep", **common))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_models_have_timestamps_after_commit(db_session: Session) -> None:
    _, user = _make_org_and_user(db_session)
    db_session.commit()
    assert isinstance(user.created_at, datetime)
    assert user.created_at.tzinfo is not None or user.created_at <= datetime.now(UTC).replace(
        tzinfo=None
    )

"""PostgreSQL helpers for watcher/telegram persistence tests."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.db.base import Base
from app.db.canonical_candidates import CanonicalCandidateRow  # noqa: F401
from app.db.canonical_eligibility import ActionEligibilityEvaluationRow  # noqa: F401
from app.db.canonical_trade_plans import CanonicalTradePlanRootRow  # noqa: F401
from app.db.models import Organization  # noqa: F401  — register metadata
from app.db.paper_evaluation import PaperEvaluationObservationRow  # noqa: F401
from app.db.telegram_security import TelegramBindingRow  # noqa: F401
from app.db.watcher_orchestration import WatcherWorkerLeaseRow  # noqa: F401

POSTGRES_URL = os.environ.get(
    "PHASE1_POSTGRES_URL",
    os.environ.get(
        "AT028_POSTGRES_URL",
        "postgresql+psycopg://alphatrade:alphatrade@localhost:5432/alphatrade_test",
    ),
)


def postgres_available() -> bool:
    try:
        engine = create_engine(POSTGRES_URL, poolclass=NullPool)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


requires_postgres = pytest.mark.skipif(
    not postgres_available(),
    reason=f"PostgreSQL not reachable at {POSTGRES_URL}",
)


def _persistence_tables() -> list[object]:
    return [
        table
        for table in Base.metadata.sorted_tables
        if table.name.startswith(
            ("watcher_", "telegram_security_", "canonical_candidate", "action_eligibility")
        )
    ]


def persistence_session_factory() -> sessionmaker[Session]:
    engine = create_engine(POSTGRES_URL, poolclass=NullPool, future=True)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    tables = _persistence_tables()
    Base.metadata.create_all(engine, tables=tables)
    return sessionmaker(bind=engine, expire_on_commit=False)


def phase7_plan_session_factory() -> sessionmaker[Session]:
    """Full schema for canonical TradePlanRevision PostgreSQL tests."""

    engine = create_engine(POSTGRES_URL, poolclass=NullPool, future=True)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)

"""Alembic cycle for PR 77 hardening migrations on PostgreSQL."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

POSTGRES_URL = os.environ.get(
    "PHASE1_POSTGRES_URL",
    os.environ.get(
        "AT028_POSTGRES_URL",
        "postgresql+psycopg://alphatrade:alphatrade@localhost:5432/alphatrade_test",
    ),
)

MAIN_HEAD = "6d4e9f0a12b3"
PHASE2 = "7e8f1a2b3c4d"
PHASE3 = "8a9b0c1d2e3f"
PHASE4 = "9b0c1d2e3f4a"
HARDENING = "a0c1d2e3f4b5"


def _postgres_available() -> bool:
    try:
        engine = create_engine(POSTGRES_URL, poolclass=NullPool)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


requires_postgres = pytest.mark.skipif(
    not _postgres_available(),
    reason=f"PostgreSQL not reachable at {POSTGRES_URL}",
)


def _alembic_config() -> Config:
    backend_root = Path(__file__).resolve().parents[1]
    ini = backend_root / "alembic.ini"
    config = Config(str(ini))
    config.set_main_option("sqlalchemy.url", POSTGRES_URL)
    config.set_main_option("script_location", str(backend_root / "src/app/db/migrations"))
    os.environ["ALEMBIC_DATABASE_URL"] = POSTGRES_URL
    return config


@requires_postgres
def test_pr77_alembic_upgrade_downgrade_reupgrade() -> None:
    engine = create_engine(POSTGRES_URL, poolclass=NullPool, future=True)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    config = _alembic_config()
    command.upgrade(config, "head")
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert version == HARDENING
        has_pattern = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'user_strategy_versions' AND column_name = 'pattern_spec'"
            )
        ).scalar()
        assert has_pattern == 1
        nullable = conn.execute(
            text(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_name = 'user_strategy_versions' AND column_name = 'content_hash'"
            )
        ).scalar()
        assert nullable == "NO"
        trigger = conn.execute(
            text(
                "SELECT 1 FROM pg_trigger "
                "WHERE tgname = 'trg_user_strategy_versions_semantic_immutable'"
            )
        ).scalar()
        assert trigger == 1

    command.downgrade(config, PHASE4)
    command.downgrade(config, PHASE3)
    command.downgrade(config, PHASE2)
    command.downgrade(config, MAIN_HEAD)
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert version == MAIN_HEAD
        missing = conn.execute(
            text("SELECT 1 FROM information_schema.tables WHERE table_name = 'model_call_attempts'")
        ).scalar()
        assert missing is None

    command.upgrade(config, "head")
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert version == HARDENING
        count = conn.execute(text("SELECT COUNT(*) FROM user_strategy_versions")).scalar()
        assert int(count or 0) == 0
        backfill_ok = conn.execute(
            text(
                "SELECT COUNT(*) FROM user_strategy_versions "
                "WHERE content_hash IS NULL OR length(content_hash) <> 64"
            )
        ).scalar()
        assert int(backfill_ok or 0) == 0
    engine.dispose()

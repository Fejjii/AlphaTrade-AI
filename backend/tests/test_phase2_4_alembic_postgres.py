"""Alembic cycle for PR 77 hardening migrations on PostgreSQL."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
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
WATCHER_TELEGRAM_PERSISTENCE = "3ec264f9aaa8"
CANONICAL_CANDIDATE_PERSISTENCE = "4fd8c1a90b27"

_NEW_TABLES = (
    "watcher_worker_leases",
    "watcher_scheduled_scans",
    "watcher_scan_lineages",
    "telegram_security_action_nonces",
    "telegram_security_action_receipts",
    "telegram_security_outbox",
    "telegram_security_enrollment_challenges",
    "telegram_security_bindings",
    "telegram_security_authorization_intents",
    "canonical_candidates",
    "canonical_candidate_creation_keys",
    "canonical_candidate_transitions",
    "canonical_candidate_transition_keys",
)


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
        assert version == CANONICAL_CANDIDATE_PERSISTENCE
        for table_name in _NEW_TABLES:
            present = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name = :name"
                ),
                {"name": table_name},
            ).scalar()
            assert present == 1, table_name
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

    command.downgrade(config, HARDENING)
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert version == HARDENING
        for table_name in _NEW_TABLES:
            missing = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name = :name"
                ),
                {"name": table_name},
            ).scalar()
            assert missing is None, table_name

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
        assert version == CANONICAL_CANDIDATE_PERSISTENCE
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


def test_alembic_single_head() -> None:
    config = _alembic_config()
    heads = ScriptDirectory.from_config(config).get_heads()
    assert heads == [CANONICAL_CANDIDATE_PERSISTENCE]


@requires_postgres
def test_canonical_candidate_alembic_upgrade_downgrade() -> None:
    engine = create_engine(POSTGRES_URL, poolclass=NullPool, future=True)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    config = _alembic_config()
    command.upgrade(config, "head")
    candidate_tables = (
        "canonical_candidates",
        "canonical_candidate_creation_keys",
        "canonical_candidate_transitions",
        "canonical_candidate_transition_keys",
    )
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert version == CANONICAL_CANDIDATE_PERSISTENCE
        for table_name in candidate_tables:
            present = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name = :name"
                ),
                {"name": table_name},
            ).scalar()
            assert present == 1, table_name
        unique_hash = conn.execute(
            text(
                "SELECT 1 FROM pg_constraint "
                "WHERE conname = 'uq_canonical_candidates_uniqueness_hash'"
            )
        ).scalar()
        assert unique_hash == 1
        trigger = conn.execute(
            text(
                "SELECT 1 FROM pg_trigger "
                "WHERE tgname = 'trg_canonical_candidate_transitions_append_only'"
            )
        ).scalar()
        assert trigger == 1

    command.downgrade(config, WATCHER_TELEGRAM_PERSISTENCE)
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert version == WATCHER_TELEGRAM_PERSISTENCE
        for table_name in candidate_tables:
            missing = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name = :name"
                ),
                {"name": table_name},
            ).scalar()
            assert missing is None, table_name
        watcher = conn.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = 'watcher_worker_leases'"
            )
        ).scalar()
        assert watcher == 1

    command.upgrade(config, "head")
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO canonical_candidates ("
                "candidate_id, organization_id, uniqueness_hash, schema_version, "
                "strategy_version_id, setup_definition_id, fusion_policy_version, "
                "direction, evidence_venue, evidence_market, evidence_instrument, "
                "timeframe, evidence_window_hash, assessment_id, executable_setup, "
                "evidence_identity, state, created_at, valid_until, transition_version, "
                "idempotency_key, correlation_id, content_hash"
                ") VALUES ("
                "gen_random_uuid(), gen_random_uuid(), :uhash, 'Candidate/v1', "
                "gen_random_uuid(), gen_random_uuid(), 'fusion/v1', "
                "'short', 'binance', 'perpetual', 'instrument-id-value', "
                "'15m', :uhash, gen_random_uuid(), '{}'::json, '{}'::json, 'active', "
                "now(), now() + interval '1 hour', 1, "
                "'idempotency-key', gen_random_uuid(), :uhash"
                ")"
            ),
            {"uhash": "a" * 64},
        )
    blocked = False
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM canonical_candidates"))
    except Exception:
        blocked = True
    assert blocked is True
    engine.dispose()

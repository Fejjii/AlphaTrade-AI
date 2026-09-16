"""PostgreSQL enforcement for append-only execution history.

ORM listeners are not sufficient. Production PostgreSQL rejects UPDATE/DELETE on
immutable historical rows. SQLite tests keep ORM listeners only; PostgreSQL
``create_all`` and Alembic both install these triggers.
"""

from __future__ import annotations

from sqlalchemy import event, inspect, text
from sqlalchemy.engine import Connection

from app.db.base import Base

# Frozen for Phase 1/3 Alembic: those migrations run before Phase 4 tables exist.
CORE_IMMUTABLE_HISTORY_TABLES: tuple[str, ...] = (
    "execution_commands",
    "execution_receipts",
    "execution_transitions",
    "execution_fill_facts",
    "compiled_setup_definitions",
    "strategy_lifecycle_events",
    "manual_level_revisions",
)

PHASE4_IMMUTABLE_HISTORY_TABLES: tuple[str, ...] = (
    "journal_lifecycle_events",
    "journal_projection_receipts",
    "journal_trade_venue_corrections",
)

IMMUTABLE_HISTORY_TABLES: tuple[str, ...] = (
    CORE_IMMUTABLE_HISTORY_TABLES + PHASE4_IMMUTABLE_HISTORY_TABLES
)

_FUNCTION_NAME = "alphatrade_forbid_historical_mutation"
_EXCEPTION_MARKER = "alphatrade_immutable_history"

_CREATE_FUNCTION_SQL = f"""
CREATE OR REPLACE FUNCTION {_FUNCTION_NAME}()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  RAISE EXCEPTION USING
    MESSAGE = '{_EXCEPTION_MARKER}:' || TG_TABLE_NAME || ':' || TG_OP,
    ERRCODE = 'P0001';
END;
$$;
"""

_DROP_FUNCTION_SQL = f"DROP FUNCTION IF EXISTS {_FUNCTION_NAME}() CASCADE"


def _trigger_name(table: str) -> str:
    return f"trg_{table}_immutable"


def _install_statements_for(tables: tuple[str, ...]) -> tuple[str, ...]:
    statements = [_CREATE_FUNCTION_SQL.strip()]
    for table in tables:
        trigger = _trigger_name(table)
        statements.append(f"DROP TRIGGER IF EXISTS {trigger} ON {table}")
        statements.append(
            f"CREATE TRIGGER {trigger} BEFORE UPDATE OR DELETE ON {table} "
            f"FOR EACH ROW EXECUTE PROCEDURE {_FUNCTION_NAME}()"
        )
    return tuple(statements)


def historical_immutability_install_statements() -> tuple[str, ...]:
    """Core tables only. Phase 1/3 Alembic calls this before Phase 4 tables exist."""
    return _install_statements_for(CORE_IMMUTABLE_HISTORY_TABLES)


def historical_immutability_phase4_install_statements() -> tuple[str, ...]:
    """Phase 4 journal history tables. Function create is included (OR REPLACE)."""
    return _install_statements_for(PHASE4_IMMUTABLE_HISTORY_TABLES)


def historical_immutability_uninstall_statements() -> tuple[str, ...]:
    statements = [
        f"DROP TRIGGER IF EXISTS {_trigger_name(table)} ON {table}"
        for table in IMMUTABLE_HISTORY_TABLES
    ]
    statements.append(_DROP_FUNCTION_SQL)
    return tuple(statements)


def _run_sql(connection: Connection, sql: str) -> None:
    connection.execute(text(sql))


def install_historical_immutability(connection: Connection) -> None:
    """Install forbid-update/delete triggers. No-op on non-PostgreSQL dialects."""

    if connection.dialect.name != "postgresql":
        return
    inspector = inspect(connection)
    existing = tuple(table for table in IMMUTABLE_HISTORY_TABLES if inspector.has_table(table))
    for statement in _install_statements_for(existing):
        _run_sql(connection, statement)


def uninstall_historical_immutability(connection: Connection) -> None:
    """Remove triggers and function. No-op on non-PostgreSQL dialects."""

    if connection.dialect.name != "postgresql":
        return
    for statement in historical_immutability_uninstall_statements():
        _run_sql(connection, statement)


def is_historical_immutability_error(exc: BaseException) -> bool:
    return _EXCEPTION_MARKER in str(exc)


@event.listens_for(Base.metadata, "after_create")
def _install_after_metadata_create(
    _target: object,
    connection: Connection,
    **_kwargs: object,
) -> None:
    install_historical_immutability(connection)

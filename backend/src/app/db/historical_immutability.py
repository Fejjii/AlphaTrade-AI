"""PostgreSQL enforcement for append-only execution history.

ORM listeners are not sufficient. Production PostgreSQL rejects UPDATE/DELETE on
immutable historical rows. SQLite tests keep ORM listeners only; PostgreSQL
``create_all`` and Alembic both install these triggers.
"""

from __future__ import annotations

from sqlalchemy import event, text
from sqlalchemy.engine import Connection

from app.db.base import Base

IMMUTABLE_HISTORY_TABLES: tuple[str, ...] = (
    "execution_commands",
    "execution_receipts",
    "execution_transitions",
    "execution_fill_facts",
    "compiled_setup_definitions",
    "strategy_lifecycle_events",
    "manual_level_revisions",
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


def historical_immutability_install_statements() -> tuple[str, ...]:
    statements = [_CREATE_FUNCTION_SQL.strip()]
    for table in IMMUTABLE_HISTORY_TABLES:
        trigger = _trigger_name(table)
        statements.append(f"DROP TRIGGER IF EXISTS {trigger} ON {table}")
        statements.append(
            f"CREATE TRIGGER {trigger} BEFORE UPDATE OR DELETE ON {table} "
            f"FOR EACH ROW EXECUTE PROCEDURE {_FUNCTION_NAME}()"
        )
    return tuple(statements)


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
    for statement in historical_immutability_install_statements():
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

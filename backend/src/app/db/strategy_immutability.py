"""ORM listeners for immutable strategy versions, compiled setups, and level revisions."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import event, inspect, text
from sqlalchemy.orm import Mapper

from app.core.errors import ValidationAppError
from app.services.canonical_serialization import canonical_sha256

_SEMANTIC_VERSION_FIELDS = frozenset(
    {
        "card",
        "structured_rules",
        "lesson_source_metadata",
        "pattern_spec",
        "content_hash",
        "parent_version_id",
        "change_source",
        "change_reason",
        "actor_user_id",
        "content_diff",
        "version",
        "strategy_id",
    }
)

_MUTABLE_EVALUATION_FIELDS = frozenset(
    {
        "validation_status",
        "backtest_status",
        "paper_validation_status",
        "updated_at",
    }
)

_PG_SEMANTIC_COLUMNS = (
    "strategy_id",
    "version",
    "card",
    "structured_rules",
    "lesson_source_metadata",
    "pattern_spec",
    "parent_version_id",
    "actor_user_id",
    "change_reason",
    "change_source",
    "content_diff",
    "content_hash",
)
_PG_JSON_COLUMNS = frozenset(
    {
        "card",
        "structured_rules",
        "lesson_source_metadata",
        "pattern_spec",
        "content_diff",
    }
)

_PG_VERSION_FUNCTION = "alphatrade_forbid_strategy_version_semantic_mutation"
_PG_VERSION_MARKER = "alphatrade_strategy_version_immutable"
_PG_VERSION_TRIGGER = "trg_user_strategy_versions_semantic_immutable"

_registered = False


class StrategyVersionImmutabilityError(ValidationAppError):
    code = "strategy_version_immutable"


class ImmutableHistoryError(ValidationAppError):
    code = "immutable_history_row"


def strategy_version_content_hash(
    *,
    card: dict[str, Any] | None,
    structured_rules: dict[str, Any] | None,
    lesson_source_metadata: dict[str, Any] | None,
    pattern_spec: dict[str, Any] | None = None,
) -> str:
    return canonical_sha256(
        {
            "card": card or {},
            "structured_rules": structured_rules,
            "lesson_source_metadata": lesson_source_metadata,
            "pattern_spec": pattern_spec,
        }
    )


def _fill_version_hash(_mapper: Mapper[Any], _connection: Any, target: Any) -> None:
    target.content_hash = strategy_version_content_hash(
        card=getattr(target, "card", None),
        structured_rules=getattr(target, "structured_rules", None),
        lesson_source_metadata=getattr(target, "lesson_source_metadata", None),
        pattern_spec=getattr(target, "pattern_spec", None),
    )


def _forbid_semantic_version_update(_mapper: Mapper[Any], _connection: Any, target: Any) -> None:
    state = inspect(target)
    changed = [
        name
        for name in _SEMANTIC_VERSION_FIELDS
        if name in state.attrs and state.attrs[name].history.has_changes()
    ]
    if changed:
        raise StrategyVersionImmutabilityError(
            "Semantic strategy version fields are immutable; create a new draft version.",
            details={"fields": changed, "version_id": str(getattr(target, "id", ""))},
        )


def _forbid_row_mutation(_mapper: Mapper[Any], _connection: Any, target: Any) -> None:
    raise ImmutableHistoryError(
        f"{type(target).__name__} rows are append-only and cannot be updated.",
        details={"model": type(target).__name__, "id": str(getattr(target, "id", ""))},
    )


def _forbid_row_delete(_mapper: Mapper[Any], _connection: Any, target: Any) -> None:
    raise ImmutableHistoryError(
        f"{type(target).__name__} rows are append-only and cannot be deleted.",
        details={"model": type(target).__name__, "id": str(getattr(target, "id", ""))},
    )


def _forbid_version_delete(_mapper: Mapper[Any], _connection: Any, target: Any) -> None:
    raise StrategyVersionImmutabilityError(
        "UserStrategyVersion rows cannot be deleted; rollback selects an older version.",
        details={"version_id": str(getattr(target, "id", ""))},
    )


def strategy_version_pg_immutability_install_statements() -> tuple[str, ...]:
    """PostgreSQL trigger: semantic columns immutable; evaluation status remains mutable."""

    comparisons = " OR ".join(
        (
            f"NEW.{column}::jsonb IS DISTINCT FROM OLD.{column}::jsonb"
            if column in _PG_JSON_COLUMNS
            else f"NEW.{column} IS DISTINCT FROM OLD.{column}"
        )
        for column in _PG_SEMANTIC_COLUMNS
    )
    allowed = ", ".join(sorted(_MUTABLE_EVALUATION_FIELDS))
    function_sql = f"""
CREATE OR REPLACE FUNCTION {_PG_VERSION_FUNCTION}()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  -- Mutable evaluation fields remain writable: {allowed}
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION USING
      MESSAGE = '{_PG_VERSION_MARKER}:user_strategy_versions:DELETE',
      ERRCODE = 'P0001';
  END IF;
  IF {comparisons} THEN
    RAISE EXCEPTION USING
      MESSAGE = '{_PG_VERSION_MARKER}:user_strategy_versions:UPDATE',
      ERRCODE = 'P0001';
  END IF;
  RETURN NEW;
END;
$$;
"""
    return (
        function_sql.strip(),
        f"DROP TRIGGER IF EXISTS {_PG_VERSION_TRIGGER} ON user_strategy_versions",
        (
            f"CREATE TRIGGER {_PG_VERSION_TRIGGER} BEFORE UPDATE OR DELETE "
            f"ON user_strategy_versions FOR EACH ROW EXECUTE PROCEDURE {_PG_VERSION_FUNCTION}()"
        ),
    )


def strategy_version_pg_immutability_uninstall_statements() -> tuple[str, ...]:
    return (
        f"DROP TRIGGER IF EXISTS {_PG_VERSION_TRIGGER} ON user_strategy_versions",
        f"DROP FUNCTION IF EXISTS {_PG_VERSION_FUNCTION}() CASCADE",
    )


def is_strategy_version_immutability_error(exc: BaseException) -> bool:
    return _PG_VERSION_MARKER in str(exc)


def backfill_strategy_version_content_hashes(connection: Any) -> int:
    """Compute the canonical content hash for every UserStrategyVersion row.

    Does not invent Pattern semantics. Missing ``pattern_spec`` hashes as null and
    remains NON_EXECUTABLE until an exact authored spec is forked.
    """

    rows = connection.execute(
        text(
            "SELECT id, card, structured_rules, lesson_source_metadata, pattern_spec, content_hash "
            "FROM user_strategy_versions"
        )
    ).fetchall()
    updated = 0
    for row in rows:
        digest = strategy_version_content_hash(
            card=_as_json_object(row[1]) or {},
            structured_rules=_as_json_object(row[2]),
            lesson_source_metadata=_as_json_object(row[3]),
            pattern_spec=_as_json_object(row[4]),
        )
        if len(digest) != 64:
            raise StrategyVersionImmutabilityError(
                "Canonical strategy version hash must be 64 hex characters.",
                details={"version_id": str(row[0])},
            )
        if row[5] == digest:
            continue
        connection.execute(
            text("UPDATE user_strategy_versions SET content_hash = :digest WHERE id = :id"),
            {"digest": digest, "id": row[0]},
        )
        updated += 1
    remaining = connection.execute(
        text(
            "SELECT COUNT(*) FROM user_strategy_versions "
            "WHERE content_hash IS NULL OR length(content_hash) <> 64"
        )
    ).scalar()
    if int(remaining or 0) != 0:
        raise StrategyVersionImmutabilityError(
            "Strategy version content hash backfill left invalid rows.",
            details={"invalid_count": int(remaining or 0)},
        )
    return updated


def _as_json_object(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else None
    return None


def register_strategy_immutability() -> None:
    """Idempotent listener registration. Called after ORM maps are defined."""

    global _registered
    if _registered:
        return
    from app.db.models import (
        CompiledSetupDefinition,
        ManualLevelRevision,
        StrategyLifecycleEvent,
        UserStrategyVersion,
    )

    event.listen(UserStrategyVersion, "before_insert", _fill_version_hash)
    event.listen(UserStrategyVersion, "before_update", _forbid_semantic_version_update)
    event.listen(UserStrategyVersion, "before_delete", _forbid_version_delete)
    for model in (CompiledSetupDefinition, ManualLevelRevision, StrategyLifecycleEvent):
        event.listen(model, "before_update", _forbid_row_mutation)
        event.listen(model, "before_delete", _forbid_row_delete)
    _registered = True

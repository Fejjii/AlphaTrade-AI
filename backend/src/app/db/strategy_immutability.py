"""ORM listeners for immutable strategy versions, compiled setups, and level revisions."""

from __future__ import annotations

from typing import Any

from sqlalchemy import event, inspect
from sqlalchemy.orm import Mapper

from app.core.errors import ValidationAppError
from app.services.canonical_serialization import canonical_sha256

_SEMANTIC_VERSION_FIELDS = frozenset(
    {
        "card",
        "structured_rules",
        "lesson_source_metadata",
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
) -> str:
    return canonical_sha256(
        {
            "card": card or {},
            "structured_rules": structured_rules,
            "lesson_source_metadata": lesson_source_metadata,
        }
    )


def _fill_version_hash(_mapper: Mapper[Any], _connection: Any, target: Any) -> None:
    if getattr(target, "content_hash", None):
        return
    target.content_hash = strategy_version_content_hash(
        card=getattr(target, "card", None),
        structured_rules=getattr(target, "structured_rules", None),
        lesson_source_metadata=getattr(target, "lesson_source_metadata", None),
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
    for model in (CompiledSetupDefinition, ManualLevelRevision, StrategyLifecycleEvent):
        event.listen(model, "before_update", _forbid_row_mutation)
        event.listen(model, "before_delete", _forbid_row_delete)
    _registered = True

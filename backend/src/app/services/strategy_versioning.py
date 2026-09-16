"""Immutable strategy-version forking and lifecycle append (Phase 3)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ForbiddenError, NotFoundError, ValidationAppError
from app.db.models import (
    CompiledSetupDefinition,
    StrategyLifecycleEvent,
    UserStrategy,
    UserStrategyVersion,
)
from app.db.strategy_immutability import strategy_version_content_hash
from app.repositories.strategy_library import UserStrategyRepository, UserStrategyVersionRepository
from app.schemas.common import StrategyChangeSource, StrategyLifecycleState
from app.schemas.strategy_library import StrategyCard
from app.services.canonical_serialization import canonical_sha256
from app.services.setup_ast_compiler import assert_canonical_alias


class CrossTenantStrategyError(ForbiddenError):
    code = "strategy_cross_tenant_rejected"


def _diff_fields(
    parent: UserStrategyVersion,
    *,
    card: dict[str, Any],
    structured_rules: dict[str, Any] | None,
    lesson_source_metadata: dict[str, Any] | None,
) -> list[str]:
    changed: list[str] = []
    if parent.card != card:
        changed.append("card")
    if parent.structured_rules != structured_rules:
        changed.append("structured_rules")
    if parent.lesson_source_metadata != lesson_source_metadata:
        changed.append("lesson_source_metadata")
    return changed


class StrategyVersioningService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._strategies = UserStrategyRepository(session)
        self._versions = UserStrategyVersionRepository(session)

    def require_strategy(
        self,
        strategy_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> UserStrategy:
        row = self._strategies.get_scoped(
            strategy_id, organization_id=organization_id, user_id=user_id
        )
        if row is None:
            raise NotFoundError("Strategy not found.")
        if row.organization_id != organization_id:
            raise CrossTenantStrategyError("Cross-tenant strategy access rejected.")
        return row

    def selected_version(self, strategy: UserStrategy) -> UserStrategyVersion | None:
        return self._versions.get_version(strategy.id, strategy.current_version)

    def next_version_number(self, strategy_id: uuid.UUID) -> int:
        latest = self._versions.latest(strategy_id)
        return 1 if latest is None else latest.version + 1

    def append_lifecycle(
        self,
        *,
        organization_id: uuid.UUID,
        strategy_id: uuid.UUID,
        strategy_version_id: uuid.UUID,
        new_state: StrategyLifecycleState,
        actor_user_id: uuid.UUID | None,
        reason: str | None,
        evidence_snapshot: dict[str, object] | None = None,
    ) -> StrategyLifecycleEvent:
        prior = self.latest_lifecycle_state(strategy_id)
        occurred = datetime.now(UTC)
        event_id = uuid.uuid4()
        payload = {
            "organization_id": str(organization_id),
            "strategy_id": str(strategy_id),
            "strategy_version_id": str(strategy_version_id),
            "prior_state": prior.value if prior else None,
            "new_state": new_state.value,
            "actor_user_id": str(actor_user_id) if actor_user_id else None,
            "reason": reason,
            "occurred_at": occurred,
            "event_id": str(event_id),
        }
        event = StrategyLifecycleEvent(
            id=event_id,
            organization_id=organization_id,
            strategy_id=strategy_id,
            strategy_version_id=strategy_version_id,
            prior_state=prior,
            new_state=new_state,
            actor_user_id=actor_user_id,
            reason=reason,
            evidence_snapshot=evidence_snapshot or {},
            occurred_at=occurred,
            event_hash=canonical_sha256(payload),
        )
        self._session.add(event)
        self._session.flush()
        return event

    def latest_lifecycle_state(self, strategy_id: uuid.UUID) -> StrategyLifecycleState | None:
        stmt = (
            select(StrategyLifecycleEvent)
            .where(StrategyLifecycleEvent.strategy_id == strategy_id)
            .order_by(StrategyLifecycleEvent.occurred_at.desc())
            .limit(1)
        )
        row = self._session.scalar(stmt)
        return row.new_state if row else None

    def fork_semantic_update(
        self,
        strategy: UserStrategy,
        *,
        parent: UserStrategyVersion,
        card: dict[str, Any],
        structured_rules: dict[str, Any] | None,
        lesson_source_metadata: dict[str, Any] | None,
        actor_user_id: uuid.UUID | None,
        source: StrategyChangeSource,
        reason: str | None,
        validation_status: Any | None = None,
    ) -> UserStrategyVersion:
        changed = _diff_fields(
            parent,
            card=card,
            structured_rules=structured_rules,
            lesson_source_metadata=lesson_source_metadata,
        )
        if not changed:
            return parent
        next_version = self.next_version_number(strategy.id)
        content_hash = strategy_version_content_hash(
            card=card,
            structured_rules=structured_rules,
            lesson_source_metadata=lesson_source_metadata,
        )
        version = UserStrategyVersion(
            strategy_id=strategy.id,
            version=next_version,
            card=card,
            validation_status=validation_status or parent.validation_status,
            backtest_status=parent.backtest_status,
            paper_validation_status=parent.paper_validation_status,
            structured_rules=structured_rules,
            lesson_source_metadata=lesson_source_metadata,
            parent_version_id=parent.id,
            actor_user_id=actor_user_id,
            change_reason=reason,
            change_source=source,
            content_diff={
                "parent_version_id": str(parent.id),
                "parent_content_hash": parent.content_hash,
                "fields_changed": changed,
                "source": source.value,
                "reason": reason,
            },
            content_hash=content_hash,
        )
        self._versions.add(version)
        strategy.current_version = next_version
        lifecycle_state = (
            StrategyLifecycleState.STRUCTURED if structured_rules else StrategyLifecycleState.DRAFT
        )
        self.append_lifecycle(
            organization_id=strategy.organization_id,
            strategy_id=strategy.id,
            strategy_version_id=version.id,
            new_state=lifecycle_state,
            actor_user_id=actor_user_id,
            reason=reason or source.value,
            evidence_snapshot={"fields_changed": changed},
        )
        return version

    def compiled_for_version(
        self,
        strategy_version_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
    ) -> CompiledSetupDefinition | None:
        stmt = select(CompiledSetupDefinition).where(
            CompiledSetupDefinition.strategy_version_id == strategy_version_id,
            CompiledSetupDefinition.organization_id == organization_id,
        )
        return self._session.scalar(stmt)

    def persist_compiled(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        strategy_id: uuid.UUID,
        strategy_version_id: uuid.UUID,
        compiler_version: str,
        grammar_version: str,
        compiled_ast: dict[str, Any],
        content_hash: str,
    ) -> CompiledSetupDefinition:
        existing = self.compiled_for_version(strategy_version_id, organization_id=organization_id)
        if existing is not None:
            if existing.content_hash != content_hash:
                raise ValidationAppError(
                    "Compiled setup already exists with a different content hash."
                )
            return existing
        row = CompiledSetupDefinition(
            organization_id=organization_id,
            user_id=user_id,
            strategy_id=strategy_id,
            strategy_version_id=strategy_version_id,
            compiler_version=compiler_version,
            grammar_version=grammar_version,
            compiled_ast=compiled_ast,
            content_hash=content_hash,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def assert_tenant_version(
        self,
        version: UserStrategyVersion,
        *,
        organization_id: uuid.UUID,
        alias: str | None = None,
    ) -> UserStrategy:
        strategy = self._session.get(UserStrategy, version.strategy_id)
        if strategy is None or strategy.organization_id != organization_id:
            raise CrossTenantStrategyError("Cross-tenant strategy access rejected.")
        card = StrategyCard.model_validate(version.card)
        assert_canonical_alias(
            strategy_version_id=version.id,
            alias=alias,
            strategy_name=card.strategy_name,
        )
        return strategy

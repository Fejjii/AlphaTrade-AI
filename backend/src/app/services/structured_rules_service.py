"""Structured rules persistence and validation (Slice 36)."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationAppError
from app.db.models import UserStrategy as UserStrategyModel
from app.repositories.strategy_library import UserStrategyRepository, UserStrategyVersionRepository
from app.schemas.common import StrategyChangeSource
from app.schemas.structured_rules import (
    StructuredRules,
    StructuredRulesPatch,
    StructuredRulesValidation,
)
from app.services.strategy_testability_service import StrategyTestabilityService
from app.services.strategy_versioning import StrategyVersioningService


class StructuredRulesService:
    def __init__(self, session: Session) -> None:
        self._strategies = UserStrategyRepository(session)
        self._versions = UserStrategyVersionRepository(session)
        self._testability = StrategyTestabilityService(session)
        self._versioning = StrategyVersioningService(session)

    def get(
        self,
        strategy_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> StructuredRules | None:
        self._require(strategy_id, organization_id=organization_id, user_id=user_id)
        row = self._strategies.get_scoped(
            strategy_id, organization_id=organization_id, user_id=user_id
        )
        version = self._versioning.selected_version(row) if row else None
        if version is None or not version.structured_rules:
            return None
        return StructuredRules.model_validate(version.structured_rules)

    def patch(
        self,
        strategy_id: uuid.UUID,
        payload: StructuredRulesPatch,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> StructuredRules:
        row = self._require(strategy_id, organization_id=organization_id, user_id=user_id)
        version = self._versioning.selected_version(row)
        if version is None:
            raise NotFoundError("Strategy version not found.")
        current_data: dict[str, object] = {}
        if version.structured_rules:
            current_data = dict(version.structured_rules)
        updates = payload.model_dump(exclude_unset=True)
        current_data.update(updates)
        merged = StructuredRules.model_validate(current_data)
        valid, errors, _ = self._testability.validate_structured(merged)
        if not valid:
            raise ValidationAppError("; ".join(errors))
        self._versioning.fork_semantic_update(
            row,
            parent=version,
            card=dict(version.card),
            structured_rules=merged.model_dump(mode="json"),
            lesson_source_metadata=version.lesson_source_metadata,
            actor_user_id=user_id,
            source=StrategyChangeSource.STRUCTURED_RULES,
            reason="structured_rules_patch",
        )
        return merged

    def validate(self, rules: StructuredRules) -> StructuredRulesValidation:
        valid, errors, warnings = self._testability.validate_structured(rules)
        return StructuredRulesValidation(valid=valid, errors=errors, warnings=warnings)

    def _require(
        self,
        strategy_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> UserStrategyModel:
        row = self._strategies.get_scoped(
            strategy_id, organization_id=organization_id, user_id=user_id
        )
        if row is None:
            raise NotFoundError("Strategy not found.")
        return row

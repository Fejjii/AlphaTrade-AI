"""Structured rules persistence and validation (Slice 36)."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationAppError
from app.repositories.strategy_library import UserStrategyRepository, UserStrategyVersionRepository
from app.schemas.structured_rules import (
    StructuredRules,
    StructuredRulesPatch,
    StructuredRulesValidation,
)
from app.services.strategy_testability_service import StrategyTestabilityService


class StructuredRulesService:
    def __init__(self, session: Session) -> None:
        self._strategies = UserStrategyRepository(session)
        self._versions = UserStrategyVersionRepository(session)
        self._testability = StrategyTestabilityService(session)

    def get(
        self,
        strategy_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> StructuredRules | None:
        self._require(strategy_id, organization_id=organization_id, user_id=user_id)
        version = self._versions.latest(strategy_id)
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
        version = self._versions.latest(row.id)
        if version is None:
            raise NotFoundError("Strategy version not found.")
        current_data: dict = {}
        if version.structured_rules:
            current_data = dict(version.structured_rules)
        updates = payload.model_dump(exclude_unset=True)
        current_data.update(updates)
        merged = StructuredRules.model_validate(current_data)
        valid, errors, _ = self._testability.validate_structured(merged)
        if not valid:
            raise ValidationAppError("; ".join(errors))
        version.structured_rules = merged.model_dump(mode="json")
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
    ):
        row = self._strategies.get_scoped(
            strategy_id, organization_id=organization_id, user_id=user_id
        )
        if row is None:
            raise NotFoundError("Strategy not found.")
        return row

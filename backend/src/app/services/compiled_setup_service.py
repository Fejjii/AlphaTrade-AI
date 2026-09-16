"""Compile tenant strategy versions into immutable CompiledSetupDefinition rows."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.db.models import UserStrategyVersion
from app.schemas.common import SetupCompileStatus
from app.schemas.strategy_library import StrategyCard
from app.schemas.strategy_lifecycle import CompiledSetupDefinitionRecord, CompileOutcome
from app.schemas.structured_rules import StructuredRules
from app.services.setup_ast_compiler import compile_from_authored, compile_pattern
from app.services.strategy_versioning import StrategyVersioningService


class CompiledSetupService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._versions = StrategyVersioningService(session)

    def compile_version(
        self,
        strategy_version_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        alias: str | None = None,
        persist: bool = True,
    ) -> CompileOutcome:
        version = self._session.get(UserStrategyVersion, strategy_version_id)
        if version is None:
            raise NotFoundError("Strategy version not found.")
        strategy = self._versions.assert_tenant_version(
            version, organization_id=organization_id, alias=alias
        )
        if strategy.user_id != user_id:
            raise NotFoundError("Strategy version not found.")
        card = StrategyCard.model_validate(version.card)
        rules = (
            StructuredRules.model_validate(version.structured_rules)
            if version.structured_rules
            else None
        )
        result = compile_from_authored(
            card=card,
            rules=rules,
            strategy_version_id=version.id,
            organization_id=organization_id,
            alias=alias,
        )
        if result.document is None:
            return CompileOutcome(
                status=SetupCompileStatus.NON_EXECUTABLE,
                failures=result.failures,
            )
        compiled_row = None
        if persist:
            compiled_row = self._versions.persist_compiled(
                organization_id=organization_id,
                user_id=user_id,
                strategy_id=strategy.id,
                strategy_version_id=version.id,
                compiler_version=result.document.compiler_version,
                grammar_version=result.document.grammar_version,
                compiled_ast=result.document.pattern.model_dump(mode="json"),
                content_hash=result.document.content_hash,
            )
        return CompileOutcome(
            status=SetupCompileStatus.EXECUTABLE,
            compiled=(
                CompiledSetupDefinitionRecord.model_validate(compiled_row, from_attributes=True)
                if compiled_row is not None
                else None
            ),
            document=result.document,
            features=result.document.pattern.features,
        )

    def golden_first_slice(self) -> CompileOutcome:
        from app.services.setup_ast_compiler import first_slice_bearish_sweep_pattern

        result = compile_pattern(first_slice_bearish_sweep_pattern())
        return CompileOutcome(
            status=SetupCompileStatus.EXECUTABLE
            if result.document is not None
            else SetupCompileStatus.NON_EXECUTABLE,
            document=result.document,
            failures=result.failures,
            features=result.document.pattern.features if result.document else [],
        )

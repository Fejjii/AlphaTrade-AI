"""Phase 3 strategy lifecycle, compiled setup, revisions, and migration contracts."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.schemas.common import (
    NonNegativeDecimal,
    ORMModel,
    SetupCompileStatus,
    SetupMigrationMode,
    StrategyChangeSource,
    StrategyLifecycleState,
    StrictModel,
)
from app.schemas.setup_ast import CompiledAstDocument, CompileFailure, FeatureRef


class StrategyContentDiff(StrictModel):
    parent_version_id: UUID | None = None
    parent_content_hash: str | None = None
    fields_changed: list[str] = Field(default_factory=list)
    source: StrategyChangeSource
    reason: str | None = None


class StrategyLifecycleEventRecord(ORMModel):
    id: UUID
    organization_id: UUID
    strategy_id: UUID
    strategy_version_id: UUID
    prior_state: StrategyLifecycleState | None = None
    new_state: StrategyLifecycleState
    actor_user_id: UUID | None = None
    reason: str | None = None
    evidence_snapshot: dict[str, object] = Field(default_factory=dict)
    occurred_at: datetime
    event_hash: str
    created_at: datetime


class CompiledSetupDefinitionRecord(ORMModel):
    id: UUID
    organization_id: UUID
    user_id: UUID
    strategy_id: UUID
    strategy_version_id: UUID
    compiler_version: str
    grammar_version: str
    compiled_ast: dict[str, object]
    content_hash: str
    compile_status: SetupCompileStatus
    created_at: datetime


class GlobalSetupTemplateRecord(ORMModel):
    id: UUID
    setup_definition_id: UUID
    name: str
    version: int
    strategy_id: str
    is_global: bool = True
    organization_id: None = None
    created_at: datetime


class ManualLevelRevisionRecord(ORMModel):
    id: UUID
    level_id: UUID
    revision_number: int
    organization_id: UUID
    user_id: UUID
    instrument: str
    exchange: str
    timeframe: str | None = None
    level_type: str
    value: NonNegativeDecimal | None = None
    price_low: Decimal | None = None
    price_high: Decimal | None = None
    valid: bool = True
    actor_user_id: UUID | None = None
    venue: str
    market_type: str
    price_unit: str
    content_hash: str
    supersedes_revision_id: UUID | None = None
    created_at: datetime
    effective_at: datetime


class SetupMigrationRow(StrictModel):
    kind: str
    source_id: UUID
    target_id: UUID | None = None
    disposition: str
    detail: str | None = None


class SetupMigrationReport(StrictModel):
    mode: SetupMigrationMode
    templates_created: int = 0
    templates_skipped: int = 0
    compiled_created: int = 0
    compiled_skipped: int = 0
    non_executable: int = 0
    collisions: int = 0
    rows: list[SetupMigrationRow] = Field(default_factory=list)
    run_id: UUID | None = None


class CompileRequest(StrictModel):
    organization_id: UUID
    user_id: UUID
    strategy_version_id: UUID
    alias: str | None = None


class CompileOutcome(StrictModel):
    status: SetupCompileStatus
    compiled: CompiledSetupDefinitionRecord | None = None
    document: CompiledAstDocument | None = None
    failures: list[CompileFailure] = Field(default_factory=list)
    features: list[FeatureRef] = Field(default_factory=list)


class StrategyVersionApproveRequest(StrictModel):
    """Explicit approval of an already compiled version. Not conversational confirm."""

    confirm: str = Field(min_length=1, max_length=200)

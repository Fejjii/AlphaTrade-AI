"""Governed learning contracts on existing proposal and lifecycle storage."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.schemas.common import StrictModel
from app.schemas.strategy_library import StrategyCard
from app.schemas.structured_rules import StructuredRules

GOVERNED_LEARNING = "governed_learning_001"


class LearningEvidenceRef(StrictModel):
    kind: Literal[
        "conversation_message",
        "journal_trade",
        "journal_observation",
        "document",
        "backtest_run",
        "paper_validation_run",
    ]
    id: UUID


class GovernedProposalCreate(StrictModel):
    conversation_id: UUID
    base_version_id: UUID
    source_observations: list[LearningEvidenceRef] = Field(min_length=1, max_length=20)
    hypothesis: str = Field(min_length=1, max_length=4000)
    reason: str = Field(min_length=1, max_length=4000)
    evidence_ids: list[LearningEvidenceRef] = Field(default_factory=list, max_length=40)
    sample_limitations: list[str] = Field(default_factory=list, max_length=20)
    validation_plan: str = Field(min_length=1, max_length=4000)
    card: StrategyCard
    structured_rules: StructuredRules | None = None
    pattern_spec: dict[str, object] | None = None
    review_day: date | None = None
    review_timezone: str = "UTC"


class LearningIdentity(StrictModel):
    expected_content_hash: str = Field(min_length=64, max_length=64)


class LearningValidationEvidence(LearningIdentity):
    baseline_run_id: UUID
    proposed_run_id: UUID
    paper_validation_run_id: UUID | None = None


class LearningPromotionApproval(LearningIdentity):
    confirm: Literal["APPROVE_PAPER_PROMOTION"]
    expected_version_id: UUID
    expected_comparison_hash: str = Field(min_length=64, max_length=64)
    expected_paper_validation_run_id: UUID
    evidence_review: str | None = Field(default=None, min_length=10, max_length=4000)
    execution_mode: Literal["paper"] = "paper"


class LearningRollbackApproval(StrictModel):
    confirm: Literal["ROLLBACK_PAPER_STRATEGY"]
    expected_active_version_id: UUID
    target_version_id: UUID
    reason: str = Field(min_length=1, max_length=4000)
    execution_mode: Literal["paper"] = "paper"


class GovernedLearningStatus(StrictModel):
    proposal_id: UUID
    strategy_id: UUID
    base_version_id: UUID
    proposed_version_id: UUID | None
    content_hash: str
    source_observations: list[LearningEvidenceRef]
    hypothesis: str
    reason: str
    proposed_parameters: dict[str, object]
    evidence_ids: list[LearningEvidenceRef]
    sample_limitations: list[str]
    validation_plan: str
    created_by: UUID
    created_at: datetime
    approval_state: Literal[
        "proposed", "validating", "approved", "rolled_back", "rejected", "superseded"
    ]
    replayed: bool = False
    comparison_hash: str | None = None
    baseline_run_id: UUID | None = None
    proposed_run_id: UUID | None = None
    observed_net_pnl_delta: Decimal | None = None
    outperformed_baseline: bool | None = None
    improvement_claim: Literal[False] = False
    paper_validation_run_id: UUID | None = None
    paper_validation_completed: bool = False
    insufficient_evidence: bool = True
    explicit_evidence_review_required: bool = True
    blockers: list[str] = Field(default_factory=list)
    paper_active_version_id: UUID | None = None
    rollback_version_id: UUID | None = None
    can_roll_back: bool = False
    live_execution_permitted: Literal[False] = False


class GovernedLearningList(StrictModel):
    items: list[GovernedLearningStatus]
    limit: int
    offset: int

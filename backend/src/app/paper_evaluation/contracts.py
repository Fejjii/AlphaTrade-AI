"""Immutable contracts for continuous paper evaluation measurement.

Facts are copied from Watcher outcomes, SetupAssessment, Candidate,
ActionEligibility, paper decisions, JournalTrade, and learning attribution.
This package does not evaluate setups, mint Candidates, authorize plans,
dispatch execution, or activate strategy refinements.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field

from app.learning_attribution.contracts import (
    ExecutionQuality,
    LearningVenueMode,
    PlannedSetupQuality,
    RiskAdherence,
    TraderBehavior,
)
from app.market_contracts.models import CanonicalDecimal, CanonicalModel
from app.schemas.common import TradeResult
from app.schemas.journal_statistics import SampleConfidence, TradeRuleCompliance
from app.signal_fusion.enums import ActionEligibilityState, SetupAssessmentState
from app.signal_fusion.types import Sha256Hex

PAPER_EVALUATION_SCHEMA: Literal["PaperEvaluation/v1"] = "PaperEvaluation/v1"
NARRATIVE_NOT_FACT_BANNER: Literal[
    "NARRATIVE_NOT_FACT — LLM wording cannot rewrite deterministic facts"
] = "NARRATIVE_NOT_FACT — LLM wording cannot rewrite deterministic facts"
REFINEMENT_NOT_ACTIVATED: Literal[
    "suggestion_only — evaluation cannot activate a strategy refinement"
] = "suggestion_only — evaluation cannot activate a strategy refinement"


class PaperEvaluationStage(StrEnum):
    """Funnel stage copied from an existing authority. Not a new lifecycle."""

    WATCHER_SCAN = "watcher_scan"
    SETUP_ASSESSMENT = "setup_assessment"
    CANDIDATE = "candidate"
    ELIGIBILITY = "eligibility"
    PAPER_DECISION = "paper_decision"
    PAPER_TRADE = "paper_trade"
    OUTCOME = "outcome"
    JOURNAL = "journal"
    ATTRIBUTION = "attribution"


class DataQualityClass(StrEnum):
    """Evidence/data-quality class at observation time. Fail-closed classes stay visible."""

    FRESH = "fresh"
    STALE = "stale"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    REPLAY = "replay"
    UNKNOWN = "unknown"


class FalseSignalClass(StrEnum):
    """Confirmed-setup outcome quality. INVALIDATED is not a trade result."""

    NOT_APPLICABLE = "not_applicable"
    CONFIRMED_WIN = "confirmed_win"
    CONFIRMED_LOSS = "confirmed_loss"
    CONFIRMED_BREAKEVEN = "confirmed_breakeven"
    CONFIRMED_INVALIDATED = "confirmed_invalidated"
    CONFIRMED_EXPIRED = "confirmed_expired"


class MissedOpportunityClass(StrEnum):
    """Operator/system miss after confirmation. Counterfactual PnL is never invented."""

    NOT_APPLICABLE = "not_applicable"
    REJECTED_CONFIRMED = "rejected_confirmed"
    SKIPPED_CONFIRMED = "skipped_confirmed"
    ELIGIBLE_NOT_APPROVED = "eligible_not_approved"
    BLOCKED_AFTER_CONFIRMATION = "blocked_after_confirmation"


class PaperEvaluationObservation(CanonicalModel):
    """One append-only measurement fact. Narrative is excluded from content_hash."""

    schema_version: Literal["PaperEvaluation/v1"] = PAPER_EVALUATION_SCHEMA
    observation_id: UUID
    organization_id: UUID
    stage: PaperEvaluationStage
    source_system: str = Field(min_length=1, max_length=80)
    source_event_id: str = Field(min_length=1, max_length=160)
    source_event_version: int = Field(ge=1)
    occurred_at: AwareDatetime
    strategy_version_id: UUID | None = None
    setup_definition_id: UUID | None = None
    candidate_id: UUID | None = None
    assessment_id: UUID | None = None
    journal_trade_id: UUID | None = None
    scan_status: str | None = Field(default=None, max_length=64)
    reason_code: str | None = Field(default=None, max_length=128)
    assessment_state: SetupAssessmentState | None = None
    eligibility_state: ActionEligibilityState | None = None
    data_quality: DataQualityClass = DataQualityClass.UNKNOWN
    replayed: bool = False
    plan_approved: bool = False
    rejected: bool = False
    skipped: bool = False
    filled: bool = False
    closed: bool = False
    executed_outcome: bool = False
    result: TradeResult | None = None
    net_pnl: CanonicalDecimal | None = None
    mfe_amount: CanonicalDecimal | None = None
    mae_amount: CanonicalDecimal | None = None
    capture_pct: CanonicalDecimal | None = None
    planned_risk_amount: CanonicalDecimal | None = None
    setup_quality: PlannedSetupQuality | None = None
    execution_quality: ExecutionQuality | None = None
    risk_adherence: RiskAdherence | None = None
    trader_behavior: TraderBehavior | None = None
    rule_compliance: TradeRuleCompliance | None = None
    learning_venue_mode: LearningVenueMode = LearningVenueMode.PAPER_INTERNAL
    live_executable: Literal[False] = False
    content_hash: Sha256Hex
    narrative_explanation: str | None = Field(default=None, max_length=4000)


class WatcherPerformanceFacts(CanonicalModel):
    scan_count: int = 0
    succeeded_count: int = 0
    failed_count: int = 0
    blocked_count: int = 0
    skipped_count: int = 0
    replay_count: int = 0
    stale_evidence_count: int = 0
    provider_outage_count: int = 0
    confirmed_setup_count: int = 0
    watch_count: int = 0
    no_setup_count: int = 0
    partial_match_count: int = 0
    invalidated_count: int = 0
    expired_count: int = 0
    candidates_published: int = 0


class SetupConversionFacts(CanonicalModel):
    scans: int = 0
    assessments: int = 0
    confirmed_setups: int = 0
    candidates: int = 0
    eligible: int = 0
    blocked: int = 0
    paper_decisions: int = 0
    approved: int = 0
    rejected: int = 0
    skipped: int = 0
    filled: int = 0
    closed: int = 0
    scan_to_confirmed_rate: CanonicalDecimal | None = None
    confirmed_to_candidate_rate: CanonicalDecimal | None = None
    candidate_to_eligible_rate: CanonicalDecimal | None = None
    eligible_to_approved_rate: CanonicalDecimal | None = None
    approved_to_fill_rate: CanonicalDecimal | None = None
    fill_to_close_rate: CanonicalDecimal | None = None


class FalseSignalFacts(CanonicalModel):
    confirmed_setups: int = 0
    executed_outcomes: int = 0
    confirmed_wins: int = 0
    confirmed_losses: int = 0
    confirmed_breakeven: int = 0
    confirmed_invalidated_before_fill: int = 0
    false_signal_rate: CanonicalDecimal | None = None


class StrategyPerformanceFacts(CanonicalModel):
    strategy_version_id: UUID | None = None
    setup_definition_id: UUID | None = None
    sample_candidates: int = 0
    executed_outcome_count: int = 0
    win_count: int = 0
    loss_count: int = 0
    breakeven_count: int = 0
    win_rate: CanonicalDecimal | None = None
    expectancy: CanonicalDecimal | None = None
    net_pnl_total: CanonicalDecimal | None = None
    max_drawdown: CanonicalDecimal | None = None
    mfe_sample_count: int = 0
    average_mfe: CanonicalDecimal | None = None
    mae_sample_count: int = 0
    average_mae: CanonicalDecimal | None = None
    capture_sample_count: int = 0
    average_capture_pct: CanonicalDecimal | None = None
    confidence: SampleConfidence = SampleConfidence.INSUFFICIENT


class RuleAdherenceFacts(CanonicalModel):
    assessed_count: int = 0
    risk_adhered_count: int = 0
    stop_violation_count: int = 0
    size_or_risk_violation_count: int = 0
    journal_compliant_count: int = 0
    journal_partial_count: int = 0
    journal_violated_count: int = 0
    journal_unassessed_count: int = 0
    adherence_rate: CanonicalDecimal | None = None


class BlockedTradeFacts(CanonicalModel):
    blocked_count: int = 0
    by_reason: tuple[tuple[str, int], ...] = ()


class HumanVsSystemEvaluationFacts(CanonicalModel):
    human_reject_or_skip: int = 0
    human_approvals: int = 0
    paper_system_executions: int = 0
    executed_outcomes: int = 0
    setup_confirmed_count: int = 0
    human_approved_executed_wins: int = 0
    human_approved_executed_losses: int = 0
    system_scan_confirmed: int = 0


class MissedOpportunityFacts(CanonicalModel):
    rejected_confirmed: int = 0
    skipped_confirmed: int = 0
    eligible_not_approved: int = 0
    blocked_after_confirmation: int = 0
    counterfactual_pnl: Literal[None] = None
    warning: str = (
        "Missed-opportunity counts are funnel misses only. Counterfactual PnL is not invented."
    )


class DataQualityFacts(CanonicalModel):
    fresh_count: int = 0
    stale_count: int = 0
    degraded_count: int = 0
    unavailable_count: int = 0
    replay_count: int = 0
    unknown_count: int = 0
    stale_or_unavailable_rate: CanonicalDecimal | None = None


class PaperEvaluationWarning(CanonicalModel):
    code: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=400)


class PaperEvaluationFacts(CanonicalModel):
    """Deterministic measurement snapshot. Narrative is excluded from content_hash."""

    schema_version: Literal["PaperEvaluation/v1"] = PAPER_EVALUATION_SCHEMA
    organization_id: UUID
    learning_venue_mode: LearningVenueMode | None = None
    watcher_orchestration_enabled: Literal[False] = False
    telegram_interaction_enabled: Literal[False] = False
    live_executable: Literal[False] = False
    generated_at: AwareDatetime
    watcher: WatcherPerformanceFacts
    conversion: SetupConversionFacts
    false_signals: FalseSignalFacts
    strategy_overall: StrategyPerformanceFacts
    strategy_versions: tuple[StrategyPerformanceFacts, ...] = ()
    rule_adherence: RuleAdherenceFacts
    blocked: BlockedTradeFacts
    human_vs_system: HumanVsSystemEvaluationFacts
    missed_opportunities: MissedOpportunityFacts
    data_quality: DataQualityFacts
    warnings: tuple[PaperEvaluationWarning, ...] = ()
    content_hash: Sha256Hex


class RefinementSuggestion(CanonicalModel):
    """Suggestion only. Evaluation cannot compile, approve, or activate a version."""

    suggestion_id: UUID
    organization_id: UUID
    category: str = Field(min_length=1, max_length=80)
    summary: str = Field(min_length=1, max_length=2000)
    strategy_version_id: UUID | None = None
    evidence_facts_hash: Sha256Hex
    severity: str = Field(min_length=1, max_length=16)
    activate: Literal[False] = False
    auto_activate: Literal[False] = False
    banner: Literal["suggestion_only — evaluation cannot activate a strategy refinement"] = (
        REFINEMENT_NOT_ACTIVATED
    )
    narrative_explanation: str | None = Field(default=None, max_length=4000)


class PaperEvaluationNarrative(CanonicalModel):
    banner: Literal["NARRATIVE_NOT_FACT — LLM wording cannot rewrite deterministic facts"] = (
        NARRATIVE_NOT_FACT_BANNER
    )
    text: str = Field(min_length=1, max_length=4000)


class PaperEvaluationSummary(CanonicalModel):
    """Operator-visible evaluation snapshot. Facts and narrative are siblings."""

    schema_version: Literal["PaperEvaluation/v1"] = PAPER_EVALUATION_SCHEMA
    summary_id: UUID
    organization_id: UUID
    authority: Literal["paper_evaluation_measurement"] = "paper_evaluation_measurement"
    live_executable: Literal[False] = False
    facts: PaperEvaluationFacts
    refinements: tuple[RefinementSuggestion, ...] = ()
    narrative: PaperEvaluationNarrative | None = None

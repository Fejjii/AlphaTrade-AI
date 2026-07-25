"""Research Validation Loop schemas (AT-035 — advisory promotion into paper queue)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.schemas.backtest import SetupEvidenceTier
from app.schemas.common import BacktestRunStatus, StrictModel
from app.schemas.paper_validation_candidate import PaperValidationCandidateItem

PROMOTE_RESEARCH_VALIDATION_CANDIDATE_CONFIRM = "PROMOTE_RESEARCH_VALIDATION_CANDIDATE"

ADVISORY_NOTE = "Advisory only — never feeds execution or risk decisions."


class ResearchValidationEvidenceItem(StrictModel):
    backtest_run_id: UUID
    strategy_id: UUID
    strategy_version_id: UUID | None = None
    strategy_name: str
    version: int
    symbol: str | None = None
    timeframe: str | None = None
    regime: str | None = None
    status: BacktestRunStatus
    dataset_hash: str | None = None
    config_hash: str | None = None
    result_hash: str | None = None
    evidence_tier: SetupEvidenceTier
    sample_size: int = 0
    oos_trade_count: int = 0
    oos_expectancy: Decimal | None = None
    oos_profit_factor: float | None = None
    confirm_trade_count: int = 0
    eligible_for_promotion: bool = False
    warnings: list[str] = Field(default_factory=list)
    existing_candidate_id: UUID | None = None
    existing_run_plan_id: UUID | None = None
    promotion_blocked_reason: str | None = None


class ResearchValidationEvidenceResponse(StrictModel):
    items: list[ResearchValidationEvidenceItem]
    generated_at: datetime
    note: str = ADVISORY_NOTE


class ResearchValidationPromoteRequest(StrictModel):
    confirm: str
    backtest_run_id: UUID


class ResearchValidationEligibility(StrictModel):
    eligible: bool
    tier: SetupEvidenceTier | None = None
    warnings: list[str] = Field(default_factory=list)
    blocked_reason: str | None = None


class ResearchValidationLinks(StrictModel):
    candidate_id: UUID | None = None
    draft_id: UUID | None = None
    source_alert_id: UUID | None = None
    run_plan_id: UUID | None = None
    backtest_run_id: UUID
    strategy_id: UUID | None = None
    strategy_version_id: UUID | None = None
    journal_comparison_path: str | None = None
    setup_evidence_path: str | None = None
    journal_statistics_path: str | None = None


class ResearchValidationPromoteResult(StrictModel):
    candidate: PaperValidationCandidateItem
    already_exists: bool = False
    eligibility: ResearchValidationEligibility
    links: ResearchValidationLinks


class ResearchValidationStatusResponse(StrictModel):
    evidence: ResearchValidationEvidenceItem
    links: ResearchValidationLinks
    generated_at: datetime
    note: str = ADVISORY_NOTE

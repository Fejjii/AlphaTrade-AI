"""Bounded conversational paper intents and canonical result identities."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.common import Timeframe, TradeDirection
from app.schemas.risk import RiskCheckResult
from app.schemas.trade_plan import (
    CanonicalModel,
    MarketType,
    PositiveCanonicalDecimal,
    TradePlanRevision,
)


class AgentPaperTradeIntent(CanonicalModel):
    mode: Literal["paper"] = "paper"
    candidate_id: UUID
    account_id: UUID
    symbol: str = Field(min_length=2, max_length=30)
    venue: str = Field(min_length=1, max_length=40)
    market: MarketType
    timeframe: Timeframe
    direction: TradeDirection
    entry: PositiveCanonicalDecimal
    stop: PositiveCanonicalDecimal
    targets: tuple[PositiveCanonicalDecimal, ...] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def validate_levels(self) -> AgentPaperTradeIntent:
        long = self.direction is TradeDirection.LONG
        if (long and self.stop >= self.entry) or (not long and self.stop <= self.entry):
            raise ValueError("Stop must be beyond entry on the loss side.")
        previous = self.entry
        for target in self.targets:
            if (long and target <= previous) or (not long and target >= previous):
                raise ValueError("Targets must progress from entry on the profit side.")
            previous = target
        return self


class AgentPaperConfirmation(CanonicalModel):
    revision_id: UUID
    plan_content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class PaperPreTradeAnalysis(CanonicalModel):
    entry: PositiveCanonicalDecimal
    stop: PositiveCanonicalDecimal
    targets: tuple[PositiveCanonicalDecimal, ...]
    risk_reward_ratios: tuple[PositiveCanonicalDecimal, ...]


class AgentPaperResult(CanonicalModel):
    stage: Literal["proposed", "executed", "blocked"]
    candidate_id: UUID
    eligibility_id: UUID
    plan: TradePlanRevision
    approval_id: UUID
    confirmation_message: str
    risk_result: RiskCheckResult
    pretrade: PaperPreTradeAnalysis
    authorization_id: UUID | None = None
    paper_action_id: UUID | None = None
    receipt_id: UUID | None = None
    journal_trade_id: UUID | None = None
    replayed: bool = False
    reason_code: str | None = None

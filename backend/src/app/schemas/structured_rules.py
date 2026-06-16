"""Structured rule blocks for machine-testable strategies (Slice 36)."""

from __future__ import annotations

from decimal import Decimal

from pydantic import Field, model_validator

from app.schemas.common import (
    EntryTriggerType,
    ExitRuleType,
    NoTradeRuleType,
    RuleConditionOperator,
    StrictModel,
    Timeframe,
    TradeDirection,
)


class RuleCondition(StrictModel):
    """Single condition within a rule block."""

    timeframe: Timeframe | None = None
    indicator: str | None = Field(default=None, max_length=60)
    operator: RuleConditionOperator | None = None
    value: Decimal | str | None = None
    lookback_candles: int | None = Field(default=None, ge=1, le=500)
    confirmation_required: bool = False


class EntryRuleBlock(StrictModel):
    """Structured entry trigger."""

    trigger_type: EntryTriggerType
    direction: TradeDirection = TradeDirection.LONG
    conditions: list[RuleCondition] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=500)


class ExitRuleBlock(StrictModel):
    """Structured exit rule."""

    rule_type: ExitRuleType
    value: Decimal | None = None
    r_multiple: Decimal | None = Field(default=None, gt=0)
    size_fraction: float | None = Field(default=None, gt=0, le=1)
    conditions: list[RuleCondition] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=500)


class NoTradeRuleBlock(StrictModel):
    """Structured no-trade filter."""

    rule_type: NoTradeRuleType
    threshold: Decimal | None = None
    conditions: list[RuleCondition] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=500)


class StructuredRules(StrictModel):
    """Machine-testable rule bundle attached to a strategy version."""

    primary_timeframe: Timeframe | None = None
    entry_rules: list[EntryRuleBlock] = Field(default_factory=list)
    exit_rules: list[ExitRuleBlock] = Field(default_factory=list)
    no_trade_rules: list[NoTradeRuleBlock] = Field(default_factory=list)

    @model_validator(mode="after")
    def _require_entry(self) -> StructuredRules:
        if not self.entry_rules:
            raise ValueError("At least one entry rule is required.")
        return self


class StructuredRulesPatch(StrictModel):
    """Partial update for structured rules."""

    primary_timeframe: Timeframe | None = None
    entry_rules: list[EntryRuleBlock] | None = None
    exit_rules: list[ExitRuleBlock] | None = None
    no_trade_rules: list[NoTradeRuleBlock] | None = None


class StructuredRulesValidation(StrictModel):
    """Validation result for structured rules."""

    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StructureFromTextRequest(StrictModel):
    """Request to draft structured rules from plain English (LLM-assisted)."""

    text: str = Field(min_length=10, max_length=8000)
    setup_hint: str | None = Field(default=None, max_length=120)


class StructureFromTextResponse(StrictModel):
    """Draft structured rules — requires deterministic validation before backtest."""

    draft: StructuredRules | None = None
    validation: StructuredRulesValidation
    source: str = "keyword_draft"
    limitations: list[str] = Field(default_factory=list)

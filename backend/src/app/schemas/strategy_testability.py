"""Strategy testability scoring schemas (Slice 36)."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from app.schemas.common import StrictModel, TestabilityBand
from app.schemas.structured_rules import StructuredRules


class MissingRuleField(StrictModel):
    """A missing or vague field blocking full testability."""

    field_key: str
    label: str
    severity: str = "required"


class StrategyTestability(StrictModel):
    """Whether a strategy can be backtested mechanically."""

    strategy_id: UUID
    score: int = Field(ge=0, le=100)
    band: TestabilityBand
    ready_for_backtest: bool
    missing_fields: list[MissingRuleField] = Field(default_factory=list)
    unsupported_rule_types: list[str] = Field(default_factory=list)
    ambiguous_conditions: list[str] = Field(default_factory=list)
    not_backtestable_reason: str | None = None
    suggested_edits: list[str] = Field(default_factory=list)
    has_structured_rules: bool = False
    structured_rules: StructuredRules | None = None
    limitations: list[str] = Field(default_factory=list)
    note: str = (
        "Testability score is deterministic — not a performance guarantee. "
        "Real trading remains disabled."
    )

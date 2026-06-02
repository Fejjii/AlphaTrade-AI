"""Trade journal schemas. Designed for future review and RAG retrieval."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.schemas.common import (
    ORMModel,
    StrategyId,
    StrictModel,
    Symbol,
    Timeframe,
    TradeDirection,
    TradeResult,
)


class JournalEntryCreate(StrictModel):
    """Request to create or update a journal entry."""

    organization_id: UUID | None = None
    user_id: UUID | None = None
    symbol: Symbol
    timeframe: Timeframe
    direction: TradeDirection
    strategy_id: StrategyId | None = None
    entry_rationale: str = Field(min_length=1, max_length=4000)
    exit_rationale: str | None = Field(default=None, max_length=4000)
    emotions: list[str] = Field(default_factory=list)
    mistakes: list[str] = Field(default_factory=list)
    lessons: str | None = Field(default=None, max_length=4000)
    improvement_rule: str | None = Field(default=None, max_length=2000)
    result: TradeResult = TradeResult.OPEN
    pnl: Decimal | None = None
    stress_score: int | None = Field(default=None, ge=0, le=10)
    tags: list[str] = Field(default_factory=list)
    screenshot_refs: list[str] = Field(default_factory=list)
    linked_proposal_id: UUID | None = None
    linked_position_id: UUID | None = None


class JournalEntryUpdate(StrictModel):
    exit_rationale: str | None = Field(default=None, max_length=4000)
    emotions: list[str] | None = None
    mistakes: list[str] | None = None
    lessons: str | None = Field(default=None, max_length=4000)
    improvement_rule: str | None = Field(default=None, max_length=2000)
    result: TradeResult | None = None
    pnl: Decimal | None = None
    stress_score: int | None = Field(default=None, ge=0, le=10)
    tags: list[str] | None = None
    screenshot_refs: list[str] | None = None
    linked_proposal_id: UUID | None = None
    linked_position_id: UUID | None = None


class JournalEntry(ORMModel):
    id: UUID
    organization_id: UUID
    user_id: UUID
    symbol: Symbol
    timeframe: Timeframe
    direction: TradeDirection
    strategy_id: StrategyId | None = None
    entry_rationale: str
    exit_rationale: str | None = None
    emotions: list[str] = Field(default_factory=list)
    mistakes: list[str] = Field(default_factory=list)
    lessons: str | None = None
    improvement_rule: str | None = None
    result: TradeResult = TradeResult.OPEN
    pnl: Decimal | None = None
    stress_score: int | None = None
    tags: list[str] = Field(default_factory=list)
    screenshot_refs: list[str] = Field(default_factory=list)
    linked_proposal_id: UUID | None = None
    linked_position_id: UUID | None = None
    rag_synced: bool = False
    created_at: datetime


class JournalEntryPrefill(StrictModel):
    """Suggested fields when journaling from a proposal or paper position."""

    symbol: Symbol
    timeframe: Timeframe
    direction: TradeDirection
    strategy_id: StrategyId | None = None
    entry_rationale: str
    linked_proposal_id: UUID | None = None
    linked_position_id: UUID | None = None
    tags: list[str] = Field(default_factory=list)


class PaginatedJournalEntries(StrictModel):
    items: list[JournalEntry]
    total: int
    limit: int
    offset: int

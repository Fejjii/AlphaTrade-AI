"""Public contracts for bounded Agent tools. Narrative text is never authority."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from app.schemas.common import PositiveDecimal, StrictModel, Symbol, Timeframe, TradeDirection
from app.schemas.watcher_watchlist import WatcherWatchlistSlotWrite


class ActionRequest(StrictModel):
    name: str = Field(min_length=1, max_length=80)
    arguments: dict[str, Any] = Field(default_factory=dict)


class ActionDescriptor(StrictModel):
    name: str
    input_contract: dict[str, Any]
    authority: str
    behavior: Literal["read", "propose", "confirm"]
    required_permissions: list[str]
    explicit_confirmation_required: bool
    result_record_identity: str
    limitations: list[str]


class TextInput(StrictModel):
    text: str = Field(min_length=1, max_length=4000)


class JournalCreateInput(TextInput):
    symbol: Symbol | None = None
    timeframe: Timeframe | None = None
    direction: TradeDirection | None = None


class JournalNoteInput(TextInput):
    journal_entry_id: UUID | None = None


class StrategyInput(TextInput):
    strategy_id: UUID | None = None
    evidence_document_ids: list[UUID] = Field(default_factory=list, max_length=20)


class KnowledgeInput(StrategyInput):
    title: str = Field(default="Trading knowledge proposal", min_length=1, max_length=255)
    kind: Literal["lesson", "rule", "observation"] = "lesson"


class WatcherChangeInput(StrictModel):
    operation: Literal["enable", "disable", "replace", "reorder", "universe"]
    revision: int | None = Field(default=None, ge=0)
    position: int | None = Field(default=None, ge=1, le=5)
    symbol: Symbol | None = None
    positions: list[int] = Field(default_factory=list, max_length=5)
    slots: list[WatcherWatchlistSlotWrite] = Field(default_factory=list, max_length=5)


class PaperTradeInput(StrictModel):
    symbol: Symbol | None = None
    timeframe: Timeframe | None = None
    direction: TradeDirection | None = None
    entry: PositiveDecimal | None = None
    stop: PositiveDecimal | None = None
    targets: list[PositiveDecimal] = Field(default_factory=list, max_length=10)
    trade_proposal_id: UUID | None = None


class EmptyInput(StrictModel):
    pass

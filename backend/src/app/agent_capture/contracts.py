"""Validated capture suggestions and user correction contracts."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.common import StrictModel

CaptureStatus = Literal["not_needed", "saved", "failed", "clarification", "unavailable"]

Category = Literal["journal", "rules", "strategies", "news_analysis", "lessons"]


class StrategyDraft(StrictModel):
    family: str = Field(min_length=1, max_length=100)
    market: str | None
    direction: Literal["long", "short", "both"] | None
    timeframe: str | None
    entry_rules: list[str] = Field(max_length=20)
    exit_rules: list[str] = Field(max_length=20)
    invalidation: list[str] = Field(max_length=20)
    missing_fields: list[str] = Field(max_length=20)
    # Model output has no approval, risk-setting, automation or order fields.


class CaptureSuggestion(StrictModel):
    category: Category
    title: str = Field(min_length=1, max_length=160)
    summary: str = Field(min_length=1, max_length=1600)
    evidence_quotes: list[str] = Field(min_length=1, max_length=8)
    tags: list[str] = Field(max_length=12)
    confidence: float = Field(ge=0, le=1)
    target_entry_id: UUID | None
    draft: StrategyDraft | None

    @model_validator(mode="after")
    def draft_is_only_strategy(self) -> "CaptureSuggestion":
        if self.draft is not None and self.category != "strategies":
            raise ValueError("Only a strategy capture can contain a draft")
        return self


class CapturePlan(StrictModel):
    entries: list[CaptureSuggestion] = Field(max_length=3)
    clarification: str | None = Field(max_length=300)


class SavedEntry(StrictModel):
    id: UUID
    category: Category
    title: str
    summary: str
    original_text: str
    conversation_id: UUID
    source_message_ids: list[UUID]
    source_document_id: UUID | None
    trade_id: UUID | None
    tags: list[str]
    draft: dict[str, Any] | None
    revision: int
    undone: bool
    created_at: datetime
    updated_at: datetime


class SavedEntryUpdate(StrictModel):
    expected_revision: int = Field(ge=1)
    category: Category | None = None
    title: str | None = Field(default=None, min_length=1, max_length=160)
    summary: str | None = Field(default=None, min_length=1, max_length=1600)
    undo: bool = False


class SavedEntriesPage(StrictModel):
    items: list[SavedEntry]
    total: int


class CaptureRetry(StrictModel):
    conversation_id: UUID
    source_message_id: UUID

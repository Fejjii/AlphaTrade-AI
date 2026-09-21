"""Persistent conversation, transcript, and strategy-proposal preview schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from app.schemas.common import (
    ConversationMessageRole,
    ConversationStatus,
    ORMModel,
    StrategyProposalStatus,
    StrictModel,
)
from app.schemas.structured_rules import StructuredRules, StructuredRulesValidation


class ConversationCreate(StrictModel):
    title: str | None = Field(default=None, max_length=200)
    strategy_id: UUID | None = None


class ConversationSummary(ORMModel):
    id: UUID
    organization_id: UUID
    user_id: UUID
    title: str | None = None
    status: ConversationStatus
    strategy_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class ConversationMessageRecord(ORMModel):
    id: UUID
    conversation_id: UUID
    organization_id: UUID
    user_id: UUID
    role: ConversationMessageRole
    content: str
    request_id: str | None = None
    intent: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class PaginatedConversations(StrictModel):
    items: list[ConversationSummary]
    total: int
    limit: int
    offset: int


class PaginatedConversationMessages(StrictModel):
    items: list[ConversationMessageRecord]
    total: int
    limit: int
    offset: int


class StrategyProposalCreate(StrictModel):
    """Create a preview-only structured-rules draft from plain English."""

    text: str = Field(min_length=10, max_length=8000)
    strategy_id: UUID | None = None


class StrategyProposalConfirm(StrictModel):
    confirm: str = Field(min_length=1, max_length=200)
    request_id: str | None = Field(default=None, max_length=80)
    expected_content_hash: str = Field(min_length=64, max_length=64)
    expected_parent_version_id: UUID | None = None
    expected_target_strategy_id: UUID | None = None


class StrategyProposalReject(StrictModel):
    confirm: str = Field(min_length=1, max_length=200)


class StrategyProposalRecord(ORMModel):
    id: UUID
    conversation_id: UUID
    organization_id: UUID
    user_id: UUID
    source_message_id: UUID | None = None
    target_strategy_id: UUID | None = None
    parent_version_id: UUID | None = None
    status: StrategyProposalStatus
    proposed_structured_rules: StructuredRules | None = None
    proposed_pattern_spec: dict[str, Any] | None = None
    proposed_card: dict[str, Any] | None = None
    validation: StructuredRulesValidation
    limitations: list[str] = Field(default_factory=list)
    challenge_notes: list[str] = Field(default_factory=list)
    context_refs: dict[str, Any] = Field(default_factory=dict)
    content_hash: str | None = None
    resulting_strategy_id: UUID | None = None
    resulting_version_id: UUID | None = None
    resulting_content_hash: str | None = None
    confirmation_request_id: str | None = None
    confirmed_at: datetime | None = None
    rejected_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    is_preview: bool = True
    mutates_strategy_authority: bool = False


class PaginatedStrategyProposals(StrictModel):
    items: list[StrategyProposalRecord]
    total: int
    limit: int
    offset: int


class StrategyVersionProvenance(ORMModel):
    strategy_id: UUID
    strategy_version_id: UUID
    conversation_id: UUID
    proposal_id: UUID
    source_message_id: UUID | None = None
    content_hash: str | None = None


class StrategyDiscussionContext(StrictModel):
    """Read-only references assembled from existing authorities."""

    strategy: dict[str, Any] | None = None
    versions: list[dict[str, Any]] = Field(default_factory=list)
    lessons: list[dict[str, Any]] = Field(default_factory=list)
    journal_trades: list[dict[str, Any]] = Field(default_factory=list)
    learning_stats: dict[str, Any] | None = None
    rag_citations: list[dict[str, Any]] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

"""Immutable contracts for the paper-only Telegram interaction layer."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field

from app.candidate_alerts.contracts import CandidateAlertActionResult, CandidateAlertProjection
from app.market_contracts.models import CanonicalModel
from app.signal_fusion.types import Sha256Hex
from app.telegram_security.actions import ActionEffectKind, TelegramRemoteAction
from app.telegram_security.contracts import ActionOutcome, ActionPayload, OutboxRecord

PAPER_NOTIFICATION_SCHEMA = "PaperTelegramNotification/v1"
PAPER_NOTIFY_OUTBOX_PREFIX = "paper-notify:"
PAPER_THREAD_OUTBOX_PREFIX = "paper-thread:"
PAPER_RESOURCE_WATCHER = "watcher_scan"
PAPER_RESOURCE_CANDIDATE = "candidate"
PAPER_RESOURCE_JOURNAL = "journal_trade"
PAPER_RESOURCE_LEARNING = "learning_summary"
PAPER_RESOURCE_PAPER_STATUS = "paper_status"
MAX_TEXT_BYTES = 4096


class PaperNotificationKind(StrEnum):
    WATCHER_CONFIRMED_SETUP = "WATCHER_CONFIRMED_SETUP"
    WATCHER_SCAN_BLOCKED = "WATCHER_SCAN_BLOCKED"
    CANDIDATE_ACTIVE = "CANDIDATE_ACTIVE"
    JOURNAL_OUTCOME = "JOURNAL_OUTCOME"


class DiscussionIntent(StrEnum):
    EXPLAIN_EVIDENCE = "EXPLAIN_EVIDENCE"
    EXPLAIN_STRATEGY = "EXPLAIN_STRATEGY"
    EXPLAIN_CANDIDATE = "EXPLAIN_CANDIDATE"
    EXPLAIN_RISK = "EXPLAIN_RISK"
    MARKET_CONTEXT = "MARKET_CONTEXT"
    PAPER_TRADE_STATUS = "PAPER_TRADE_STATUS"
    JOURNAL_OUTCOME = "JOURNAL_OUTCOME"
    LEARNING_SUMMARY = "LEARNING_SUMMARY"
    STRATEGY_DISCUSSION = "STRATEGY_DISCUSSION"
    CONFIRM_MUTATION = "CONFIRM_MUTATION"
    REQUEST_REJECT = "REQUEST_REJECT"
    REQUEST_SKIP = "REQUEST_SKIP"
    REQUEST_APPROVE = "REQUEST_APPROVE"
    REQUEST_EXECUTE = "REQUEST_EXECUTE"
    REQUEST_APPROVE_STRATEGY = "REQUEST_APPROVE_STRATEGY"
    REQUEST_OVERRIDE_ASSESSMENT = "REQUEST_OVERRIDE_ASSESSMENT"
    REQUEST_OVERRIDE_RISK = "REQUEST_OVERRIDE_RISK"
    REQUEST_MINT_CANDIDATE = "REQUEST_MINT_CANDIDATE"
    REQUEST_ENABLE_LIVE = "REQUEST_ENABLE_LIVE"
    UNKNOWN = "UNKNOWN"


class PaperAlertRecipient(CanonicalModel):
    organization_id: UUID
    user_id: UUID
    account_id: UUID
    binding_id: UUID
    bot_id: str = Field(min_length=1, max_length=64)
    chat_id: str = Field(min_length=1, max_length=64)


class WatcherScanNotice(CanonicalModel):
    """Watcher scan facts copied for notification. Not a second evaluator."""

    organization_id: UUID
    user_id: UUID
    scan_scope: str = Field(min_length=1, max_length=200)
    symbol: str = Field(min_length=1, max_length=32)
    status: str = Field(min_length=1, max_length=32)
    reason_code: str = Field(min_length=1, max_length=80)
    published: bool
    candidate_ids: tuple[UUID, ...] = ()
    request_hash: str | None = Field(default=None, min_length=64, max_length=64)
    lineage_id: UUID | None = None


class PaperNotificationIntent(CanonicalModel):
    schema_version: str = PAPER_NOTIFICATION_SCHEMA
    intent_id: UUID
    identity_hash: Sha256Hex
    organization_id: UUID
    user_id: UUID
    account_id: UUID
    kind: PaperNotificationKind
    resource_type: str = Field(min_length=1, max_length=64)
    resource_id: UUID
    content_hash: Sha256Hex
    telegram_revision_id: UUID
    candidate_id: UUID | None = None
    watcher_lineage_id: UUID | None = None
    watcher_reason_code: str | None = None
    text: str = Field(min_length=1, max_length=MAX_TEXT_BYTES)
    created_at: AwareDatetime


class PaperThread(CanonicalModel):
    thread_id: UUID
    organization_id: UUID
    user_id: UUID
    account_id: UUID
    binding_id: UUID
    bot_id: str
    chat_id: str
    resource_type: str
    resource_id: UUID | None = None
    notification_id: UUID | None = None
    created_at: AwareDatetime
    updated_at: AwareDatetime


class PaperThreadMessage(CanonicalModel):
    message_id: UUID
    thread_id: UUID
    organization_id: UUID
    user_id: UUID
    role: Literal["user", "assistant"]
    intent: DiscussionIntent
    content: str = Field(min_length=1, max_length=MAX_TEXT_BYTES)
    receipt_id: UUID | None = None
    created_at: AwareDatetime


class PresentedPaperConfirmation(CanonicalModel):
    confirmation_id: UUID
    thread_id: UUID
    organization_id: UUID
    user_id: UUID
    account_id: UUID
    action: TelegramRemoteAction
    resource_type: str
    resource_id: UUID
    content_hash: Sha256Hex
    revision_id: UUID | None = None
    payload_hash: Sha256Hex
    presented_at: AwareDatetime
    consumed_at: AwareDatetime | None = None


class PaperTradeStatusView(CanonicalModel):
    open_positions: int = Field(ge=0)
    open_orders: int = Field(ge=0)
    execution_mode: Literal["paper"] = "paper"
    real_trading_enabled: Literal[False] = False
    summary: str = Field(min_length=1, max_length=500)


class JournalOutcomeView(CanonicalModel):
    trade_id: UUID
    symbol: str = Field(min_length=1, max_length=32)
    status: str = Field(min_length=1, max_length=32)
    result: str | None = None
    net_pnl: str | None = None
    summary: str = Field(min_length=1, max_length=800)


class LearningSummaryView(CanonicalModel):
    organization_id: UUID
    candidate_id: UUID | None = None
    setup_quality: str | None = None
    execution_quality: str | None = None
    trader_behavior: str | None = None
    fact_lines: tuple[str, ...] = ()
    banner: str = Field(min_length=1, max_length=200)


class StrategyDraftView(CanonicalModel):
    """Non-authoritative discussion sketch. Confirm does not compile or approve."""

    strategy_id: UUID | None = None
    version_id: UUID | None = None
    compiled: Literal[False] = False
    approved: Literal[False] = False
    summary: str = Field(min_length=1, max_length=800)


class PaperNotificationProjection(CanonicalModel):
    intent: PaperNotificationIntent
    outbox: OutboxRecord
    thread: PaperThread
    candidate_alert: CandidateAlertProjection | None = None
    confirmations: tuple[PresentedPaperConfirmation, ...] = ()
    converged: bool


class PaperDiscussionResult(CanonicalModel):
    intent: DiscussionIntent
    telegram_outcome: ActionOutcome
    thread: PaperThread
    reply_outbox: OutboxRecord | None = None
    candidate_result: CandidateAlertActionResult | None = None
    refused: bool = False
    refusal_reason: str | None = None
    effect_kind: ActionEffectKind = ActionEffectKind.READ_ONLY_RESPONSE
    executed: Literal[False] = False
    execution_attempted: Literal[False] = False
    candidate_minted: Literal[False] = False
    setup_assessment_overridden: Literal[False] = False
    risk_overridden: Literal[False] = False
    strategy_approved: Literal[False] = False
    live_trading_enabled: Literal[False] = False


class PaperConfirmPayload(CanonicalModel):
    action: TelegramRemoteAction
    payload: ActionPayload

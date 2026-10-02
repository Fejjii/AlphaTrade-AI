"""Read-only attention contract with explicit provenance and unavailable states."""

from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field

from app.daily_review.contracts import ReviewSource
from app.market_contracts.models import CanonicalModel


class AttentionCategory(StrEnum):
    RISK_BLOCK = "risk_block"
    RISK_EVENT = "risk_event"
    PROVIDER_OUTAGE = "provider_outage"
    MISSING_EVIDENCE = "missing_evidence"
    STALE_EVIDENCE = "stale_evidence"
    TELEGRAM_FAILURE = "telegram_delivery_failure"
    WATCHER = "watcher_state"
    CONFIRMED = "confirmed_setup"
    FORMING = "forming_setup"
    POSITION = "paper_position"
    PROPOSAL = "strategy_proposal_pending"
    VALIDATION = "strategy_validation_job"
    REPLAY = "replay_result"
    LESSON = "daily_review_lesson"


class AttentionItem(CanonicalModel):
    item_id: UUID
    category: AttentionCategory
    severity: Literal["critical", "high", "medium", "low", "info"]
    title: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    sources: tuple[ReviewSource, ...] = Field(min_length=1)
    symbol: str | None = None
    strategy_id: str | None = None
    strategy_version_id: UUID | None = None
    recommended_next_action: str | None = None
    expires_at: AwareDatetime | None = None
    acknowledgement_state: Literal["unsupported", "unacknowledged", "acknowledged"] = "unsupported"


class AttentionSignal(CanonicalModel):
    """Internal scoped fact; semantic_key is never an executable action handle."""

    organization_id: UUID
    user_id: UUID | None  # None means organization-shared records only.
    semantic_key: str = Field(min_length=1)
    category: AttentionCategory
    severity: Literal["critical", "high", "medium", "low", "info"]
    title: str
    reason: str
    sources: tuple[ReviewSource, ...] = Field(min_length=1)
    symbol: str | None = None
    strategy_id: str | None = None
    strategy_version_id: UUID | None = None
    recommended_next_action: str | None = None
    expires_at: AwareDatetime | None = None
    acknowledgement_state: Literal["unsupported", "unacknowledged", "acknowledged"] = "unsupported"


class AttentionQueue(CanonicalModel):
    schema_version: Literal["AttentionQueue/v1"] = "AttentionQueue/v1"
    organization_id: UUID
    user_id: UUID
    generated_at: AwareDatetime
    items: tuple[AttentionItem, ...]
    recommended_next_action: str | None
    limitations: tuple[str, ...]
    execution_mode: Literal["paper"] = "paper"
    executes_trades: Literal[False] = False
    approves_strategies: Literal[False] = False
    bypasses_risk: Literal[False] = False
    telegram_delivery: Literal[False] = False

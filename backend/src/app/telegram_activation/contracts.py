"""Redaction-safe activation contracts. No tokens, secrets, or chat ids."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ActivationVerdict(StrEnum):
    NOT_ARMED = "NOT_ARMED"
    BLOCKED = "BLOCKED"
    ARMABLE = "ARMABLE"


class InboundSourceKind(StrEnum):
    REFUSING = "refusing"
    RECORDED = "recorded"
    HTTP = "http"


class ForbiddenCapabilities(FrozenModel):
    """Capabilities Telegram is not allowed to hold. Every flag stays false."""

    mint_candidate: Literal[False] = False
    override_setup_assessment: Literal[False] = False
    override_risk: Literal[False] = False
    activate_strategy: Literal[False] = False
    create_live_order: Literal[False] = False
    enable_live_trading: Literal[False] = False


class OutboxCounts(FrozenModel):
    pending: int = 0
    claimed: int = 0
    sent: int = 0
    acknowledged: int = 0
    retryable: int = 0
    dead_letter: int = 0


class PreflightReport(FrozenModel):
    """Whether this process may arm. Default settings are not armable."""

    runtime_armable: bool
    defaults_safe: bool
    verdict: ActivationVerdict
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    environment: str
    execution_mode: str
    real_trading_enabled: bool
    enable_real_trading: bool
    exchange_mode: str
    watcher_orchestration_enabled: bool
    market_watcher_enabled: bool
    telegram_alerts_enabled: bool
    telegram_interaction_enabled: bool
    automatic_telegram_delivery_enabled: bool
    telegram_paper_activation_armed: bool
    telegram_inbound_mode: str
    telegram_network_permitted: bool
    webhook_mounted: bool = False
    recipient_bound: bool = False
    private_chat: bool = False
    tenant_isolated: bool = False
    confirmation_identity_required: Literal[True] = True
    forbidden: ForbiddenCapabilities = Field(default_factory=ForbiddenCapabilities)
    outbox: OutboxCounts | None = None
    inbound_cursor_present: bool = False


class RollbackStep(FrozenModel):
    order: int
    action: str
    target: str
    mutates_environment: Literal[False] = False
    mutates_deployment: Literal[False] = False


class RollbackPlan(FrozenModel):
    """Human rollback checklist. Applying it does not edit env or deploy."""

    steps: tuple[RollbackStep, ...]
    disables_watcher: Literal[False] = False
    enables_live_trading: Literal[False] = False


class WebhookAccept(FrozenModel):
    status_code: int
    disposition: str
    reason: str | None = None


class PollResult(FrozenModel):
    fetched: int = 0
    applied: int = 0
    replayed: int = 0
    rejected: int = 0
    deferred: int = 0

"""Risk engine schemas: daily state, check request/result, and risk events.

The risk engine is deterministic and is the final authority on gating. These
schemas are the typed contract between callers and that engine.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import Field

from app.schemas.common import (
    Confidence,
    Leverage,
    ORMModel,
    PositiveDecimal,
    RiskAction,
    RiskPercent,
    RiskRuleId,
    RiskSeverity,
    StrategyId,
    StrictModel,
    Symbol,
    TradeDirection,
)


class DailyRiskState(ORMModel):
    """Per-user, per-day risk accounting that can lock trading."""

    organization_id: UUID
    user_id: UUID
    day: date
    realized_pnl: Decimal = Decimal("0")
    unrealized_pnl: Decimal = Decimal("0")
    daily_loss_limit: Decimal | None = Field(
        default=None,
        description="Max loss before trading locks (account ccy); None when unset.",
    )
    daily_target: Decimal | None = Field(
        default=None, description="Optional daily profit target for green-day protection."
    )
    max_trades_per_day: int | None = Field(
        default=None, ge=1, description="Optional per-day trade frequency cap."
    )
    trade_count: int = Field(default=0, ge=0)
    locked: bool = False
    updated_at: datetime


class RiskCheckRequest(StrictModel):
    """Input to the deterministic risk engine for a candidate trade."""

    symbol: Symbol
    direction: TradeDirection
    strategy_id: StrategyId | None = None
    entry_price: PositiveDecimal
    stop_loss: Decimal | None = Field(
        default=None, description="Absence triggers the no-stop-loss rule."
    )
    position_size: PositiveDecimal
    leverage: Leverage
    account_equity: PositiveDecimal
    risk_percent: RiskPercent | None = None
    is_countertrend: bool = False
    is_volatile_altcoin: bool = False
    funding_rate: Decimal | None = None
    volume_24h: Decimal | None = None
    sleep_test_passed: bool | None = Field(
        default=None, description="None = not answered; False = position too large to sleep on."
    )


class TriggeredRule(ORMModel):
    """A single rule outcome contributing to the overall verdict."""

    rule_id: RiskRuleId
    action: RiskAction
    severity: RiskSeverity
    message: str


class RiskCheckResult(ORMModel):
    """Aggregated, deterministic verdict.

    The overall ``action`` is the most restrictive of all triggered rules; the
    engine defaults to ``BLOCK`` when inputs are insufficient to decide safely.
    """

    action: RiskAction
    severity: RiskSeverity
    triggered_rules: list[TriggeredRule] = Field(default_factory=list)
    explanation: str
    approval_required: bool
    suggested_modification: dict[str, str] | None = Field(
        default=None, description="Optional safer parameters (e.g. reduced size/leverage)."
    )


class RiskEvent(ORMModel):
    """Audit-grade record of a risk rule firing (Architecture §8)."""

    id: UUID | None = None
    organization_id: UUID
    user_id: UUID
    rule_triggered: RiskRuleId
    severity: RiskSeverity
    action_taken: RiskAction
    confidence: Confidence | None = None
    details: dict[str, str] = Field(default_factory=dict)
    timestamp: datetime


class UserRiskSettingsResponse(StrictModel):
    """Tenant-scoped user risk settings for paper discipline."""

    organization_id: UUID
    user_id: UUID
    daily_loss_limit: Decimal | None = None
    daily_target: Decimal | None = None
    max_trades_per_day: int = Field(default=20, ge=1)
    max_risk_per_trade_percent: Decimal = Field(default=Decimal("1"), gt=0, le=10)
    default_account_balance: PositiveDecimal = Field(default=Decimal("10000"))
    timezone: str = "UTC"
    green_day_protection_enabled: bool = True
    one_loss_stop_enabled: bool = False
    overtrading_guard_enabled: bool = True
    notes: str | None = None
    using_defaults: bool = Field(
        default=False,
        description="True when no persisted row exists and system defaults are returned.",
    )
    timezone_fallback: bool = False


class UserRiskSettingsUpdate(StrictModel):
    """Partial update for user risk settings."""

    daily_loss_limit: Decimal | None = None
    daily_target: Decimal | None = None
    max_trades_per_day: int | None = Field(default=None, ge=1)
    max_risk_per_trade_percent: Decimal | None = Field(default=None, gt=0, le=10)
    default_account_balance: PositiveDecimal | None = None
    timezone: str | None = None
    green_day_protection_enabled: bool | None = None
    one_loss_stop_enabled: bool | None = None
    overtrading_guard_enabled: bool | None = None
    notes: str | None = None


class KillSwitchScope(StrEnum):
    """Kill-switch scope labels (organization is the durable API scope)."""

    ORGANIZATION = "organization"
    GLOBAL = "global"


class KillSwitchStatus(StrictModel):
    """Authoritative kill-switch status for an organization."""

    organization_id: UUID
    active: bool
    reason: str | None = None
    activated_by: UUID | None = None
    activated_at: datetime | None = None
    deactivated_by: UUID | None = None
    deactivated_at: datetime | None = None
    version: int = 1
    scope: str = KillSwitchScope.ORGANIZATION
    global_active: bool = Field(
        default=False,
        description="True when the process-level GLOBAL_KILL_SWITCH_ACTIVE env gate is on.",
    )
    execution_blocked: bool = Field(
        default=False,
        description="True when organization and/or global kill switch blocks execution.",
    )


class KillSwitchMutationRequest(StrictModel):
    """Activate or deactivate the organization kill switch."""

    confirm: bool = Field(description="Must be true; explicit confirmation of the mutation.")
    reason: str = Field(min_length=3, max_length=500)
    expected_version: int | None = Field(
        default=None,
        ge=1,
        description="Optional optimistic concurrency token from the last GET.",
    )

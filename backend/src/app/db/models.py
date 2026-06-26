"""SQLAlchemy 2.0 typed ORM models for all core trading entities.

PostgreSQL is the production target; SQLite is used only for tests. Types are
chosen to be portable across both: ``Uuid`` for ids, ``Numeric(20, 8)`` for
monetary/size values, ``JSON`` for small structured lists, and non-native
``Enum`` (VARCHAR + CHECK) reusing the exact enums defined in
:mod:`app.schemas.common` to prevent string drift between API and database.

Tenant-scoped resources carry ``organization_id``; vectors live in Qdrant while
document/chunk metadata lives here.
"""

from __future__ import annotations

import uuid
from datetime import date as date_type
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.schemas.common import (
    ActorType,
    AlertDeliveryChannel,
    AlertDeliveryStatus,
    ApprovalAction,
    ApprovalStatus,
    AuditEventType,
    AuditResult,
    AuditSeverity,
    BacktestRunStatus,
    BacktestStatus,
    CostSource,
    DocumentSourceType,
    ExchangeAccountStatus,
    ExecutionMode,
    LossAcceptanceStatus,
    ManualLevelType,
    MarketWatcherBridgeDecisionType,
    MarketWatcherObservationStatus,
    MembershipRole,
    OrderSide,
    OrderStatus,
    OrderType,
    PaperAlertSeverity,
    PaperAlertType,
    PaperObservabilityEventType,
    PaperRuntimeCycleMode,
    PaperRuntimeCycleStatus,
    PaperSignalStatus,
    PaperTradeStatus,
    PaperValidationRuntimeMode,
    PaperValidationStatus,
    PositionStatus,
    ProposalStatus,
    RiskAction,
    RiskProfile,
    RiskRuleId,
    RiskSeverity,
    SetupCategory,
    StrategyId,
    StrategyValidationStatus,
    TradeDirection,
    TradeResult,
    UsageStatus,
    UserRole,
)

_MONEY = Numeric(20, 8)
_ENUM_LEN = 40


def _enum(enum_cls: type) -> Enum:
    """Portable, non-native enum column (VARCHAR + CHECK)."""
    return Enum(enum_cls, native_enum=False, length=_ENUM_LEN, validate_strings=True)


# --------------------------------------------------------------------------- #
# Identity & tenancy
# --------------------------------------------------------------------------- #


class Organization(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(_enum(UserRole), default=UserRole.TRADER)
    risk_profile: Mapped[RiskProfile] = mapped_column(
        _enum(RiskProfile), default=RiskProfile.MODERATE
    )
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)


class Membership(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "organization_id", name="uq_membership_user_org"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    role: Mapped[MembershipRole] = mapped_column(
        _enum(MembershipRole), default=MembershipRole.TRADER
    )


class EmailVerificationToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One-time email verification token (hashed at rest)."""

    __tablename__ = "email_verification_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PasswordResetToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One-time password reset token (hashed at rest)."""

    __tablename__ = "password_reset_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OrganizationInvitation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Organization membership invitation (token hashed at rest)."""

    __tablename__ = "organization_invitations"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    role: Mapped[MembershipRole] = mapped_column(_enum(MembershipRole), nullable=False)
    invited_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RefreshToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Rotating refresh token store (hashed at rest)."""

    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("refresh_tokens.id"), nullable=True
    )


class ExchangeAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "exchange_accounts"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    exchange: Mapped[str] = mapped_column(String(40), nullable=False)
    api_key_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    has_withdrawal_permission: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[ExchangeAccountStatus] = mapped_column(
        _enum(ExchangeAccountStatus), default=ExchangeAccountStatus.ACTIVE
    )


# --------------------------------------------------------------------------- #
# Market data (global, not tenant-scoped)
# --------------------------------------------------------------------------- #


class MarketSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "market_snapshots"

    symbol: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    open: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    high: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    low: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    close: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    volume: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    funding_rate: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class IndicatorSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "indicator_snapshots"

    symbol: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    rsi: Mapped[float | None] = mapped_column(nullable=True)
    vwap: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    ema_fast: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    ema_slow: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    macd: Mapped[float | None] = mapped_column(nullable=True)
    macd_signal: Mapped[float | None] = mapped_column(nullable=True)
    atr: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    volatility: Mapped[float | None] = mapped_column(nullable=True)
    funding_rate: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# --------------------------------------------------------------------------- #
# Setups, signals & analytics
# --------------------------------------------------------------------------- #


class SetupDefinition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "setup_definitions"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_setup_name_version"),)

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    strategy_id: Mapped[StrategyId] = mapped_column(_enum(StrategyId), nullable=False)
    category: Mapped[SetupCategory] = mapped_column(_enum(SetupCategory), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    rules: Mapped[list] = mapped_column(JSON, default=list)
    filters: Mapped[list] = mapped_column(JSON, default=list)


class SetupPerformance(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "setup_performance"

    setup_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("setup_definitions.id"), unique=True, nullable=False
    )
    trades: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    win_rate: Mapped[float] = mapped_column(default=0.0)
    expectancy: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal("0"))
    avg_pnl: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal("0"))
    avg_stress: Mapped[float | None] = mapped_column(nullable=True)


class StrategySignal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "strategy_signals"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    setup_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("setup_definitions.id"), nullable=True
    )
    strategy_id: Mapped[StrategyId] = mapped_column(_enum(StrategyId), nullable=False)
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    direction: Mapped[TradeDirection] = mapped_column(_enum(TradeDirection), nullable=False)
    confidence: Mapped[float] = mapped_column(nullable=False)
    entry_low: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    entry_high: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    invalidation: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    risk_notes: Mapped[list] = mapped_column(JSON, default=list)
    signal_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# --------------------------------------------------------------------------- #
# Proposals, approvals, execution & positions
# --------------------------------------------------------------------------- #


class TradeProposal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "trade_proposals"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    signal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("strategy_signals.id"), nullable=True
    )
    strategy_id: Mapped[StrategyId] = mapped_column(_enum(StrategyId), nullable=False)
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    direction: Mapped[TradeDirection] = mapped_column(_enum(TradeDirection), nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    position_size: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    leverage: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    stop_loss: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    take_profits: Mapped[list] = mapped_column(JSON, default=list)
    breakeven_trigger: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    runner_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    runner_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    invalidation: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(nullable=False)
    risk_level: Mapped[RiskSeverity] = mapped_column(_enum(RiskSeverity), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ProposalStatus] = mapped_column(
        _enum(ProposalStatus), default=ProposalStatus.DRAFT
    )
    entry_low: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    entry_high: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    approval_required: Mapped[bool] = mapped_column(Boolean, default=False)
    risk_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    user_strategy_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_strategies.id"), nullable=True
    )
    planned_loss_amount: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    loss_acceptance_required: Mapped[bool] = mapped_column(Boolean, default=False)
    loss_acceptance_status: Mapped[LossAcceptanceStatus] = mapped_column(
        _enum(LossAcceptanceStatus), default=LossAcceptanceStatus.NOT_REQUIRED
    )
    actual_loss_amount: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)


class UserStrategy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Tenant-scoped strategy library entry (Slice 33)."""

    __tablename__ = "user_strategies"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "user_id",
            "name",
            name="uq_user_strategy_org_user_name",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    setup_type: Mapped[StrategyId] = mapped_column(_enum(StrategyId), nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    paper_eligible: Mapped[bool] = mapped_column(Boolean, default=False)


class UserStrategyVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Versioned strategy card content."""

    __tablename__ = "user_strategy_versions"
    __table_args__ = (
        UniqueConstraint(
            "strategy_id",
            "version",
            name="uq_user_strategy_version",
        ),
    )

    strategy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_strategies.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    card: Mapped[dict] = mapped_column(JSON, nullable=False)
    validation_status: Mapped[StrategyValidationStatus] = mapped_column(
        _enum(StrategyValidationStatus), default=StrategyValidationStatus.DRAFT
    )
    backtest_status: Mapped[BacktestStatus] = mapped_column(
        _enum(BacktestStatus), default=BacktestStatus.NOT_RUN
    )
    paper_validation_status: Mapped[PaperValidationStatus] = mapped_column(
        _enum(PaperValidationStatus), default=PaperValidationStatus.NOT_STARTED
    )
    structured_rules: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    lesson_source_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class LessonCandidate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Discipline lesson awaiting review — not auto-promoted to permanent rules."""

    __tablename__ = "lesson_candidates"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), default="journal", nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    related_strategy_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_strategies.id"), nullable=True
    )
    trade_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("journals.id"), nullable=True
    )
    related_journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("journals.id"), nullable=True
    )
    lesson_text: Mapped[str] = mapped_column(Text, nullable=False)
    mistake_type: Mapped[str] = mapped_column(String(60), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="pending_review", nullable=False)
    proposed_rule_update: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    accepted_rule_update: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    analysis_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class HistoricalCandle(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Persisted OHLCV bar for backtest replay (global market data — not tenant-scoped)."""

    __tablename__ = "historical_candles"
    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "exchange",
            "timeframe",
            "open_time",
            name="uq_historical_candle",
        ),
    )

    symbol: Mapped[str] = mapped_column(String(30), nullable=False)
    exchange: Mapped[str] = mapped_column(String(40), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    close_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    high: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    low: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    close: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    volume: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    is_stale: Mapped[bool] = mapped_column(Boolean, default=False)
    freshness_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class BacktestRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Backtest run record (Slice 35 — deterministic simulation, paper only)."""

    __tablename__ = "backtest_runs"

    strategy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_strategies.id"), nullable=False)
    strategy_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_strategy_versions.id"), nullable=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[BacktestRunStatus] = mapped_column(
        _enum(BacktestRunStatus), default=BacktestRunStatus.NOT_STARTED
    )
    assumptions: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class BacktestTrade(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Simulated trade from a backtest run."""

    __tablename__ = "backtest_trades"

    backtest_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("backtest_runs.id"), nullable=False
    )
    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    exit_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    exit_price: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    stop_loss: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    size: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    fees: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    slippage_cost: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    gross_pnl: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    net_pnl: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    tp_hit_status: Mapped[str] = mapped_column(String(40), nullable=False)
    exit_reason: Mapped[str] = mapped_column(String(60), nullable=False)
    rule_notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class PaperValidationRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Paper validation run with metrics (Slice 35 — paper only)."""

    __tablename__ = "paper_validation_runs"

    strategy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_strategies.id"), nullable=False)
    strategy_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_strategy_versions.id"), nullable=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[PaperValidationStatus] = mapped_column(
        _enum(PaperValidationStatus), default=PaperValidationStatus.NOT_STARTED
    )
    runtime_mode: Mapped[PaperValidationRuntimeMode] = mapped_column(
        _enum(PaperValidationRuntimeMode), default=PaperValidationRuntimeMode.SCAN_ONLY
    )
    paper_eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    blockers: Mapped[list | None] = mapped_column(JSON, nullable=True)
    last_scan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_tick_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_scan_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    recommendation: Mapped[str | None] = mapped_column(String(40), nullable=True)


class PaperSignal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Detected setup during paper validation scan (Slice 39)."""

    __tablename__ = "paper_signals"

    paper_validation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("paper_validation_runs.id"), nullable=False
    )
    strategy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_strategies.id"), nullable=False)
    strategy_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_strategy_versions.id"), nullable=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)
    exchange: Mapped[str] = mapped_column(String(40), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    direction: Mapped[TradeDirection] = mapped_column(_enum(TradeDirection), nullable=False)
    triggered: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[PaperSignalStatus] = mapped_column(
        _enum(PaperSignalStatus), default=PaperSignalStatus.DETECTED
    )
    matched_entry_blocks: Mapped[list | None] = mapped_column(JSON, nullable=True)
    blocked_no_trade_filters: Mapped[list | None] = mapped_column(JSON, nullable=True)
    confidence: Mapped[float] = mapped_column(default=0.0)
    suggested_entry: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    stop_loss: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    invalidation: Mapped[str | None] = mapped_column(Text, nullable=True)
    tp_plan: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    runner_plan: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    limitations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    rule_engine_source: Mapped[str | None] = mapped_column(String(40), nullable=True)


class PaperTrade(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Simulated paper trade (Slice 39 — no exchange orders)."""

    __tablename__ = "paper_trades"

    paper_validation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("paper_validation_runs.id"), nullable=False
    )
    strategy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_strategies.id"), nullable=False)
    strategy_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_strategy_versions.id"), nullable=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_from_signal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("paper_signals.id"), nullable=True
    )
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)
    exchange: Mapped[str] = mapped_column(String(40), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    direction: Mapped[TradeDirection] = mapped_column(_enum(TradeDirection), nullable=False)
    entry_price: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    entry_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    size: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    stop_loss: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    invalidation: Mapped[str | None] = mapped_column(Text, nullable=True)
    tp_plan: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    runner_plan: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[PaperTradeStatus] = mapped_column(
        _enum(PaperTradeStatus), default=PaperTradeStatus.PROPOSED
    )
    exit_price: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    exit_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(60), nullable=True)
    gross_pnl: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    net_pnl: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    fees: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    slippage: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    rule_engine_source: Mapped[str | None] = mapped_column(String(40), nullable=True)


class PaperTradeEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Audit trail for paper trade lifecycle events."""

    __tablename__ = "paper_trade_events"

    paper_trade_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("paper_trades.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class PaperValidationMetricSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Point-in-time paper validation metrics after trade close."""

    __tablename__ = "paper_validation_metric_snapshots"

    paper_validation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("paper_validation_runs.id"), nullable=False
    )
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False)
    trigger_trade_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("paper_trades.id"), nullable=True
    )


class PaperValidationSchedulerConfig(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Tenant-scoped paper scheduler settings (Slice 40 — env flag still required)."""

    __tablename__ = "paper_validation_scheduler_configs"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_paper_scheduler_org"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    interval_seconds: Mapped[int] = mapped_column(Integer, default=300)
    max_runs_per_cycle: Mapped[int] = mapped_column(Integer, default=5)
    max_scans_per_minute: Mapped[int] = mapped_column(Integer, default=10)
    last_tick_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_tick_status: Mapped[str | None] = mapped_column(String(40), nullable=True)


class PaperValidationRuntimeHistory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Per-cycle runtime history for scans, ticks, and scheduler cycles."""

    __tablename__ = "paper_validation_runtime_history"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("paper_validation_runs.id"), nullable=True
    )
    strategy_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_strategies.id"), nullable=True
    )
    symbol: Mapped[str | None] = mapped_column(String(30), nullable=True)
    mode: Mapped[PaperRuntimeCycleMode] = mapped_column(
        _enum(PaperRuntimeCycleMode), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[PaperRuntimeCycleStatus] = mapped_column(
        _enum(PaperRuntimeCycleStatus), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    signals_created: Mapped[int] = mapped_column(Integer, default=0)
    trades_opened: Mapped[int] = mapped_column(Integer, default=0)
    trades_closed: Mapped[int] = mapped_column(Integer, default=0)
    blockers: Mapped[list | None] = mapped_column(JSON, nullable=True)
    warnings: Mapped[list | None] = mapped_column(JSON, nullable=True)
    data_freshness: Mapped[str | None] = mapped_column(String(40), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class PaperValidationAlert(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Paper validation alert events (Slice 40 — no Telegram/email delivery)."""

    __tablename__ = "paper_validation_alerts"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    alert_type: Mapped[PaperAlertType] = mapped_column(_enum(PaperAlertType), nullable=False)
    severity: Mapped[PaperAlertSeverity] = mapped_column(
        _enum(PaperAlertSeverity), default=PaperAlertSeverity.INFO
    )
    strategy_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_strategies.id"), nullable=True
    )
    paper_validation_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("paper_validation_runs.id"), nullable=True
    )
    paper_trade_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("paper_trades.id"), nullable=True
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dedup_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    delivery_status: Mapped[AlertDeliveryStatus] = mapped_column(
        _enum(AlertDeliveryStatus), default=AlertDeliveryStatus.DISABLED
    )
    delivery_channel: Mapped[AlertDeliveryChannel] = mapped_column(
        _enum(AlertDeliveryChannel), default=AlertDeliveryChannel.IN_APP
    )
    delivery_attempts: Mapped[int] = mapped_column(default=0)
    last_delivery_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MarketWatcherObservation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Read-only market watcher observations (Slice 41 — no execution)."""

    __tablename__ = "market_watcher_observations"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)
    exchange: Mapped[str] = mapped_column(String(40), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    price: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    volume: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    data_freshness: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[MarketWatcherObservationStatus] = mapped_column(
        _enum(MarketWatcherObservationStatus), nullable=False
    )
    related_strategy_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_strategies.id"), nullable=True
    )
    related_paper_validation_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("paper_validation_runs.id"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_alert_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("paper_validation_alerts.id"), nullable=True
    )


class MarketWatcherBridgeDecision(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Market watcher → paper validation bridge decision history (Slice 42)."""

    __tablename__ = "market_watcher_bridge_decisions"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    observation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("market_watcher_observations.id"), nullable=True
    )
    strategy_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_strategies.id"), nullable=True
    )
    paper_validation_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("paper_validation_runs.id"), nullable=True
    )
    symbol: Mapped[str | None] = mapped_column(String(30), nullable=True)
    exchange: Mapped[str | None] = mapped_column(String(40), nullable=True)
    timeframe: Mapped[str | None] = mapped_column(String(10), nullable=True)
    decision: Mapped[MarketWatcherBridgeDecisionType] = mapped_column(
        _enum(MarketWatcherBridgeDecisionType), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    blockers: Mapped[list | None] = mapped_column(JSON, nullable=True)
    triggered_scan_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("paper_signals.id"), nullable=True
    )
    created_alert_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("paper_validation_alerts.id"), nullable=True
    )
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


class PaperValidationObservabilityEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Structured observability for paper validation runtime."""

    __tablename__ = "paper_validation_observability_events"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    event_type: Mapped[PaperObservabilityEventType] = mapped_column(
        _enum(PaperObservabilityEventType), nullable=False
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("paper_validation_runs.id"), nullable=True
    )
    strategy_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_strategies.id"), nullable=True
    )
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)


class PaperValidationSampleWindow(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Walk-forward sample window metrics for paper validation evidence."""

    __tablename__ = "paper_validation_sample_windows"

    paper_validation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("paper_validation_runs.id"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    trades_count: Mapped[int] = mapped_column(Integer, default=0)
    win_rate: Mapped[float] = mapped_column(default=0.0)
    net_pnl: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal("0"))
    max_drawdown: Mapped[float] = mapped_column(default=0.0)
    expectancy: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal("0"))
    recommendation: Mapped[str | None] = mapped_column(String(40), nullable=True)
    data_quality: Mapped[str | None] = mapped_column(String(40), nullable=True)


class ManualChartLevel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """User-drawn chart levels for pre-trade analysis."""

    __tablename__ = "manual_chart_levels"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)
    exchange: Mapped[str] = mapped_column(String(40), nullable=False)
    timeframe: Mapped[str | None] = mapped_column(String(8), nullable=True)
    level_type: Mapped[ManualLevelType] = mapped_column(_enum(ManualLevelType), nullable=False)
    price: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    price_low: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    price_high: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class WatchlistItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "watchlist_items"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "user_id",
            "symbol",
            "exchange",
            name="uq_watchlist_org_user_symbol_exchange",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)
    exchange: Mapped[str] = mapped_column(String(40), nullable=False)
    timeframes: Mapped[list] = mapped_column(JSON, default=list)
    strategy_ids: Mapped[list] = mapped_column(JSON, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class ApprovalRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "approvals"

    proposal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("trade_proposals.id"), unique=True, nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[ApprovalStatus] = mapped_column(
        _enum(ApprovalStatus), default=ApprovalStatus.PENDING
    )
    proposed_action: Mapped[ApprovalAction | None] = mapped_column(
        _enum(ApprovalAction), nullable=True
    )
    modified_fields: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    risk_level: Mapped[RiskSeverity] = mapped_column(_enum(RiskSeverity), nullable=False)
    confidence: Mapped[float] = mapped_column(nullable=False)
    approval_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    audit_event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("audit_logs.id"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Order(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "orders"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    strategy_id: Mapped[StrategyId | None] = mapped_column(_enum(StrategyId), nullable=True)
    proposal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("trade_proposals.id"), nullable=True
    )
    approval_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("approvals.id"), nullable=True)
    mode: Mapped[ExecutionMode] = mapped_column(_enum(ExecutionMode), default=ExecutionMode.PAPER)
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)
    side: Mapped[OrderSide] = mapped_column(_enum(OrderSide), nullable=False)
    order_type: Mapped[OrderType] = mapped_column(_enum(OrderType), nullable=False)
    size: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    price: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    status: Mapped[OrderStatus] = mapped_column(_enum(OrderStatus), default=OrderStatus.PENDING)
    reduce_only: Mapped[bool] = mapped_column(Boolean, default=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    exchange_order_id: Mapped[str | None] = mapped_column(String(128), nullable=True)


class Position(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "positions"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    strategy_id: Mapped[StrategyId | None] = mapped_column(_enum(StrategyId), nullable=True)
    linked_proposal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("trade_proposals.id"), nullable=True
    )
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)
    direction: Mapped[TradeDirection] = mapped_column(_enum(TradeDirection), nullable=False)
    size: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    leverage: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    stop_loss: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    liquidation_price: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    unrealized_pnl: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal("0"))
    realized_pnl: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal("0"))
    status: Mapped[PositionStatus] = mapped_column(
        _enum(PositionStatus), default=PositionStatus.OPEN
    )
    take_profits: Mapped[list] = mapped_column(JSON, default=list)
    risk_state: Mapped[dict] = mapped_column(JSON, default=dict)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# --------------------------------------------------------------------------- #
# Risk state & events
# --------------------------------------------------------------------------- #


class DailyRiskState(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "daily_risk_states"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", "day", name="uq_daily_risk_org_user_day"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    day: Mapped[date_type] = mapped_column(Date, nullable=False)
    realized_pnl: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal("0"))
    unrealized_pnl: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal("0"))
    daily_loss_limit: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    daily_target: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    max_trades_per_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trade_count: Mapped[int] = mapped_column(Integer, default=0)
    locked: Mapped[bool] = mapped_column(Boolean, default=False)


class UserRiskSettings(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Persistent per-user risk settings for paper discipline (Slice 45)."""

    __tablename__ = "user_risk_settings"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_user_risk_settings_org_user"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    daily_loss_limit: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    daily_target: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    max_trades_per_day: Mapped[int] = mapped_column(Integer, default=20)
    max_risk_per_trade_percent: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal("1"))
    default_account_balance: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal("10000"))
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    green_day_protection_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    one_loss_stop_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    overtrading_guard_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class UserNotificationPreferences(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Per-user notification delivery preferences (Slice 46 — no provider secrets)."""

    __tablename__ = "user_notification_preferences"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "user_id",
            name="uq_user_notification_preferences_org_user",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    in_app_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    webhook_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    telegram_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    min_severity: Mapped[PaperAlertSeverity] = mapped_column(
        _enum(PaperAlertSeverity), default=PaperAlertSeverity.INFO
    )
    enabled_alert_types: Mapped[list | None] = mapped_column(JSON, nullable=True)
    quiet_hours_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    quiet_hours_start: Mapped[str | None] = mapped_column(String(5), nullable=True)
    quiet_hours_end: Mapped[str | None] = mapped_column(String(5), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    digest_mode: Mapped[str] = mapped_column(String(32), default="immediate")
    telegram_chat_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class RiskEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "risk_events"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    rule_triggered: Mapped[RiskRuleId] = mapped_column(_enum(RiskRuleId), nullable=False)
    severity: Mapped[RiskSeverity] = mapped_column(_enum(RiskSeverity), nullable=False)
    action_taken: Mapped[RiskAction] = mapped_column(_enum(RiskAction), nullable=False)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# --------------------------------------------------------------------------- #
# Journal
# --------------------------------------------------------------------------- #


class TradeJournal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "journals"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    direction: Mapped[TradeDirection] = mapped_column(_enum(TradeDirection), nullable=False)
    strategy_id: Mapped[StrategyId | None] = mapped_column(_enum(StrategyId), nullable=True)
    entry_rationale: Mapped[str] = mapped_column(Text, nullable=False)
    exit_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    emotions: Mapped[list] = mapped_column(JSON, default=list)
    mistakes: Mapped[list] = mapped_column(JSON, default=list)
    lessons: Mapped[str | None] = mapped_column(Text, nullable=True)
    improvement_rule: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[TradeResult] = mapped_column(_enum(TradeResult), default=TradeResult.OPEN)
    pnl: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    stress_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    screenshot_refs: Mapped[list] = mapped_column(JSON, default=list)
    linked_proposal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("trade_proposals.id"), nullable=True
    )
    linked_position_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("positions.id"), nullable=True
    )


# --------------------------------------------------------------------------- #
# RAG knowledge base (metadata only; vectors in Qdrant)
# --------------------------------------------------------------------------- #


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "source_hash",
            name="uq_document_org_source_hash",
        ),
    )

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    source_type: Mapped[DocumentSourceType] = mapped_column(
        _enum(DocumentSourceType), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    uri: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    source_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    tags: Mapped[list] = mapped_column(JSON, default=list)


class Chunk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chunks"
    __table_args__ = (UniqueConstraint("document_id", "ordinal", name="uq_chunk_document_ordinal"),)

    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    embedding_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    chunk_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict)


# --------------------------------------------------------------------------- #
# Usage & audit
# --------------------------------------------------------------------------- #


class UsageEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "usage_events"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    feature: Mapped[str] = mapped_column(String(80), nullable=False)
    model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(80), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    provider_reported_cost: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    estimated_cost: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal("0"))
    cost_source: Mapped[CostSource] = mapped_column(
        _enum(CostSource), default=CostSource.UNAVAILABLE, nullable=False
    )
    cost_is_placeholder: Mapped[bool] = mapped_column(Boolean, default=True)
    tool_calls: Mapped[int] = mapped_column(Integer, default=0)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False)
    latency_ms: Mapped[float | None] = mapped_column(nullable=True)
    status: Mapped[UsageStatus] = mapped_column(
        _enum(UsageStatus), default=UsageStatus.SUCCESS, nullable=False
    )
    event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OrganizationQuota(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Per-organization usage limits (Slice 24)."""

    __tablename__ = "organization_quotas"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), unique=True, nullable=False
    )
    monthly_token_limit: Mapped[int] = mapped_column(Integer, default=2_000_000)
    monthly_cost_limit: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal("100"))
    daily_request_limit: Mapped[int] = mapped_column(Integer, default=5_000)
    limit_agent_chat: Mapped[int] = mapped_column(Integer, default=2_000)
    limit_rag_ingest: Mapped[int] = mapped_column(Integer, default=500)
    limit_market_analyze: Mapped[int] = mapped_column(Integer, default=1_000)
    limit_agent_narrative: Mapped[int] = mapped_column(Integer, default=2_000)
    limit_paper_execution: Mapped[int] = mapped_column(Integer, default=200)
    soft_warning_threshold: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal("0.80"))
    hard_block_threshold: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal("1.00"))
    plan_id: Mapped[str] = mapped_column(String(40), default="free", nullable=False)


# --------------------------------------------------------------------------- #
# Billing (Slice 26)
# --------------------------------------------------------------------------- #


class BillingCustomer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "billing_customers"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_billing_customer_org"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_customer_id: Mapped[str] = mapped_column(String(128), nullable=False)
    billing_email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)


class Subscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "subscriptions"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_subscription_org"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    provider_subscription_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    plan_id: Mapped[str] = mapped_column(String(40), default="free", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    current_period_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False)


class BillingEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "billing_events"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_event_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    redacted_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UsageExportBatch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "usage_export_batches"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    total_events: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    provider_reported_cost: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal("0"))
    estimated_cost: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal("0"))
    billing_grade_cost: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal("0"))
    cost_is_billing_grade: Mapped[bool] = mapped_column(Boolean, default=False)
    fallback_event_count: Mapped[int] = mapped_column(Integer, default=0)
    export_summary: Mapped[dict] = mapped_column(JSON, default=dict)


class WebhookEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "webhook_events"
    __table_args__ = (UniqueConstraint("provider_event_id", name="uq_webhook_provider_event"),)

    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="processed", nullable=False)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True
    )
    redacted_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AuditLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "audit_logs"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_type: Mapped[ActorType] = mapped_column(
        _enum(ActorType), default=ActorType.SYSTEM, nullable=False
    )
    action: Mapped[AuditEventType] = mapped_column(_enum(AuditEventType), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    result: Mapped[AuditResult] = mapped_column(
        _enum(AuditResult), default=AuditResult.SUCCESS, nullable=False
    )
    severity: Mapped[AuditSeverity] = mapped_column(
        _enum(AuditSeverity), default=AuditSeverity.INFO, nullable=False
    )
    payload_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    redacted_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    before: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# --------------------------------------------------------------------------- #
# Background worker (Slice 59)
# --------------------------------------------------------------------------- #


class WorkerHeartbeat(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Liveness + control record for a background worker instance.

    One row per ``worker_name``. ``paused`` is the manual pause/resume switch;
    ``status`` reflects the last cycle outcome.
    """

    __tablename__ = "worker_heartbeats"
    __table_args__ = (UniqueConstraint("worker_name", name="uq_worker_heartbeat_name"),)

    worker_name: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="starting", nullable=False)
    paused: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cycle_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_beat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    detail: Mapped[str | None] = mapped_column(String(255), nullable=True)


class MarketScanRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One worker scan cycle. Failed rows act as a dead-letter record."""

    __tablename__ = "market_scan_runs"

    worker_name: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), default="success", nullable=False)
    symbols_scanned: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    setups_detected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(nullable=True)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)


class SetupDetectionRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A persisted setup detection from the deterministic analysis engine."""

    __tablename__ = "setup_detections"

    scan_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("market_scan_runs.id"), nullable=True
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True
    )
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    setup_name: Mapped[str] = mapped_column(String(64), nullable=False)
    direction: Mapped[str | None] = mapped_column(String(8), nullable=True)
    confidence: Mapped[float] = mapped_column(default=0.0, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    detected_metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# --------------------------------------------------------------------------- #
# Exchange demo execution (Slice 61) — paper_exchange_demo only, never live
# --------------------------------------------------------------------------- #


class ExchangeOrder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An order mirrored to the BloFin *demo* venue.

    ``exchange_mode`` is always ``paper_exchange_demo`` for rows created in this
    scaffold. ``internal_order_id`` links back to the paper :class:`Order`.
    """

    __tablename__ = "exchange_orders"

    internal_order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("orders.id"), nullable=True
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True
    )
    exchange: Mapped[str] = mapped_column(String(40), nullable=False)
    exchange_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    inst_id: Mapped[str] = mapped_column(String(40), nullable=False)
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    order_type: Mapped[str] = mapped_column(String(16), nullable=False)
    size: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    exchange_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    venue_client_order_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="submitted", nullable=False)
    filled_size: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=Decimal("0"))
    average_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)


class ExchangeFill(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A fill recorded against an :class:`ExchangeOrder` (demo venue)."""

    __tablename__ = "exchange_fills"

    exchange_order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exchange_orders.id"), nullable=False
    )
    fill_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    size: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    fee: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=Decimal("0"))
    fee_currency: Mapped[str | None] = mapped_column(String(16), nullable=True)


# --------------------------------------------------------------------------- #
# Performance analytics (Slice 62)
# --------------------------------------------------------------------------- #


class PerformanceSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A point-in-time account-level performance aggregate.

    Headline metrics are stored as columns for cheap querying; the full payload
    (breakdowns, equity curve) lives in ``metrics`` JSON.
    """

    __tablename__ = "performance_snapshots"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    scope: Mapped[str] = mapped_column(String(32), default="account", nullable=False)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    trade_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    net_pnl: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal("0"), nullable=False)
    gross_profit: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal("0"), nullable=False)
    gross_loss: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal("0"), nullable=False)
    total_fees: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal("0"), nullable=False)
    total_funding: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal("0"), nullable=False)
    win_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    profit_factor: Mapped[float | None] = mapped_column(Float, nullable=True)
    expectancy: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal("0"), nullable=False)
    avg_r_multiple: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_drawdown: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal("0"), nullable=False)
    max_drawdown_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)


class StrategyPerformanceDaily(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Per-strategy, per-day performance rollup (idempotent on the natural key)."""

    __tablename__ = "strategy_performance_daily"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "strategy_id",
            "day",
            name="uq_strategy_perf_daily_org_strategy_day",
        ),
    )

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True
    )
    strategy_id: Mapped[str] = mapped_column(String(64), default="unknown", nullable=False)
    day: Mapped[date_type] = mapped_column(Date, nullable=False)
    trade_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    net_pnl: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal("0"), nullable=False)
    win_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    profit_factor: Mapped[float | None] = mapped_column(Float, nullable=True)
    expectancy: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal("0"), nullable=False)
    max_drawdown: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal("0"), nullable=False)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)

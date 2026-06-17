"""Dashboard summary schemas (Slice 44 — paper-only, deterministic)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.schemas.common import PaperAlertSeverity, PaperAlertType, StrictModel


class DashboardSafetyStatus(StrictModel):
    execution_mode: str
    paper_only: bool = True
    real_trading_enabled: bool = False
    real_trading_disabled: bool = True


class DailyDisciplineSnapshot(StrictModel):
    date: date
    timezone: str
    trades_today: int = 0
    paper_trades_opened_today: int = 0
    paper_trades_closed_today: int = 0
    journal_entries_today: int = 0
    realized_pnl_today_paper: Decimal | None = None
    unrealized_pnl_paper: Decimal | None = None
    net_pnl_today_paper: Decimal | None = None
    daily_loss_limit: Decimal | None = None
    daily_target: Decimal | None = None
    loss_lock_active: bool = False
    green_day_protection_active: bool = False
    overtrading_warning_active: bool = False
    max_trades_per_day: int | None = None
    remaining_trades_allowed: int | None = None
    discipline_status: str = Field(
        description="One of: calm, caution, locked, review_only",
        default="calm",
    )
    risk_settings_source: str = Field(
        default="system_default",
        description="One of: configured_daily_state, user_risk_settings, system_default",
    )
    pnl_sources: dict[str, Decimal | None] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)
    recommended_action: str = ""
    limitations: list[str] = Field(default_factory=list)


class DisciplineScoreSummary(StrictModel):
    score: int | None = None
    grade: str | None = None
    band: str | None = Field(
        default=None,
        description="One of: strong, good, caution, review_needed",
    )
    main_contributors: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class OpenPaperTradesSummary(StrictModel):
    proposal_flow_count: int = 0
    paper_validation_count: int = 0
    total_count: int = 0
    total_open_exposure: Decimal | None = None
    items: list[OpenPaperTradeItem] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class OpenPaperTradeItem(StrictModel):
    position_id: UUID | None = None
    paper_trade_id: UUID | None = None
    strategy_id: UUID | None = None
    strategy_name: str | None = None
    symbol: str
    direction: str
    unrealized_pnl: Decimal | None = None
    status: str = "open"
    source: str = Field(description="proposal_flow or paper_validation")


class StrategyReadinessCounts(StrictModel):
    needs_structure: int = 0
    ready_for_backtest: int = 0
    needs_more_sample: int = 0
    paper_eligible: int = 0
    paper_validation_running: int = 0
    paper_validated: int = 0
    restricted: int = 0


class StrategyActionItem(StrictModel):
    strategy_id: UUID
    name: str
    status: str
    next_action: str
    blockers: list[str] = Field(default_factory=list)
    link_hint: str = "/strategy-lab"


class StrategyReadinessSummary(StrictModel):
    counts: StrategyReadinessCounts
    top_needing_action: list[StrategyActionItem] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ActivePaperValidationItem(StrictModel):
    strategy_id: UUID
    name: str
    status: str = "running"


class AlertSummaryItem(StrictModel):
    alert_type: PaperAlertType
    severity: PaperAlertSeverity
    message: str


class AlertsLessonsSummary(StrictModel):
    unread_alerts: int = 0
    latest_high_priority: list[AlertSummaryItem] = Field(default_factory=list)
    pending_lessons: int = 0
    accepted_lessons: int = 0
    top_pending_lessons: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class MarketWatcherDashboardStatus(StrictModel):
    effective_enabled: bool = False
    last_scan_at: str | None = None
    fresh_observations: int = 0
    limitations: list[str] = Field(default_factory=list)


class BridgeDashboardStatus(StrictModel):
    effective_enabled: bool = False
    last_tick_at: str | None = None
    scans_triggered_last_tick: int = 0
    limitations: list[str] = Field(default_factory=list)


class NextRecommendedAction(StrictModel):
    action: str
    reason: str
    link: str = "/"
    priority: int = 10


class DashboardSummary(StrictModel):
    safety: DashboardSafetyStatus
    daily_discipline: DailyDisciplineSnapshot | None = None
    discipline_score: DisciplineScoreSummary | None = None
    strategy_readiness: StrategyReadinessSummary | None = None
    active_paper_validations: list[ActivePaperValidationItem] = Field(default_factory=list)
    open_paper_trades: list[OpenPaperTradeItem] = Field(default_factory=list)
    open_paper_trades_summary: OpenPaperTradesSummary | None = None
    alerts_lessons: AlertsLessonsSummary | None = None
    market_watcher: MarketWatcherDashboardStatus | None = None
    bridge: BridgeDashboardStatus | None = None
    next_recommended_action: NextRecommendedAction
    limitations: list[str] = Field(default_factory=list)

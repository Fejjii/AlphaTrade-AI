"""Daily discipline snapshot — paper data only, timezone-aware day boundaries."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.models import DailyRiskState as DailyRiskStateModel
from app.db.models import PaperTrade, Position, TradeJournal, User, UserRiskSettings
from app.schemas.common import PaperTradeStatus, PositionStatus
from app.schemas.dashboard import DailyDisciplineSnapshot
from app.services.risk.settings_service import (
    SYSTEM_RISK_DEFAULTS,
    RiskSettingsService,
    normalize_timezone,
)


@dataclass(frozen=True)
class DayWindow:
    date: date
    timezone: str
    start_utc: datetime
    end_utc: datetime
    timezone_fallback: bool = False


def resolve_day_window(timezone_name: str | None) -> DayWindow:
    tz_label, fallback = normalize_timezone(timezone_name)
    tz = ZoneInfo(tz_label)
    now_local = datetime.now(tz)
    start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    end_local = start_local + timedelta(days=1)
    return DayWindow(
        date=start_local.date(),
        timezone=tz_label,
        start_utc=start_local.astimezone(UTC),
        end_utc=end_local.astimezone(UTC),
        timezone_fallback=fallback,
    )


@dataclass(frozen=True)
class ResolvedRiskSettings:
    daily_loss_limit: Decimal | None = None
    daily_target: Decimal | None = None
    max_trades_per_day: int | None = None
    green_day_protection_enabled: bool = True
    one_loss_stop_enabled: bool = False
    overtrading_guard_enabled: bool = True
    loss_lock_from_state: bool = False
    source: str = "system_default"


def _load_risk_settings(
    session: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    day: date,
    risk_settings: RiskSettingsService | None = None,
) -> ResolvedRiskSettings:
    daily_row = session.scalar(
        select(DailyRiskStateModel).where(
            DailyRiskStateModel.organization_id == organization_id,
            DailyRiskStateModel.user_id == user_id,
            DailyRiskStateModel.day == day,
        )
    )
    if daily_row is not None:
        return ResolvedRiskSettings(
            daily_loss_limit=daily_row.daily_loss_limit,
            daily_target=daily_row.daily_target,
            max_trades_per_day=daily_row.max_trades_per_day,
            loss_lock_from_state=daily_row.locked,
            source="configured_daily_state",
        )

    settings_row = session.scalar(
        select(UserRiskSettings).where(
            UserRiskSettings.organization_id == organization_id,
            UserRiskSettings.user_id == user_id,
        )
    )
    if settings_row is not None:
        if risk_settings is not None:
            risk_settings.ensure_daily_risk_state(
                organization_id=organization_id,
                user_id=user_id,
                day=day,
            )
        return ResolvedRiskSettings(
            daily_loss_limit=settings_row.daily_loss_limit,
            daily_target=settings_row.daily_target,
            max_trades_per_day=settings_row.max_trades_per_day,
            green_day_protection_enabled=settings_row.green_day_protection_enabled,
            one_loss_stop_enabled=settings_row.one_loss_stop_enabled,
            overtrading_guard_enabled=settings_row.overtrading_guard_enabled,
            source="user_risk_settings",
        )

    defaults = SYSTEM_RISK_DEFAULTS
    return ResolvedRiskSettings(
        daily_loss_limit=defaults.daily_loss_limit,
        daily_target=defaults.daily_target,
        max_trades_per_day=defaults.max_trades_per_day,
        green_day_protection_enabled=defaults.green_day_protection_enabled,
        one_loss_stop_enabled=defaults.one_loss_stop_enabled,
        overtrading_guard_enabled=defaults.overtrading_guard_enabled,
        source="system_default",
    )


def _sum_closed_paper_trade_pnl(
    session: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    window: DayWindow,
) -> Decimal:
    value = session.scalar(
        select(func.coalesce(func.sum(PaperTrade.net_pnl), 0)).where(
            PaperTrade.organization_id == organization_id,
            PaperTrade.user_id == user_id,
            PaperTrade.status == PaperTradeStatus.CLOSED,
            PaperTrade.exit_time.is_not(None),
            PaperTrade.exit_time >= window.start_utc,
            PaperTrade.exit_time < window.end_utc,
        )
    )
    return Decimal(str(value or 0))


def _sum_closed_proposal_position_pnl(
    session: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    window: DayWindow,
) -> Decimal:
    value = session.scalar(
        select(func.coalesce(func.sum(Position.realized_pnl), 0)).where(
            Position.organization_id == organization_id,
            Position.user_id == user_id,
            Position.status == PositionStatus.CLOSED,
            Position.closed_at.is_not(None),
            Position.closed_at >= window.start_utc,
            Position.closed_at < window.end_utc,
        )
    )
    return Decimal(str(value or 0))


def _sum_open_unrealized_positions(
    session: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Decimal:
    rows = session.scalars(
        select(Position.unrealized_pnl).where(
            Position.organization_id == organization_id,
            Position.user_id == user_id,
            Position.status == PositionStatus.OPEN,
        )
    ).all()
    if not rows:
        return Decimal("0")
    return sum((Decimal(str(v or 0)) for v in rows), Decimal("0"))


def _count_losing_closed_trades_today(
    session: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    window: DayWindow,
) -> int:
    paper_losses = int(
        session.scalar(
            select(func.count())
            .select_from(PaperTrade)
            .where(
                PaperTrade.organization_id == organization_id,
                PaperTrade.user_id == user_id,
                PaperTrade.status == PaperTradeStatus.CLOSED,
                PaperTrade.exit_time.is_not(None),
                PaperTrade.exit_time >= window.start_utc,
                PaperTrade.exit_time < window.end_utc,
                PaperTrade.net_pnl < 0,
            )
        )
        or 0
    )
    position_losses = int(
        session.scalar(
            select(func.count())
            .select_from(Position)
            .where(
                Position.organization_id == organization_id,
                Position.user_id == user_id,
                Position.status == PositionStatus.CLOSED,
                Position.closed_at.is_not(None),
                Position.closed_at >= window.start_utc,
                Position.closed_at < window.end_utc,
                Position.realized_pnl < 0,
            )
        )
        or 0
    )
    return paper_losses + position_losses


def _count_paper_trades_opened(
    session: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    window: DayWindow,
) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(PaperTrade)
            .where(
                PaperTrade.organization_id == organization_id,
                PaperTrade.user_id == user_id,
                PaperTrade.entry_time.is_not(None),
                PaperTrade.entry_time >= window.start_utc,
                PaperTrade.entry_time < window.end_utc,
            )
        )
        or 0
    )


def _count_paper_trades_closed(
    session: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    window: DayWindow,
) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(PaperTrade)
            .where(
                PaperTrade.organization_id == organization_id,
                PaperTrade.user_id == user_id,
                PaperTrade.status == PaperTradeStatus.CLOSED,
                PaperTrade.exit_time.is_not(None),
                PaperTrade.exit_time >= window.start_utc,
                PaperTrade.exit_time < window.end_utc,
            )
        )
        or 0
    )


def _count_journal_entries(
    session: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    window: DayWindow,
) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(TradeJournal)
            .where(
                TradeJournal.organization_id == organization_id,
                TradeJournal.user_id == user_id,
                TradeJournal.created_at >= window.start_utc,
                TradeJournal.created_at < window.end_utc,
            )
        )
        or 0
    )


def _resolve_discipline_status(
    *,
    loss_lock: bool,
    green_day: bool,
    overtrading: bool,
) -> str:
    if loss_lock:
        return "locked"
    if green_day or overtrading:
        return "caution"
    return "calm"


def build_daily_discipline_snapshot(
    session: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    risk_settings: RiskSettingsService | None = None,
) -> DailyDisciplineSnapshot:
    limitations: list[str] = []
    user = session.get(User, user_id)
    settings_row = session.scalar(
        select(UserRiskSettings).where(
            UserRiskSettings.organization_id == organization_id,
            UserRiskSettings.user_id == user_id,
        )
    )
    tz_source = (
        settings_row.timezone if settings_row is not None else (user.timezone if user else "UTC")
    )
    window = resolve_day_window(tz_source)
    if window.timezone_fallback:
        limitations.append("Invalid timezone; defaulted to UTC for day boundaries.")

    risk = _load_risk_settings(
        session,
        organization_id=organization_id,
        user_id=user_id,
        day=window.date,
        risk_settings=risk_settings,
    )

    if risk.source == "system_default":
        limitations.append(
            "Risk limits use system defaults; configure Risk Settings for personalized limits."
        )
    elif risk.source == "user_risk_settings":
        limitations.append("Daily risk state initialized from user risk settings for today.")

    opened = _count_paper_trades_opened(
        session, organization_id=organization_id, user_id=user_id, window=window
    )
    closed = _count_paper_trades_closed(
        session, organization_id=organization_id, user_id=user_id, window=window
    )
    journal_entries = _count_journal_entries(
        session, organization_id=organization_id, user_id=user_id, window=window
    )

    trades_today = int(
        session.scalar(
            select(func.count())
            .select_from(PaperTrade)
            .where(
                PaperTrade.organization_id == organization_id,
                PaperTrade.user_id == user_id,
                or_(
                    (
                        PaperTrade.entry_time.is_not(None)
                        & (PaperTrade.entry_time >= window.start_utc)
                        & (PaperTrade.entry_time < window.end_utc)
                    ),
                    (
                        PaperTrade.exit_time.is_not(None)
                        & (PaperTrade.exit_time >= window.start_utc)
                        & (PaperTrade.exit_time < window.end_utc)
                    ),
                ),
            )
        )
        or 0
    )

    realized_paper = _sum_closed_paper_trade_pnl(
        session, organization_id=organization_id, user_id=user_id, window=window
    )
    realized_positions = _sum_closed_proposal_position_pnl(
        session, organization_id=organization_id, user_id=user_id, window=window
    )
    realized = realized_paper + realized_positions
    unrealized_positions = _sum_open_unrealized_positions(
        session, organization_id=organization_id, user_id=user_id
    )
    unrealized: Decimal | None = unrealized_positions
    pnl_sources = {
        "paper_validation_closed": realized_paper,
        "proposal_flow_closed": realized_positions,
        "proposal_flow_open_unrealized": unrealized_positions,
    }

    net: Decimal | None = realized + unrealized if unrealized is not None else realized

    daily_loss_limit = risk.daily_loss_limit
    daily_target = risk.daily_target
    max_trades = risk.max_trades_per_day

    if daily_target is None and risk.source == "system_default":
        limitations.append("daily_target is not configured.")
    if daily_loss_limit is None:
        limitations.append("daily_loss_limit is not configured; loss lock uses one-loss stop only.")

    pnl_for_risk = net if net is not None else realized
    loss_lock = risk.loss_lock_from_state

    if not loss_lock and daily_loss_limit is not None and pnl_for_risk <= -daily_loss_limit:
        loss_lock = True

    if (
        not loss_lock
        and risk.one_loss_stop_enabled
        and _count_losing_closed_trades_today(
            session,
            organization_id=organization_id,
            user_id=user_id,
            window=window,
        )
        >= 1
    ):
        loss_lock = True

    green_day = False
    if (
        risk.green_day_protection_enabled
        and daily_target is not None
        and pnl_for_risk >= daily_target
    ):
        green_day = True

    overtrading = (
        risk.overtrading_guard_enabled and max_trades is not None and trades_today >= max_trades
    )

    remaining: int | None = None
    if max_trades is not None:
        remaining = max(0, max_trades - trades_today)

    reasons: list[str] = []
    if loss_lock:
        if risk.loss_lock_from_state:
            reasons.append("Daily risk state is locked for paper trading today.")
        elif risk.one_loss_stop_enabled and daily_loss_limit is None:
            reasons.append("One-loss stop is active after a losing paper trade today.")
        else:
            reasons.append("Daily loss limit reached for paper trading today.")
    if green_day:
        reasons.append("Daily target reached — green-day protection is active.")
    if overtrading:
        reasons.append("Trade count is at or above today's frequency threshold.")

    status = _resolve_discipline_status(
        loss_lock=loss_lock,
        green_day=green_day,
        overtrading=overtrading,
    )
    if status == "locked":
        recommended = "Step back and review today's paper results before taking more risk."
    elif status == "caution":
        recommended = "Move deliberately — protective signals are active for paper trading today."
    else:
        recommended = "Stay patient and wait for setups that match your plan."

    return DailyDisciplineSnapshot(
        date=window.date,
        timezone=window.timezone,
        trades_today=trades_today,
        paper_trades_opened_today=opened,
        paper_trades_closed_today=closed,
        journal_entries_today=journal_entries,
        realized_pnl_today_paper=realized,
        unrealized_pnl_paper=unrealized,
        net_pnl_today_paper=net,
        daily_loss_limit=daily_loss_limit,
        daily_target=daily_target,
        loss_lock_active=loss_lock,
        green_day_protection_active=green_day,
        overtrading_warning_active=overtrading,
        max_trades_per_day=max_trades,
        remaining_trades_allowed=remaining,
        discipline_status=status,
        risk_settings_source=risk.source,
        pnl_sources=pnl_sources,
        reasons=reasons,
        recommended_action=recommended,
        limitations=limitations,
    )

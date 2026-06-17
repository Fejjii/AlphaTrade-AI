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
from app.db.models import PaperTrade, Position, TradeJournal, User
from app.schemas.common import PaperTradeStatus, PositionStatus
from app.schemas.dashboard import DailyDisciplineSnapshot
from app.services.risk.limits import RiskLimits


@dataclass(frozen=True)
class DayWindow:
    date: date
    timezone: str
    start_utc: datetime
    end_utc: datetime
    timezone_fallback: bool = False


def resolve_day_window(timezone_name: str | None) -> DayWindow:
    tz_label = (timezone_name or "UTC").strip() or "UTC"
    fallback = False
    try:
        tz = ZoneInfo(tz_label)
    except Exception:
        tz = ZoneInfo("UTC")
        tz_label = "UTC"
        fallback = True

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
    loss_lock_from_state: bool = False
    configured: bool = False


def _load_risk_settings(
    session: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    day: date,
) -> ResolvedRiskSettings:
    row = session.scalar(
        select(DailyRiskStateModel).where(
            DailyRiskStateModel.organization_id == organization_id,
            DailyRiskStateModel.user_id == user_id,
            DailyRiskStateModel.day == day,
        )
    )
    if row is None:
        return ResolvedRiskSettings()
    return ResolvedRiskSettings(
        daily_loss_limit=row.daily_loss_limit,
        daily_target=row.daily_target,
        max_trades_per_day=row.max_trades_per_day,
        loss_lock_from_state=row.locked,
        configured=True,
    )


def _sum_closed_paper_pnl(
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


def _sum_open_unrealized(
    session: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Decimal | None:
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
) -> DailyDisciplineSnapshot:
    limitations: list[str] = []
    user = session.get(User, user_id)
    window = resolve_day_window(user.timezone if user else "UTC")
    if window.timezone_fallback:
        limitations.append("Invalid user timezone; defaulted to UTC for day boundaries.")

    risk = _load_risk_settings(
        session,
        organization_id=organization_id,
        user_id=user_id,
        day=window.date,
    )

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

    realized = _sum_closed_paper_pnl(
        session, organization_id=organization_id, user_id=user_id, window=window
    )
    unrealized = _sum_open_unrealized(session, organization_id=organization_id, user_id=user_id)
    net: Decimal | None = None
    if unrealized is not None:
        net = realized + unrealized
    else:
        limitations.append("Unrealized paper PnL unavailable; net PnL falls back to realized only.")
        net = realized

    daily_loss_limit = risk.daily_loss_limit
    daily_target = risk.daily_target
    max_trades = risk.max_trades_per_day

    if not risk.configured:
        limitations.append("No daily risk settings row for today; limits are not configured.")
    if daily_target is None:
        limitations.append("daily_target is not configured for this tenant.")
    if max_trades is None:
        engine_default = RiskLimits().max_trades_per_day
        max_trades = engine_default
        limitations.append(
            f"max_trades_per_day uses engine default ({engine_default}); not user-configured."
        )

    pnl_for_risk = net if net is not None else realized
    loss_lock = risk.loss_lock_from_state
    if not loss_lock and daily_loss_limit is not None and pnl_for_risk <= -daily_loss_limit:
        loss_lock = True

    green_day = False
    if daily_target is not None and pnl_for_risk >= daily_target:
        green_day = True

    overtrading = max_trades is not None and trades_today >= max_trades

    remaining: int | None = None
    if max_trades is not None:
        remaining = max(0, max_trades - trades_today)

    reasons: list[str] = []
    if loss_lock:
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
        reasons=reasons,
        recommended_action=recommended,
        limitations=limitations,
    )

"""Authoritative DailyRiskState sync for paper execution (AT-012).

Reads portfolio/order facts from the database, writes them through to
``DailyRiskState``, and never trusts client-supplied risk counters.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import DailyRiskState, Order, Position
from app.schemas.common import ExecutionMode, OrderStatus, PositionStatus
from app.services.risk.settings_service import RiskSettingsService, normalize_timezone


@dataclass(frozen=True)
class AuthoritativeDailySnapshot:
    """Server-computed daily risk inputs for execution-time evaluation."""

    day: date
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    open_exposure_notional: Decimal
    trade_count: int
    daily_locked: bool
    daily_loss_limit: Decimal | None
    max_trades_per_day: int | None
    account_equity: Decimal
    row: DailyRiskState


class DailyRiskAccounting:
    """Compute and persist daily risk state from paper portfolio facts."""

    def __init__(self, session: Session, risk_settings: RiskSettingsService) -> None:
        self._session = session
        self._settings = risk_settings

    @property
    def risk_settings(self) -> RiskSettingsService:
        return self._settings

    def resolve_day(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> tuple[date, str]:
        user_settings = self._settings.get(
            organization_id=organization_id,
            user_id=user_id,
        )
        tz_name, _ = normalize_timezone(user_settings.timezone)
        try:
            today = datetime.now(UTC).astimezone(ZoneInfo(tz_name)).date()
        except Exception:
            today = date.today()
            tz_name = "UTC"
        return today, tz_name

    def sync_from_portfolio(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        day: date | None = None,
        timezone_name: str | None = None,
    ) -> AuthoritativeDailySnapshot:
        """Recompute daily counters from orders/positions and persist DailyRiskState."""
        user_settings = self._settings.get(
            organization_id=organization_id,
            user_id=user_id,
        )
        if day is None or timezone_name is None:
            day, timezone_name = self.resolve_day(
                organization_id=organization_id,
                user_id=user_id,
            )

        start_utc, end_utc = _day_bounds_utc(day, timezone_name)
        realized = self._sum_realized_closed(
            organization_id=organization_id,
            user_id=user_id,
            start_utc=start_utc,
            end_utc=end_utc,
        )
        trade_count = self._count_paper_fills(
            organization_id=organization_id,
            user_id=user_id,
            start_utc=start_utc,
            end_utc=end_utc,
        )
        open_exposure, unrealized = self._open_position_totals(
            organization_id=organization_id,
            user_id=user_id,
        )

        row = self._settings.ensure_daily_risk_state(
            organization_id=organization_id,
            user_id=user_id,
            day=day,
        )
        assert row is not None  # ensure always creates after AT-012

        daily_loss_limit = (
            user_settings.daily_loss_limit
            if user_settings.daily_loss_limit is not None
            else row.daily_loss_limit
        )
        row.daily_loss_limit = user_settings.daily_loss_limit
        row.daily_target = user_settings.daily_target
        row.max_trades_per_day = user_settings.max_trades_per_day
        row.realized_pnl = realized
        row.unrealized_pnl = unrealized
        row.trade_count = trade_count

        if daily_loss_limit is not None and realized <= -daily_loss_limit:
            row.locked = True

        self._session.flush()

        # Paper account equity: starting balance ± realized/unrealized (server-side only).
        account_equity = user_settings.default_account_balance + realized + unrealized

        return AuthoritativeDailySnapshot(
            day=day,
            realized_pnl=realized,
            unrealized_pnl=unrealized,
            open_exposure_notional=open_exposure,
            trade_count=trade_count,
            daily_locked=bool(row.locked),
            daily_loss_limit=daily_loss_limit,
            max_trades_per_day=user_settings.max_trades_per_day,
            account_equity=account_equity,
            row=row,
        )

    def record_after_paper_fill(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> AuthoritativeDailySnapshot:
        """Refresh DailyRiskState immediately after an accepted paper fill."""
        return self.sync_from_portfolio(
            organization_id=organization_id,
            user_id=user_id,
        )

    def record_after_position_close(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> AuthoritativeDailySnapshot:
        """Refresh DailyRiskState after a paper position close (realized PnL)."""
        return self.sync_from_portfolio(
            organization_id=organization_id,
            user_id=user_id,
        )

    def _sum_realized_closed(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        start_utc: datetime,
        end_utc: datetime,
    ) -> Decimal:
        value = self._session.scalar(
            select(func.coalesce(func.sum(Position.realized_pnl), 0)).where(
                Position.organization_id == organization_id,
                Position.user_id == user_id,
                Position.status == PositionStatus.CLOSED,
                Position.closed_at.is_not(None),
                Position.closed_at >= start_utc,
                Position.closed_at < end_utc,
            )
        )
        return Decimal(str(value or 0))

    def _count_paper_fills(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        start_utc: datetime,
        end_utc: datetime,
    ) -> int:
        value = self._session.scalar(
            select(func.count())
            .select_from(Order)
            .where(
                Order.organization_id == organization_id,
                Order.user_id == user_id,
                Order.mode == ExecutionMode.PAPER,
                Order.status == OrderStatus.FILLED,
                Order.created_at >= start_utc,
                Order.created_at < end_utc,
            )
        )
        return int(value or 0)

    def _open_position_totals(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> tuple[Decimal, Decimal]:
        rows = list(
            self._session.scalars(
                select(Position).where(
                    Position.organization_id == organization_id,
                    Position.user_id == user_id,
                    Position.status == PositionStatus.OPEN,
                )
            ).all()
        )
        exposure = sum((r.size * r.entry_price for r in rows), Decimal("0"))
        unrealized = sum((r.unrealized_pnl for r in rows), Decimal("0"))
        return exposure, unrealized


def _day_bounds_utc(day: date, timezone_name: str) -> tuple[datetime, datetime]:
    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        tz = ZoneInfo("UTC")
    start_local = datetime(day.year, day.month, day.day, tzinfo=tz)
    start_utc = start_local.astimezone(UTC)
    end_utc = start_utc + timedelta(days=1)
    return start_utc, end_utc

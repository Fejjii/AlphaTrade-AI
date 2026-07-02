"""Unified paper portfolio performance service (Slice 91A).

Read-only aggregation over proposal-flow positions and paper-validation trades.
No execution, exchange, or automation paths.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import UserRiskSettings
from app.repositories.performance import PerformanceSnapshotRepository
from app.schemas.analytics import AnalyticsDateRange
from app.schemas.performance import (
    DailyPortfolioPointSchema,
    DollarEquityPointSchema,
    OpenExposureSummary,
    PaperPortfolioAccount,
    PaperPortfolioResponse,
    PaperPortfolioSafetyBanner,
    PerformanceSnapshotListResponse,
    PerformanceSnapshotResponse,
    PortfolioBreakdowns,
    PortfolioFiltersApplied,
    PortfolioTrend,
)
from app.services.performance.calculator import PerformanceCalculator
from app.services.performance.equity_calculator import PortfolioEquityCalculator
from app.services.performance.types import GroupBreakdown, TradeRecord
from app.services.performance.unified_trade import (
    PortfolioSourceFilter,
    PortfolioTradeFilters,
    UnifiedTradeLoader,
    UnifiedTradeRecord,
    closed_trades,
    open_trades,
)
from app.services.performance_service import _to_group_schemas, _to_metrics_schema
from app.services.risk.settings_service import SYSTEM_RISK_DEFAULTS, normalize_timezone

_ZERO = Decimal("0")
_OPEN_PAPER_VALIDATION_LIMITATION = (
    "Paper-validation open trades are excluded from unrealized PnL until "
    "mark-to-market is implemented."
)
_TREND_WINDOW_DAYS = 14
_MIN_TREND_TRADES = 5


class PaperPortfolioService:
    """Builds unified read-only paper portfolio responses."""

    def __init__(
        self,
        session: Session,
        *,
        calculator: PerformanceCalculator | None = None,
        equity_calculator: PortfolioEquityCalculator | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._session = session
        self._loader = UnifiedTradeLoader(session)
        self._snapshots = PerformanceSnapshotRepository(session)
        self._calc = calculator or PerformanceCalculator()
        self._equity = equity_calculator or PortfolioEquityCalculator()
        self._clock = clock

    def build_portfolio(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        start_date: date | None = None,
        end_date: date | None = None,
        source: PortfolioSourceFilter = PortfolioSourceFilter.ALL,
        symbol: str | None = None,
        setup: str | None = None,
        timeframe: str | None = None,
        timezone: str | None = None,
    ) -> PaperPortfolioResponse:
        tz_label, tz_fallback = normalize_timezone(timezone)
        filters = PortfolioTradeFilters(
            start_date=start_date,
            end_date=end_date,
            source=source,
            symbol=symbol,
            setup=setup,
            timeframe=timeframe,
            timezone=tz_label,
        )
        starting_balance = self._starting_balance(organization_id, user_id)
        records = self._loader.load(
            organization_id=organization_id,
            user_id=user_id,
            filters=filters,
        )
        closed = closed_trades(records)
        open_rows = open_trades(records)

        unrealized, unrealized_limits = self._unrealized(open_rows)
        equity_result = self._equity.build(
            starting_balance=starting_balance,
            records=records,
            unrealized_pnl=unrealized,
            as_of=self._clock(),
            timezone=tz_label,
            series_start=start_date,
            series_end=end_date,
        )
        current_equity = (
            starting_balance + equity_result.cumulative_realized_pnl + (unrealized or _ZERO)
        )

        limitations = list(unrealized_limits)
        if tz_fallback:
            limitations.append("Invalid timezone requested; defaulted to UTC.")
        if start_date is not None or end_date is not None:
            limitations.append(
                "Date filters apply to closed-trade metrics; open positions reflect current state."
            )

        trade_records = [t.to_trade_record() for t in closed]
        metrics = _to_metrics_schema(self._calc.calculate(trade_records))
        metrics = metrics.model_copy(
            update={
                "max_drawdown": equity_result.max_drawdown,
                "max_drawdown_pct": equity_result.max_drawdown_pct,
            }
        )

        return PaperPortfolioResponse(
            safety=PaperPortfolioSafetyBanner(),
            account=PaperPortfolioAccount(
                starting_balance=starting_balance,
                current_equity=current_equity,
                cumulative_realized_pnl=equity_result.cumulative_realized_pnl,
                unrealized_pnl=unrealized,
                open_trade_count=len(open_rows),
                closed_trade_count=len(closed),
                as_of=self._clock(),
                limitations=limitations,
            ),
            metrics=metrics,
            open_exposure=self._open_exposure(open_rows),
            equity_curve=[
                DollarEquityPointSchema(
                    index=p.index,
                    timestamp=p.timestamp,
                    equity=p.equity,
                    cumulative_realized_pnl=p.cumulative_realized_pnl,
                    unrealized_pnl=p.unrealized_pnl,
                    event=p.event,  # type: ignore[arg-type]
                )
                for p in equity_result.equity_curve
            ],
            daily_series=[
                DailyPortfolioPointSchema.model_validate(p) for p in equity_result.daily_series
            ],
            breakdowns=self._breakdowns(closed),
            trend=self._trend(closed, tz_label),
            date_range=AnalyticsDateRange(start=start_date, end=end_date)
            if start_date or end_date
            else None,
            filters_applied=PortfolioFiltersApplied(
                start_date=start_date,
                end_date=end_date,
                source=source.value,
                symbol=symbol,
                setup=setup,
                timeframe=timeframe,
                timezone=tz_label,
            ),
        )

    def list_snapshots(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 50,
    ) -> PerformanceSnapshotListResponse:
        rows = self._snapshots.list_for_tenant(
            organization_id=organization_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            limit=min(max(limit, 1), 200),
        )
        items = [PerformanceSnapshotResponse.model_validate(row) for row in rows]
        return PerformanceSnapshotListResponse(items=items, total=len(items))

    def _starting_balance(self, organization_id: uuid.UUID, user_id: uuid.UUID) -> Decimal:
        row = self._session.scalar(
            select(UserRiskSettings).where(
                UserRiskSettings.organization_id == organization_id,
                UserRiskSettings.user_id == user_id,
            )
        )
        if row is not None:
            return row.default_account_balance
        return SYSTEM_RISK_DEFAULTS.default_account_balance

    @staticmethod
    def _unrealized(
        open_rows: list[UnifiedTradeRecord],
    ) -> tuple[Decimal | None, list[str]]:
        limitations: list[str] = []
        has_open_validation = any(
            r.execution_lane is PortfolioSourceFilter.PAPER_VALIDATION for r in open_rows
        )
        if has_open_validation:
            limitations.append(_OPEN_PAPER_VALIDATION_LIMITATION)

        values = [
            r.unrealized_pnl
            for r in open_rows
            if r.execution_lane is PortfolioSourceFilter.PROPOSAL_FLOW
            and r.unrealized_pnl is not None
        ]
        if not open_rows:
            return None, limitations
        if not values and has_open_validation:
            return None, limitations
        return sum(values, _ZERO), limitations

    @staticmethod
    def _open_exposure(open_rows: list[UnifiedTradeRecord]) -> OpenExposureSummary:
        proposal = [r for r in open_rows if r.execution_lane is PortfolioSourceFilter.PROPOSAL_FLOW]
        validation = [
            r for r in open_rows if r.execution_lane is PortfolioSourceFilter.PAPER_VALIDATION
        ]
        unrealized_values = [r.unrealized_pnl for r in proposal if r.unrealized_pnl is not None]
        notional = _ZERO
        for row in open_rows:
            if row.size is not None and row.entry_price is not None:
                notional += abs(row.size * row.entry_price)
        limitations: list[str] = []
        if validation:
            limitations.append(_OPEN_PAPER_VALIDATION_LIMITATION)
        return OpenExposureSummary(
            open_trade_count=len(open_rows),
            proposal_flow_count=len(proposal),
            paper_validation_count=len(validation),
            unrealized_pnl_total=sum(unrealized_values, _ZERO) if unrealized_values else None,
            notional_exposure=notional if notional > _ZERO else None,
            limitations=limitations,
        )

    def _breakdowns(self, closed: list[UnifiedTradeRecord]) -> PortfolioBreakdowns:
        trade_records = [t.to_trade_record() for t in closed]
        return PortfolioBreakdowns(
            by_symbol=_to_group_schemas(self._calc.breakdown_by_symbol(trade_records)),
            by_setup=_to_group_schemas(
                self._breakdown_by_key(closed, lambda t: t.setup_key or "unknown")
            ),
            by_timeframe=_to_group_schemas(
                self._breakdown_by_key(closed, lambda t: t.timeframe or "unknown")
            ),
            by_strategy=_to_group_schemas(
                self._breakdown_by_key(closed, lambda t: t.strategy_key or "unknown")
            ),
            by_source=_to_group_schemas(
                self._breakdown_by_key(closed, lambda t: t.execution_lane.value)
            ),
            by_detector=_to_group_schemas(
                self._breakdown_by_key(
                    closed,
                    lambda t: (
                        (t.detector_condition or "unknown")
                        if t.execution_lane is PortfolioSourceFilter.PAPER_VALIDATION
                        else "n/a"
                    ),
                )
            ),
        )

    def _breakdown_by_key(
        self,
        closed: list[UnifiedTradeRecord],
        key_fn: Callable[[UnifiedTradeRecord], str],
    ) -> list[GroupBreakdown]:
        groups: dict[str, list[TradeRecord]] = {}
        for trade in closed:
            key = key_fn(trade) or "unknown"
            groups.setdefault(key, []).append(trade.to_trade_record())
        return [
            GroupBreakdown(key=key, metrics=self._calc.calculate(group))
            for key, group in sorted(groups.items())
        ]

    def _trend(self, closed: list[UnifiedTradeRecord], timezone: str) -> PortfolioTrend:
        if len(closed) < _MIN_TREND_TRADES:
            return PortfolioTrend(
                label="insufficient_data",
                window_days=_TREND_WINDOW_DAYS,
                rationale=f"Fewer than {_MIN_TREND_TRADES} closed trades in scope.",
            )

        tz = ZoneInfo(timezone)
        now = self._clock().astimezone(tz).date()
        recent_start = now - timedelta(days=_TREND_WINDOW_DAYS - 1)
        prior_start = now - timedelta(days=_TREND_WINDOW_DAYS * 2 - 1)
        prior_end = recent_start - timedelta(days=1)

        recent = _ZERO
        prior = _ZERO
        for trade in closed:
            if trade.closed_at is None:
                continue
            day = trade.closed_at.astimezone(tz).date()
            if recent_start <= day <= now:
                recent += trade.realized_pnl
            elif prior_start <= day <= prior_end:
                prior += trade.realized_pnl

        if recent > prior * Decimal("1.05") and recent > _ZERO:
            label = "improving"
            rationale = (
                f"Recent {_TREND_WINDOW_DAYS}-day net PnL exceeds prior window by more than 5%."
            )
        elif prior > _ZERO and recent < prior * Decimal("0.95"):
            label = "deteriorating"
            rationale = (
                f"Recent {_TREND_WINDOW_DAYS}-day net PnL trails prior window by more than 5%."
            )
        else:
            label = "flat"
            rationale = f"Recent and prior {_TREND_WINDOW_DAYS}-day net PnL are within 5%."

        return PortfolioTrend(
            label=label,  # type: ignore[arg-type]
            window_days=_TREND_WINDOW_DAYS,
            recent_net_pnl=recent,
            prior_net_pnl=prior,
            rationale=rationale,
        )

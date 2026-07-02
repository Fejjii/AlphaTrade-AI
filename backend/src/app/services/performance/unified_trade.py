"""Unified trade loader for paper portfolio analytics (Slice 91A).

Merges proposal-flow :class:`Position` rows and paper-validation
:class:`PaperTrade` rows into normalized :class:`UnifiedTradeRecord` values.
Read-only — no execution or exchange I/O.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from enum import StrEnum
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PaperTrade, PaperValidationRun, Position, UserStrategy
from app.repositories.positions import PositionRepository
from app.schemas.common import PaperTradeStatus, PositionStatus
from app.services.performance.calculator import trade_record_from_human_flag
from app.services.performance.types import TradeRecord, TradeSource
from app.services.risk.settings_service import normalize_timezone

_ZERO = Decimal("0")


class PortfolioSourceFilter(StrEnum):
    ALL = "all"
    PROPOSAL_FLOW = "proposal_flow"
    PAPER_VALIDATION = "paper_validation"


@dataclass(frozen=True)
class PortfolioTradeFilters:
    start_date: date | None = None
    end_date: date | None = None
    source: PortfolioSourceFilter = PortfolioSourceFilter.ALL
    symbol: str | None = None
    setup: str | None = None
    timeframe: str | None = None
    timezone: str | None = None


@dataclass(frozen=True)
class UnifiedTradeRecord:
    """Normalized trade row spanning proposal-flow and paper-validation sources."""

    trade_id: uuid.UUID
    execution_lane: PortfolioSourceFilter
    status: str
    realized_pnl: Decimal
    unrealized_pnl: Decimal | None
    symbol: str | None
    setup_key: str | None
    strategy_key: str | None
    strategy_name: str | None
    timeframe: str | None
    detector_condition: str | None
    direction: str | None
    size: Decimal | None
    entry_price: Decimal | None
    fees: Decimal
    risk_amount: Decimal | None
    opened_at: datetime | None
    closed_at: datetime | None
    had_violation: bool = False

    def to_trade_record(self) -> TradeRecord:
        """Convert to Slice 62 :class:`TradeRecord` for closed-trade metrics."""
        source = (
            TradeSource.HUMAN
            if self.execution_lane is PortfolioSourceFilter.PAPER_VALIDATION
            else trade_record_from_human_flag(strategy_id=self.strategy_key)
        )
        return TradeRecord(
            realized_pnl=self.realized_pnl,
            symbol=self.symbol,
            strategy_id=self.strategy_key,
            timeframe=self.timeframe,
            direction=self.direction,
            size=self.size,
            fees=self.fees,
            funding=_ZERO,
            risk_amount=self.risk_amount,
            opened_at=self.opened_at,
            closed_at=self.closed_at,
            source=source,
            had_violation=self.had_violation,
        )


class UnifiedTradeLoader:
    """Loads tenant-scoped positions and paper trades for portfolio analytics."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._positions = PositionRepository(session)

    def load(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        filters: PortfolioTradeFilters | None = None,
    ) -> list[UnifiedTradeRecord]:
        filters = filters or PortfolioTradeFilters()
        records: list[UnifiedTradeRecord] = []

        if filters.source in (PortfolioSourceFilter.ALL, PortfolioSourceFilter.PROPOSAL_FLOW):
            records.extend(
                self._load_positions(
                    organization_id=organization_id,
                    user_id=user_id,
                    filters=filters,
                )
            )
        if filters.source in (PortfolioSourceFilter.ALL, PortfolioSourceFilter.PAPER_VALIDATION):
            records.extend(
                self._load_paper_trades(
                    organization_id=organization_id,
                    user_id=user_id,
                    filters=filters,
                )
            )

        return records

    def _load_positions(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        filters: PortfolioTradeFilters,
    ) -> list[UnifiedTradeRecord]:
        rows, _ = self._positions.list_positions(
            organization_id=organization_id,
            user_id=user_id,
            limit=10_000,
        )
        out: list[UnifiedTradeRecord] = []
        for row in rows:
            if filters.symbol and row.symbol != filters.symbol:
                continue
            setup_key = row.strategy_id.value if row.strategy_id is not None else None
            if filters.setup and setup_key != filters.setup:
                continue
            if filters.timeframe:
                continue

            is_closed = row.status == PositionStatus.CLOSED
            close_ts = row.closed_at
            if is_closed and not self._closed_in_range(close_ts, filters):
                continue

            risk_amount = _position_risk_amount(row)
            risk_state = row.risk_state or {}
            out.append(
                UnifiedTradeRecord(
                    trade_id=row.id,
                    execution_lane=PortfolioSourceFilter.PROPOSAL_FLOW,
                    status="closed" if is_closed else "open",
                    realized_pnl=row.realized_pnl or _ZERO,
                    unrealized_pnl=row.unrealized_pnl if not is_closed else None,
                    symbol=row.symbol,
                    setup_key=setup_key,
                    strategy_key=setup_key,
                    strategy_name=setup_key,
                    timeframe=None,
                    detector_condition=None,
                    direction=row.direction.value if row.direction is not None else None,
                    size=row.size,
                    entry_price=row.entry_price,
                    fees=_ZERO,
                    risk_amount=risk_amount,
                    opened_at=row.opened_at,
                    closed_at=close_ts,
                    had_violation=bool(risk_state.get("violation") or risk_state.get("violations")),
                )
            )
        return out

    def _load_paper_trades(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        filters: PortfolioTradeFilters,
    ) -> list[UnifiedTradeRecord]:
        stmt = (
            select(PaperTrade, PaperValidationRun, UserStrategy)
            .join(
                PaperValidationRun,
                PaperTrade.paper_validation_run_id == PaperValidationRun.id,
            )
            .join(UserStrategy, PaperTrade.strategy_id == UserStrategy.id)
            .where(
                PaperTrade.organization_id == organization_id,
                PaperTrade.user_id == user_id,
            )
            .order_by(PaperTrade.created_at.asc())
        )
        rows = self._session.execute(stmt).all()
        out: list[UnifiedTradeRecord] = []
        for paper_trade, run, strategy in rows:
            if filters.symbol and paper_trade.symbol != filters.symbol:
                continue
            if filters.timeframe and paper_trade.timeframe != filters.timeframe:
                continue
            strategy_key = str(strategy.id)
            setup_key = strategy.name
            if filters.setup and filters.setup not in (setup_key, strategy_key):
                continue

            is_closed = paper_trade.status == PaperTradeStatus.CLOSED
            close_ts = paper_trade.exit_time
            if is_closed and not self._closed_in_range(close_ts, filters):
                continue

            detector = _detector_from_run_config(run.config)
            risk_amount = _paper_trade_risk_amount(paper_trade)
            out.append(
                UnifiedTradeRecord(
                    trade_id=paper_trade.id,
                    execution_lane=PortfolioSourceFilter.PAPER_VALIDATION,
                    status="closed" if is_closed else "open",
                    realized_pnl=paper_trade.net_pnl or _ZERO,
                    unrealized_pnl=None,
                    symbol=paper_trade.symbol,
                    setup_key=setup_key,
                    strategy_key=strategy_key,
                    strategy_name=strategy.name,
                    timeframe=paper_trade.timeframe,
                    detector_condition=detector,
                    direction=paper_trade.direction.value
                    if paper_trade.direction is not None
                    else None,
                    size=paper_trade.size,
                    entry_price=paper_trade.entry_price,
                    fees=paper_trade.fees or _ZERO,
                    risk_amount=risk_amount,
                    opened_at=paper_trade.entry_time,
                    closed_at=close_ts,
                )
            )
        return out

    @staticmethod
    def _closed_in_range(
        closed_at: datetime | None,
        filters: PortfolioTradeFilters,
    ) -> bool:
        if closed_at is None:
            return False
        tz_label, _ = normalize_timezone(filters.timezone)
        tz = ZoneInfo(tz_label)
        local_close = closed_at.astimezone(tz).date()
        if filters.start_date is not None and local_close < filters.start_date:
            return False
        return filters.end_date is None or local_close <= filters.end_date


def closed_trades(records: list[UnifiedTradeRecord]) -> list[UnifiedTradeRecord]:
    return [r for r in records if r.status == "closed"]


def open_trades(records: list[UnifiedTradeRecord]) -> list[UnifiedTradeRecord]:
    return [r for r in records if r.status == "open"]


def date_range_bounds(
    start_date: date | None,
    end_date: date | None,
    *,
    timezone: str | None,
) -> tuple[datetime | None, datetime | None]:
    """Inclusive local-date bounds converted to UTC datetimes."""
    tz_label, _ = normalize_timezone(timezone)
    tz = ZoneInfo(tz_label)
    start_dt: datetime | None = None
    end_dt: datetime | None = None
    if start_date is not None:
        start_dt = datetime.combine(start_date, time.min, tzinfo=tz).astimezone(UTC)
    if end_date is not None:
        end_local = datetime.combine(end_date, time.max, tzinfo=tz)
        end_dt = (end_local + timedelta(microseconds=1)).astimezone(UTC)
    return start_dt, end_dt


def _position_risk_amount(position: Position) -> Decimal | None:
    if position.stop_loss is None or position.entry_price is None:
        return None
    distance = abs(position.entry_price - position.stop_loss)
    size = position.size or _ZERO
    risk = distance * size
    return risk if risk > _ZERO else None


def _paper_trade_risk_amount(trade: PaperTrade) -> Decimal | None:
    if trade.stop_loss is None or trade.entry_price is None or trade.size is None:
        return None
    distance = abs(trade.entry_price - trade.stop_loss)
    risk = distance * trade.size
    return risk if risk > _ZERO else None


def _detector_from_run_config(config: dict | None) -> str | None:
    if not config:
        return None
    condition = config.get("condition")
    if isinstance(condition, str) and condition.strip():
        return condition.strip()
    return None

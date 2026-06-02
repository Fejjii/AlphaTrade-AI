"""Position schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.schemas.common import (
    Leverage,
    ORMModel,
    PositionStatus,
    PositiveDecimal,
    StrategyId,
    StrictModel,
    Symbol,
    TradeDirection,
)
from app.schemas.proposal import TakeProfitLevel


class Position(ORMModel):
    """An open or historical position (paper in this scaffold)."""

    id: UUID
    organization_id: UUID
    user_id: UUID
    strategy_id: StrategyId | None = None
    linked_proposal_id: UUID | None = None
    symbol: Symbol
    direction: TradeDirection
    size: PositiveDecimal
    entry_price: PositiveDecimal
    leverage: Leverage
    stop_loss: Decimal | None = None
    take_profits: list[TakeProfitLevel] = Field(default_factory=list)
    liquidation_price: Decimal | None = None
    unrealized_pnl: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")
    risk_state: dict[str, str] = Field(default_factory=dict)
    status: PositionStatus = PositionStatus.OPEN
    opened_at: datetime
    closed_at: datetime | None = None

    @property
    def is_open(self) -> bool:
        return self.status is PositionStatus.OPEN


class PositionUpdate(StrictModel):
    stop_loss: Decimal | None = None
    take_profits: list[TakeProfitLevel] | None = None
    risk_state: dict[str, str] | None = None


class ClosePaperPositionRequest(StrictModel):
    exit_price: PositiveDecimal
    reason: str | None = Field(default=None, max_length=500)


class PaginatedPositions(StrictModel):
    items: list[Position]
    total: int
    limit: int
    offset: int

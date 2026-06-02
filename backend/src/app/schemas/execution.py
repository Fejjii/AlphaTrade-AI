"""Execution schemas. Paper orders only in this scaffold.

Real exchange execution is intentionally not represented here beyond the
idempotency contract. Execution requires a prior approval (Architecture §9).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.schemas.common import (
    ExecutionMode,
    OrderSide,
    OrderStatus,
    OrderType,
    ORMModel,
    PositiveDecimal,
    StrategyId,
    StrictModel,
    Symbol,
)


class PaperOrderRequest(StrictModel):
    """Request to place a paper order against an approved proposal."""

    proposal_id: UUID
    approval_id: UUID
    symbol: Symbol
    side: OrderSide
    type: OrderType
    size: PositiveDecimal
    price: Decimal | None = Field(default=None, description="Required for limit/stop_limit types.")
    reduce_only: bool = False
    idempotency_key: str = Field(min_length=8, max_length=128)


class PaperOrder(ORMModel):
    """A simulated order. ``mode`` is always ``paper`` in this scaffold."""

    id: UUID
    organization_id: UUID
    user_id: UUID
    strategy_id: StrategyId | None = None
    proposal_id: UUID | None = None
    approval_id: UUID | None = None
    mode: ExecutionMode = ExecutionMode.PAPER
    symbol: Symbol
    side: OrderSide
    type: OrderType
    size: PositiveDecimal
    price: Decimal | None = None
    status: OrderStatus = OrderStatus.PENDING
    reduce_only: bool = False
    idempotency_key: str
    exchange_order_id: str | None = None
    created_at: datetime


class PaginatedPaperOrders(StrictModel):
    items: list[PaperOrder]
    total: int
    limit: int
    offset: int

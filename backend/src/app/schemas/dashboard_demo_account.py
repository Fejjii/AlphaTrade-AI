"""Bounded presentation of the configured BloFin demo account."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.schemas.common import StrictModel


class DemoAccountBalance(StrictModel):
    asset: str
    total: Decimal
    available: Decimal


class DemoAccountPosition(StrictModel):
    symbol: str
    side: Literal["long", "short"]
    contracts: Decimal
    entry_price: Decimal | None = None
    mark_price: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    leverage: Decimal | None = None


class DashboardDemoAccount(StrictModel):
    venue: Literal["BLOFIN_DEMO"] = "BLOFIN_DEMO"
    read_only: Literal[True] = True
    status: Literal["ok", "degraded", "stale", "unavailable", "not_synced", "inactive"]
    can_refresh: bool = False
    snapshot_id: UUID | None = None
    synced_at: datetime | None = None
    expires_at: datetime | None = None
    balances: list[DemoAccountBalance] = Field(default_factory=list)
    positions: list[DemoAccountPosition] = Field(default_factory=list)
    balances_truncated: bool = False
    positions_truncated: bool = False
    position_count: int | None = None
    message: str

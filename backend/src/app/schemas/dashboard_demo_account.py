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
    equity: Decimal | None = None


class DemoAccountPosition(StrictModel):
    symbol: str
    side: Literal["long", "short"]
    contracts: Decimal
    base_asset: str | None = None
    quote_asset: str | None = None
    base_quantity: Decimal | None = None
    entry_price: Decimal | None = None
    mark_price: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    leverage: Decimal | None = None


class DemoAccountPerformance(StrictModel):
    status: Literal["partial", "unavailable"] = "unavailable"
    currency: Literal["USDT"] = "USDT"
    gross_pnl: Decimal | None = None
    fees: Decimal | None = None
    funding: Decimal | None = None
    net_pnl: Decimal | None = None
    verified_closed_trades: int = 0
    unresolved_trades: int = 0
    manual_test_trades: int = 0
    strategy_closed_trades: int | None = None
    coverage: str = "Verified performance is unavailable for this account."


class DashboardDemoAccount(StrictModel):
    venue: Literal["BLOFIN_DEMO"] = "BLOFIN_DEMO"
    read_only: Literal[True] = True
    account_id: UUID | None = None
    performance: DemoAccountPerformance = Field(default_factory=DemoAccountPerformance)
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
    total_equity_usd: Decimal | None = None
    refresh_error: str | None = None
    last_attempt_at: datetime | None = None
    message: str

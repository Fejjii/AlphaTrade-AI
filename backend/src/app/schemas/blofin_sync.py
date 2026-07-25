"""BloFin demo read-only synchronisation schemas (AT-037)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import BloFinSyncHealthStatus


class BloFinSyncBalanceItem(BaseModel):
    asset: str
    total: str
    available: str


class BloFinSyncPositionItem(BaseModel):
    symbol: str
    side: str | None = None
    size: str | None = None
    entry_price: str | None = None
    unrealized_pnl: str | None = None
    leverage: str | None = None
    margin_mode: str | None = None


class BloFinSyncSnapshotItem(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    user_id: uuid.UUID | None = None
    synced_at: datetime
    health_status: BloFinSyncHealthStatus
    provider: str
    exchange_mode: str
    account_snapshot: dict[str, Any] = Field(default_factory=dict)
    positions_snapshot: dict[str, Any] = Field(default_factory=dict)
    market_context: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
    is_stale: bool = False
    stale_reason: str | None = None
    error_summary: str | None = None
    position_count: int = 0
    balance_count: int = 0
    note: str = "BloFin demo read-only snapshot. Never places, modifies, or cancels orders."


class BloFinSyncResult(BaseModel):
    snapshot: BloFinSyncSnapshotItem
    note: str = "Read-only reconciliation complete. Live BloFin trading remains disabled."

"""Schemas for owner-scoped BloFin demo exchange probes (read-only + cancel)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.providers.base import ProviderStatus
from app.schemas.common import StrictModel


class ExchangeStatusResponse(StrictModel):
    """Redaction-safe exchange connectivity posture for operators."""

    exchange_mode: str
    execution_mode: str
    real_trading_enabled: bool
    blofin_demo_enabled: bool
    demo_active: bool
    api_key_configured: bool
    api_secret_configured: bool
    api_passphrase_configured: bool
    credentials_configured: bool
    provider: ProviderStatus | None = Field(
        default=None,
        description="Exchange provider health; never contains secrets.",
    )
    generated_at: datetime


class ExchangeInstrumentItem(StrictModel):
    """A tradable instrument with sizing fields needed for controlled demo orders."""

    symbol: str
    inst_id: str
    base_currency: str
    quote_currency: str
    instrument_type: str
    tick_size: Decimal | None = None
    lot_size: Decimal | None = None
    min_size: Decimal | None = None
    contract_size: Decimal | None = None
    active: bool = True


class ExchangeInstrumentsResponse(StrictModel):
    items: list[ExchangeInstrumentItem]
    generated_at: datetime


class ExchangeBalanceItem(StrictModel):
    asset: str
    total: Decimal
    available: Decimal


class ExchangeBalancesResponse(StrictModel):
    items: list[ExchangeBalanceItem]
    generated_at: datetime


class ExchangePositionItem(StrictModel):
    symbol: str
    inst_id: str
    side: str
    size: Decimal
    entry_price: Decimal | None = None
    mark_price: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    leverage: Decimal | None = None


class ExchangePositionsResponse(StrictModel):
    items: list[ExchangePositionItem]
    generated_at: datetime


class ExchangeOrderStatusResponse(StrictModel):
    inst_id: str
    exchange_order_id: str
    client_order_id: str | None = None
    status: str
    filled_size: Decimal
    average_price: Decimal | None = None
    generated_at: datetime


class ExchangeOrderCancelResponse(StrictModel):
    inst_id: str
    exchange_order_id: str
    cancelled: bool
    generated_at: datetime

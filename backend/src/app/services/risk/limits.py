"""Configurable risk limits used by deterministic rules."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class RiskLimits:
    """Thresholds for the risk engine. Tune via settings in a later slice."""

    max_leverage: Decimal = Decimal("10")
    max_position_pct_of_equity: Decimal = Decimal("5")  # notional cap as % of equity
    max_daily_loss_pct: Decimal = Decimal("3")
    max_weekly_loss_pct: Decimal = Decimal("8")
    extreme_funding_rate: Decimal = Decimal("0.01")  # 1% absolute
    min_volume_24h: Decimal = Decimal("1000000")
    max_trades_per_day: int = 20
    countertrend_max_leverage: Decimal = Decimal("3")
    volatile_alt_max_leverage: Decimal = Decimal("2")
    supported_symbols: frozenset[str] = frozenset(
        {"BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "BTC/USDT", "ETH/USDT"}
    )

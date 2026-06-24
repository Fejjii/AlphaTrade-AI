"""Symbol and timeframe mapping between the platform and BloFin."""

from __future__ import annotations

from app.schemas.common import Timeframe

# Ordered longest-first so ``USDT`` matches before ``USD``.
_QUOTE_CURRENCIES = ("USDT", "USDC", "USD", "BTC", "ETH", "EUR")

# Platform Timeframe -> BloFin candle ``bar`` parameter.
_TIMEFRAME_TO_BAR: dict[Timeframe, str] = {
    Timeframe.M1: "1m",
    Timeframe.M3: "3m",
    Timeframe.M5: "5m",
    Timeframe.M15: "15m",
    Timeframe.M30: "30m",
    Timeframe.H1: "1H",
    Timeframe.H2: "2H",
    Timeframe.H4: "4H",
    Timeframe.H6: "6H",
    Timeframe.H12: "12H",
    Timeframe.D1: "1D",
    Timeframe.D3: "3D",
    Timeframe.W1: "1W",
}


def to_blofin_inst_id(symbol: str) -> str:
    """Convert a platform symbol (e.g. ``BTCUSDT``) to a BloFin instId (``BTC-USDT``).

    Already-hyphenated symbols are normalized and returned uppercased.
    """
    cleaned = symbol.strip().upper().replace("/", "-")
    if "-" in cleaned:
        return cleaned
    for quote in _QUOTE_CURRENCIES:
        if cleaned.endswith(quote) and len(cleaned) > len(quote):
            return f"{cleaned[: -len(quote)]}-{quote}"
    return cleaned


def from_blofin_inst_id(inst_id: str) -> str:
    """Convert a BloFin instId (``BTC-USDT``) to a platform symbol (``BTCUSDT``)."""
    return inst_id.strip().upper().replace("-", "")


def timeframe_to_bar(timeframe: Timeframe) -> str:
    """Return the BloFin candle ``bar`` value for a platform timeframe."""
    return _TIMEFRAME_TO_BAR.get(timeframe, "1H")

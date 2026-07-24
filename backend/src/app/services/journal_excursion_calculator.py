"""Deterministic in-trade MFE/MAE and available-profit arithmetic (AT-032).

Pure functions over OHLC bars — no I/O. Long and short are first-class.
Amounts use recorded size when present; price extremes always compute when bars exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.schemas.common import TradeDirection

_ZERO = Decimal("0")
_MONEY_Q = Decimal("0.00000001")


@dataclass(frozen=True, slots=True)
class CandleBar:
    """Minimal OHLC bar used by the excursion calculator."""

    open_time: datetime
    close_time: datetime
    high: Decimal
    low: Decimal
    source: str
    is_stale: bool
    freshness_note: str | None = None


@dataclass(frozen=True, slots=True)
class ExcursionCalculation:
    """Deterministic excursion metrics for one closed trade window."""

    mfe_price: Decimal
    mae_price: Decimal
    mfe_amount: Decimal | None
    mae_amount: Decimal | None
    available_profit: Decimal | None
    realized_vs_available_pct: float | None
    candle_count: int
    data_source: str | None
    any_stale: bool
    limitations: tuple[str, ...]


def compute_trade_excursions(
    *,
    direction: TradeDirection,
    entry_price: Decimal,
    size: Decimal | None,
    net_pnl: Decimal | None,
    bars: list[CandleBar],
) -> ExcursionCalculation:
    """Compute MFE/MAE/available profit from bars inside the trade window.

    Definitions (deterministic):
    - LONG: MFE price = max(high); MAE price = min(low)
    - SHORT: MFE price = min(low); MAE price = max(high)
    - Amounts = (price - entry) * size for long; (entry - price) * size for short
      (so MFE amount is typically ≥ 0 and MAE amount ≤ 0)
    - available_profit = max(mfe_amount, 0) when size is known
    - realized_vs_available_pct = net_pnl / available_profit * 100 when both set
      and available_profit ≠ 0
    """
    if not bars:
        return ExcursionCalculation(
            mfe_price=entry_price,
            mae_price=entry_price,
            mfe_amount=None,
            mae_amount=None,
            available_profit=None,
            realized_vs_available_pct=None,
            candle_count=0,
            data_source=None,
            any_stale=False,
            limitations=("No candles in trade window — excursions not computed.",),
        )

    highs = [b.high for b in bars]
    lows = [b.low for b in bars]
    max_high = max(highs)
    min_low = min(lows)

    if direction == TradeDirection.LONG:
        mfe_price = max_high
        mae_price = min_low
        mfe_amount = _amount_long(mfe_price, entry_price, size)
        mae_amount = _amount_long(mae_price, entry_price, size)
    else:
        mfe_price = min_low
        mae_price = max_high
        mfe_amount = _amount_short(mfe_price, entry_price, size)
        mae_amount = _amount_short(mae_price, entry_price, size)

    available = _available_profit(mfe_amount)
    capture = _capture_pct(net_pnl, available)

    sources = {b.source for b in bars if b.source}
    data_source = sorted(sources)[0] if len(sources) == 1 else ("mixed" if sources else None)
    any_stale = any(b.is_stale for b in bars)
    limitations: list[str] = []
    if size is None:
        limitations.append("Trade size missing — amount metrics omitted; prices only.")
    if any_stale:
        limitations.append("One or more candles marked stale.")
    if len(sources) > 1:
        limitations.append(f"Mixed candle sources: {', '.join(sorted(sources))}.")

    return ExcursionCalculation(
        mfe_price=mfe_price.quantize(_MONEY_Q),
        mae_price=mae_price.quantize(_MONEY_Q),
        mfe_amount=mfe_amount,
        mae_amount=mae_amount,
        available_profit=available,
        realized_vs_available_pct=capture,
        candle_count=len(bars),
        data_source=data_source,
        any_stale=any_stale,
        limitations=tuple(limitations),
    )


def filter_bars_in_window(
    bars: list[CandleBar],
    *,
    entry_time: datetime,
    exit_time: datetime,
) -> list[CandleBar]:
    """Keep bars that overlap the open trade interval ``[entry_time, exit_time)``.

    The exit timestamp is exclusive so the exit bar is not double-counted with
    post-exit runner lookahead candles.
    """
    return [b for b in bars if b.open_time < exit_time and b.close_time > entry_time]


def _amount_long(price: Decimal, entry: Decimal, size: Decimal | None) -> Decimal | None:
    if size is None:
        return None
    return ((price - entry) * size).quantize(_MONEY_Q)


def _amount_short(price: Decimal, entry: Decimal, size: Decimal | None) -> Decimal | None:
    if size is None:
        return None
    return ((entry - price) * size).quantize(_MONEY_Q)


def _available_profit(mfe_amount: Decimal | None) -> Decimal | None:
    if mfe_amount is None:
        return None
    if mfe_amount <= _ZERO:
        return _ZERO
    return mfe_amount


def _capture_pct(net_pnl: Decimal | None, available: Decimal | None) -> float | None:
    if net_pnl is None or available is None or available == _ZERO:
        return None
    return float(net_pnl / available * Decimal("100"))

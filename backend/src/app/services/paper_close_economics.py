"""Deterministic paper-close PnL. No market data and no exchange calls."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.core.errors import ValidationAppError
from app.schemas.common import TradeDirection, TradeResult

_QUANT = Decimal("0.00000001")


@dataclass(frozen=True, slots=True)
class PaperCloseEconomics:
    """Gross and net PnL for one already-filled paper trade."""

    gross_pnl: Decimal
    net_pnl: Decimal
    result: TradeResult


def paper_close_pnl(
    *,
    direction: TradeDirection,
    entry_price: Decimal,
    exit_price: Decimal,
    size: Decimal,
    fees: Decimal,
    funding: Decimal,
    slippage: Decimal,
) -> PaperCloseEconomics:
    """Compute paper PnL from recorded entry, explicit exit, and recorded costs.

    Long PnL is ``(exit - entry) * size``. Short PnL flips the price delta.
    Net PnL subtracts fees, funding, and slippage. The result follows the sign
    of net PnL. Missing or non-finite inputs fail closed.
    """

    entry = _positive_money(entry_price, field="entry_price")
    exit_ = _positive_money(exit_price, field="exit_price")
    quantity = _positive_money(size, field="size")
    fee_cost = _non_negative_money(fees, field="fees")
    funding_cost = _non_negative_money(funding, field="funding")
    slippage_cost = _non_negative_money(slippage, field="slippage")
    delta = exit_ - entry
    if direction is TradeDirection.SHORT:
        delta = -delta
    elif direction is not TradeDirection.LONG:
        raise ValidationAppError(
            "Paper close requires a long or short direction.",
            details={"reason": "invalid_direction"},
        )
    gross = _money(delta * quantity)
    net = _money(gross - fee_cost - funding_cost - slippage_cost)
    return PaperCloseEconomics(gross_pnl=gross, net_pnl=net, result=_result_for(net))


def _result_for(net_pnl: Decimal) -> TradeResult:
    if net_pnl > 0:
        return TradeResult.WIN
    if net_pnl < 0:
        return TradeResult.LOSS
    return TradeResult.BREAKEVEN


def _money(value: Decimal) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValidationAppError(
            "Paper close monetary value must be a finite decimal.",
            details={"reason": "invalid_money"},
        )
    return value.quantize(_QUANT)


def _positive_money(value: Decimal, *, field: str) -> Decimal:
    amount = _money(value)
    if amount <= 0:
        raise ValidationAppError(
            "Paper close price and size must be positive.",
            details={"reason": "non_positive_money", "field": field},
        )
    return amount


def _non_negative_money(value: Decimal, *, field: str) -> Decimal:
    amount = _money(value)
    if amount < 0:
        raise ValidationAppError(
            "Paper close costs cannot be negative.",
            details={"reason": "negative_cost", "field": field},
        )
    return amount

"""Deterministic signed quote flow for a closed bar."""

from __future__ import annotations

from datetime import UTC
from decimal import Decimal

from pydantic import AwareDatetime, Field

from app.market_contracts.cvd import accumulate_signed_quote, select_trades_in_window
from app.market_contracts.enums import AggressorSide
from app.market_contracts.errors import IncompleteWarmUpError
from app.market_contracts.hashing import with_content_hash
from app.market_contracts.identity import EvidenceMarketIdentity
from app.market_contracts.models import CanonicalDecimal, CanonicalModel
from app.market_contracts.ohlcv import OhlcvBar
from app.market_contracts.trades import TradeEvent

SIGNED_FLOW_POLICY_VERSION = "signed-quote-delta/total-quote-volume/v1"


class SignedQuoteFlow(CanonicalModel):
    identity: EvidenceMarketIdentity
    interval_start: AwareDatetime
    interval_end: AwareDatetime
    signed_quote_delta: CanonicalDecimal
    total_quote_volume: CanonicalDecimal
    signed_flow_ratio: CanonicalDecimal
    buy_quote_volume: CanonicalDecimal
    sell_quote_volume: CanonicalDecimal
    event_count: int = Field(ge=0)
    policy_version: str = Field(min_length=3, max_length=80)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


def bar_signed_quote_flow(
    *,
    identity: EvidenceMarketIdentity,
    bar: OhlcvBar,
    trades: list[TradeEvent],
) -> SignedQuoteFlow:
    """signed_quote_delta / total_quote_volume over the bar's half-open interval."""
    selected = select_trades_in_window(trades, start=bar.interval_start, end=bar.interval_end)
    signed, total = accumulate_signed_quote(selected)
    if total == 0:
        raise IncompleteWarmUpError("Signed quote flow is undefined when total quote volume is 0.")
    buy = Decimal("0")
    sell = Decimal("0")
    for trade in selected:
        if trade.aggressor_side is AggressorSide.BUY:
            buy += trade.quote_quantity
        else:
            sell += trade.quote_quantity
    ratio = signed / total
    flow = SignedQuoteFlow(
        identity=identity,
        interval_start=bar.interval_start.astimezone(UTC),
        interval_end=bar.interval_end.astimezone(UTC),
        signed_quote_delta=signed,
        total_quote_volume=total,
        signed_flow_ratio=ratio,
        buy_quote_volume=buy,
        sell_quote_volume=sell,
        event_count=len(selected),
        policy_version=SIGNED_FLOW_POLICY_VERSION,
        content_hash="0" * 64,
    )
    return with_content_hash(flow)


def trigger_bar_aggressive_sell_imbalance(flow: SignedQuoteFlow, *, threshold: Decimal) -> bool:
    """First-slice sell imbalance: signed_quote_delta / total_quote_volume <= threshold."""
    return flow.signed_flow_ratio <= threshold

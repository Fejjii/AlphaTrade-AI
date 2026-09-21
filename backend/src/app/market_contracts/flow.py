"""Deterministic signed quote flow for a closed bar."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import AwareDatetime, Field

from app.market_contracts.coverage import require_complete_window_coverage
from app.market_contracts.cursor import TradeStreamSnapshot
from app.market_contracts.cvd import (
    accumulate_signed_quote,
    require_cvd_stream_proof,
    select_trades_in_window,
)
from app.market_contracts.enums import AggressorSide
from app.market_contracts.errors import (
    IncompleteWarmUpError,
    WrongInstrumentError,
    WrongMarketError,
)
from app.market_contracts.freshness import evaluate_freshness, first_slice_freshness_policy
from app.market_contracts.hashing import with_content_hash
from app.market_contracts.identity import EvidenceMarketIdentity
from app.market_contracts.models import CanonicalDecimal, CanonicalModel
from app.market_contracts.ohlcv import OhlcvBar

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
    source_connection_id: UUID
    coverage_proof_id: UUID
    coverage_content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    event_time_max: AwareDatetime
    policy_version: str = Field(min_length=3, max_length=80)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


def bar_signed_quote_flow(
    *,
    identity: EvidenceMarketIdentity,
    bar: OhlcvBar,
    snapshot: TradeStreamSnapshot,
    evaluated_at: datetime,
    require_live_freshness: bool = True,
) -> SignedQuoteFlow:
    """Compute signed flow only from proven, complete, fresh trigger-bar evidence."""
    if identity != snapshot.cursor.identity:
        raise WrongMarketError(
            "Signed-flow identity does not exactly match the authoritative trade snapshot."
        )
    if bar.instrument != identity.instrument:
        raise WrongInstrumentError("Signed-flow bar instrument does not match market identity.")
    if identity.timeframe is not None and bar.timeframe is not identity.timeframe:
        raise WrongMarketError("Signed-flow bar timeframe does not match market identity.")
    require_cvd_stream_proof(snapshot)
    require_complete_window_coverage(
        snapshot.coverage,
        identity=identity,
        lineage_id=snapshot.cursor.connection_identity,
        trades=snapshot.trades,
        required_start=bar.interval_start,
        required_end=bar.interval_end,
    )
    selected = select_trades_in_window(
        snapshot.trades,
        start=bar.interval_start,
        end=bar.interval_end,
    )
    signed, total = accumulate_signed_quote(selected)
    if total == 0:
        raise IncompleteWarmUpError("Signed quote flow is undefined when total quote volume is 0.")
    terminal = selected[-1]
    evaluate_freshness(
        source_time=terminal.event_timestamp,
        evaluated_at=evaluated_at,
        policy=first_slice_freshness_policy(),
        require_fresh=require_live_freshness,
    )
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
        source_connection_id=snapshot.cursor.connection_identity,
        coverage_proof_id=snapshot.coverage.coverage_proof_id,
        coverage_content_hash=snapshot.coverage.content_hash,
        event_time_max=terminal.event_timestamp,
        policy_version=SIGNED_FLOW_POLICY_VERSION,
        content_hash="0" * 64,
    )
    return with_content_hash(flow)


def trigger_bar_aggressive_sell_imbalance(flow: SignedQuoteFlow, *, threshold: Decimal) -> bool:
    """First-slice sell imbalance: signed_quote_delta / total_quote_volume <= threshold."""
    return flow.signed_flow_ratio <= threshold

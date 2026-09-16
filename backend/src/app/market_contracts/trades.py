"""Ordered perpetual trade events and aggressor normalization."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4, uuid5

from pydantic import AwareDatetime, Field, model_validator

from app.market_contracts.coverage import (
    TradeWindowCoverageProof,
    require_trade_matches_identity,
    verify_trade_window_coverage,
)
from app.market_contracts.enums import AggressorSide, MarketType
from app.market_contracts.errors import (
    DuplicateDataError,
    OutOfOrderTradesError,
    UnknownAggressorError,
    WrongMarketError,
)
from app.market_contracts.hashing import with_content_hash
from app.market_contracts.identity import (
    AGGRESSOR_CONVENTION,
    EvidenceMarketIdentity,
    InstrumentIdentity,
    require_instrument,
    require_perpetual,
)
from app.market_contracts.models import CanonicalModel, PositiveCanonicalDecimal

_TRADE_NAMESPACE = UUID("c3e9d4a1-8b52-4f07-91aa-77d0c2f1b904")


class TradeEvent(CanonicalModel):
    """One venue perpetual execution after normalization."""

    trade_event_id: UUID
    venue_trade_id: str = Field(min_length=1, max_length=40)
    sequence: int = Field(ge=0)
    instrument: InstrumentIdentity
    market_type: MarketType
    price: PositiveCanonicalDecimal
    quantity: PositiveCanonicalDecimal
    quote_quantity: PositiveCanonicalDecimal
    aggressor_side: AggressorSide
    aggressor_convention: str = Field(min_length=3, max_length=120)
    event_timestamp: AwareDatetime
    receive_timestamp: AwareDatetime
    source_connection_id: UUID
    adapter_version: str = Field(min_length=3, max_length=80)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _quote_matches_linear_formula(self) -> TradeEvent:
        if self.market_type is not MarketType.PERPETUAL:
            raise WrongMarketError("TradeEvent is only defined for perpetual markets.")
        expected_quote = self.price * self.quantity * self.instrument.contract_multiplier
        if expected_quote != self.quote_quantity:
            raise ValueError("quote_quantity must equal price * quantity * contract_multiplier.")
        return self


class OrderedTradeBatch(CanonicalModel):
    identity: EvidenceMarketIdentity
    trades: list[TradeEvent]
    source_connection_id: UUID
    coverage: TradeWindowCoverageProof
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _ordered_unique(self) -> OrderedTradeBatch:
        require_perpetual(self.identity)
        require_instrument(self.identity, self.identity.instrument)
        seen: dict[str, str] = {}
        previous_seq: int | None = None
        previous_ts: datetime | None = None
        for trade in self.trades:
            require_trade_matches_identity(trade, self.identity)
            if trade.source_connection_id != self.source_connection_id:
                raise ValueError("Mixed source_connection_id values are not allowed in one batch.")
            prior_hash = seen.get(trade.venue_trade_id)
            if prior_hash is not None:
                if prior_hash != trade.content_hash:
                    raise DuplicateDataError(
                        f"Conflicting content for venue trade {trade.venue_trade_id}."
                    )
                raise DuplicateDataError(f"Duplicate venue trade {trade.venue_trade_id}.")
            seen[trade.venue_trade_id] = trade.content_hash
            if previous_seq is not None and trade.sequence < previous_seq:
                raise OutOfOrderTradesError(
                    f"Trade sequence {trade.sequence} is before previous {previous_seq}."
                )
            if previous_seq is not None and trade.sequence == previous_seq:
                raise DuplicateDataError(f"Duplicate sequence {trade.sequence}.")
            if previous_ts is not None and trade.event_timestamp < previous_ts:
                raise OutOfOrderTradesError(
                    "Trade event timestamps must be non-decreasing in venue order."
                )
            previous_seq = trade.sequence
            previous_ts = trade.event_timestamp
        verify_trade_window_coverage(
            self.coverage,
            identity=self.identity,
            lineage_id=self.source_connection_id,
            trades=self.trades,
        )
        return self


def quote_quantity(*, price: Decimal, quantity: Decimal, multiplier: Decimal) -> Decimal:
    """Unrounded Decimal quote value for linear perpetuals."""
    return price * quantity * multiplier


def aggressor_from_buyer_is_maker(buyer_is_maker: bool) -> AggressorSide:
    """Binance USD-M aggTrade `m`: true means buyer is maker, so seller is aggressor."""
    return AggressorSide.SELL if buyer_is_maker else AggressorSide.BUY


def natural_trade_id(instrument_id: str, venue_trade_id: str) -> UUID:
    return uuid5(_TRADE_NAMESPACE, f"{instrument_id}:{venue_trade_id}")


def build_trade_event(
    *,
    instrument: InstrumentIdentity,
    venue_trade_id: str,
    sequence: int,
    price: Decimal,
    quantity: Decimal,
    buyer_is_maker: bool | None,
    event_timestamp: datetime,
    receive_timestamp: datetime,
    source_connection_id: UUID,
    adapter_version: str,
    aggressor_convention: str = AGGRESSOR_CONVENTION,
    trade_event_id: UUID | None = None,
) -> TradeEvent:
    if buyer_is_maker is None:
        raise UnknownAggressorError("Aggressor flag is required for signed quote flow.")
    if instrument.market_type is not MarketType.PERPETUAL:
        raise WrongMarketError("TradeEvent requires a perpetual instrument.")
    quote = quote_quantity(
        price=price, quantity=quantity, multiplier=instrument.contract_multiplier
    )
    event = TradeEvent(
        trade_event_id=trade_event_id or natural_trade_id(instrument.instrument_id, venue_trade_id),
        venue_trade_id=str(venue_trade_id),
        sequence=sequence,
        instrument=instrument,
        market_type=MarketType.PERPETUAL,
        price=price,
        quantity=quantity,
        quote_quantity=quote,
        aggressor_side=aggressor_from_buyer_is_maker(buyer_is_maker),
        aggressor_convention=aggressor_convention,
        event_timestamp=event_timestamp.astimezone(UTC),
        receive_timestamp=receive_timestamp.astimezone(UTC),
        source_connection_id=source_connection_id,
        adapter_version=adapter_version,
        content_hash="0" * 64,
    )
    return with_content_hash(event, extra_exclude=frozenset({"source_connection_id"}))


def signed_quote_value(trade: TradeEvent) -> Decimal:
    if not trade.aggressor_convention:
        raise UnknownAggressorError("Missing aggressor convention.")
    if trade.aggressor_side is AggressorSide.BUY:
        return trade.quote_quantity
    if trade.aggressor_side is AggressorSide.SELL:
        return -trade.quote_quantity
    raise UnknownAggressorError("Unknown aggressor side.")


def order_trades(trades: list[TradeEvent]) -> list[TradeEvent]:
    """Stable venue order: sequence, then event time, then venue trade id."""
    return sorted(
        trades,
        key=lambda trade: (trade.sequence, trade.event_timestamp, trade.venue_trade_id),
    )


def new_connection_id() -> UUID:
    return uuid4()

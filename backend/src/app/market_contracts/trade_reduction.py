"""Build a coverage-bound trade snapshot without retaining every trade.

CVD, signed flow, and the coverage hash stay identical to the full trade list.
Only closed-bar Decimal sums and the proof remain.
"""

from __future__ import annotations

import gc
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from app.market_contracts.coverage import build_complete_trade_window_coverage_from_hash
from app.market_contracts.cursor import TradeStreamCursor, TradeStreamSnapshot, initial_cursor
from app.market_contracts.enums import AggressorSide, GapState, ReconnectState, WarmUpStatus
from app.market_contracts.errors import (
    DuplicateDataError,
    GapDetectedError,
    IncompleteTradeWindowError,
    OutOfOrderTradesError,
    WrongSourceError,
)
from app.market_contracts.hashing import with_content_hash
from app.market_contracts.identity import INTERVAL_SECONDS, EvidenceMarketIdentity
from app.market_contracts.released_tape import ClosedBarFlow, ReleasedTradeTape
from app.market_contracts.streaming_hash import TradeSetHasher, VenueIdSetHasher
from app.market_contracts.trades import TradeEvent, signed_quote_value
from app.observability.process_memory import release_allocator_memory
from app.schemas.common import Timeframe

_GC_EVERY = 2_000


@dataclass
class _BarAccum:
    interval_start: datetime
    interval_end: datetime
    signed: Decimal
    total: Decimal
    buy: Decimal
    sell: Decimal
    count: int
    event_time_max: datetime
    terminal_price: Decimal


def build_released_trade_snapshot(
    trades: Iterable[TradeEvent],
    *,
    identity: EvidenceMarketIdentity,
    lineage_id: UUID,
    window_start: datetime,
    window_end: datetime,
    observed_at: datetime,
) -> TradeStreamSnapshot:
    """Reduce ``trades`` to a snapshot whose proof matches a retained tape.

    The iterable is consumed once. Trade objects are not stored.
    """

    start = window_start.astimezone(UTC)
    end = window_end.astimezone(UTC)
    if end <= start:
        raise IncompleteTradeWindowError("Trade window end must be after start.")
    bar_seconds = _bar_seconds(identity)
    trade_hasher = TradeSetHasher()
    id_hasher = VenueIdSetHasher()
    bars: dict[datetime, _BarAccum] = {}
    signed = Decimal("0")
    total = Decimal("0")
    count = 0
    first_trade_id: str | None = None
    last_trade_id: str | None = None
    first_sequence: int | None = None
    last_sequence: int | None = None
    event_time_max: datetime | None = None
    receive_time_max: datetime | None = None
    terminal_price: Decimal | None = None
    previous_sequence: int | None = None
    previous_timestamp: datetime | None = None

    for trade in trades:
        _require_trade(trade, identity=identity, lineage_id=lineage_id, start=start, end=end)
        if previous_sequence is not None:
            if trade.sequence == previous_sequence:
                raise DuplicateDataError(f"Duplicate sequence {trade.sequence}.")
            if trade.sequence != previous_sequence + 1:
                raise GapDetectedError(
                    f"Confirmed sequence gap {previous_sequence + 1}-{trade.sequence - 1}."
                )
            if previous_timestamp is not None and trade.event_timestamp < previous_timestamp:
                raise OutOfOrderTradesError(
                    "Trade event timestamps must be non-decreasing in venue order."
                )
        previous_sequence = trade.sequence
        previous_timestamp = trade.event_timestamp
        trade_hasher.add(
            venue_trade_id=trade.venue_trade_id,
            sequence=trade.sequence,
            content_hash=trade.content_hash,
        )
        id_hasher.add(trade.venue_trade_id)
        quote = trade.quote_quantity
        delta = signed_quote_value(trade)
        signed += delta
        total += quote
        count += 1
        if first_trade_id is None:
            first_trade_id = trade.venue_trade_id
            first_sequence = trade.sequence
        last_trade_id = trade.venue_trade_id
        last_sequence = trade.sequence
        event_time_max = trade.event_timestamp
        receive_time_max = trade.receive_timestamp
        terminal_price = trade.price
        _add_bar(
            bars,
            trade,
            bar_seconds=bar_seconds,
            delta=delta,
            quote=quote,
        )
        if count % _GC_EVERY == 0:
            gc.collect()

    if (
        count < 1
        or first_trade_id is None
        or last_trade_id is None
        or first_sequence is None
        or last_sequence is None
        or event_time_max is None
        or receive_time_max is None
        or terminal_price is None
    ):
        raise IncompleteTradeWindowError("AggTrade window contained no trades.")

    closed_bars = tuple(
        ClosedBarFlow(
            interval_start=bar.interval_start,
            interval_end=bar.interval_end,
            signed_quote_delta=bar.signed,
            total_quote_volume=bar.total,
            buy_quote_volume=bar.buy,
            sell_quote_volume=bar.sell,
            event_count=bar.count,
            event_time_max=bar.event_time_max,
            terminal_price=bar.terminal_price,
        )
        for bar in bars.values()
    )
    tape = ReleasedTradeTape(
        window_start=start,
        window_end=end,
        trade_set_hash=trade_hasher.hexdigest(),
        event_set_hash=id_hasher.hexdigest(),
        event_count=count,
        signed_quote_delta=signed,
        total_quote_volume=total,
        first_trade_id=first_trade_id,
        last_trade_id=last_trade_id,
        first_sequence=first_sequence,
        last_sequence=last_sequence,
        event_time_max=event_time_max,
        receive_time_max=receive_time_max,
        terminal_price=terminal_price,
        bars=closed_bars,
    )
    coverage = build_complete_trade_window_coverage_from_hash(
        identity=identity,
        lineage_id=lineage_id,
        requested_start=start,
        requested_end=end,
        trade_set_hash=tape.trade_set_hash,
        first_trade_id=tape.first_trade_id,
        last_trade_id=tape.last_trade_id,
        first_sequence=tape.first_sequence,
        last_sequence=tape.last_sequence,
    )
    observed = observed_at.astimezone(UTC)
    cursor = _final_cursor(
        identity=identity,
        lineage_id=lineage_id,
        observed_at=observed,
        last_trade_id=tape.last_trade_id,
        last_sequence=tape.last_sequence,
        last_event_at=tape.event_time_max,
    )
    snapshot = TradeStreamSnapshot(
        cursor=cursor,
        trades=[],
        coverage=coverage,
        usable=True,
        released_tape=tape,
    )
    release_allocator_memory()
    return snapshot


def _require_trade(
    trade: TradeEvent,
    *,
    identity: EvidenceMarketIdentity,
    lineage_id: UUID,
    start: datetime,
    end: datetime,
) -> None:
    from app.market_contracts.coverage import require_trade_matches_identity

    require_trade_matches_identity(trade, identity)
    if trade.source_connection_id != lineage_id:
        raise WrongSourceError("Trade lineage does not match the coverage proof lineage.")
    if not start <= trade.event_timestamp < end:
        raise IncompleteTradeWindowError(
            "Trade event falls outside the coverage proof requested window."
        )


def _add_bar(
    bars: dict[datetime, _BarAccum],
    trade: TradeEvent,
    *,
    bar_seconds: int,
    delta: Decimal,
    quote: Decimal,
) -> None:
    interval_start, interval_end = _bar_bounds(trade.event_timestamp, bar_seconds)
    current = bars.get(interval_start)
    buy = quote if trade.aggressor_side is AggressorSide.BUY else Decimal("0")
    sell = Decimal("0") if trade.aggressor_side is AggressorSide.BUY else quote
    if current is None:
        bars[interval_start] = _BarAccum(
            interval_start=interval_start,
            interval_end=interval_end,
            signed=delta,
            total=quote,
            buy=buy,
            sell=sell,
            count=1,
            event_time_max=trade.event_timestamp,
            terminal_price=trade.price,
        )
        return
    current.signed += delta
    current.total += quote
    current.buy += buy
    current.sell += sell
    current.count += 1
    current.event_time_max = trade.event_timestamp
    current.terminal_price = trade.price


def _bar_bounds(moment: datetime, bar_seconds: int) -> tuple[datetime, datetime]:
    epoch = int(moment.astimezone(UTC).timestamp())
    start_epoch = epoch - (epoch % bar_seconds)
    start = datetime.fromtimestamp(start_epoch, tz=UTC)
    return start, start + timedelta(seconds=bar_seconds)


def _bar_seconds(identity: EvidenceMarketIdentity) -> int:
    timeframe = identity.timeframe if identity.timeframe is not None else Timeframe.M15
    try:
        return INTERVAL_SECONDS[timeframe]
    except KeyError as exc:
        raise IncompleteTradeWindowError(
            f"Unsupported timeframe {timeframe.value} for trade reduction."
        ) from exc


def _final_cursor(
    *,
    identity: EvidenceMarketIdentity,
    lineage_id: UUID,
    observed_at: datetime,
    last_trade_id: str,
    last_sequence: int,
    last_event_at: datetime,
) -> TradeStreamCursor:
    cursor = initial_cursor(
        identity=identity,
        connected_at=observed_at,
        connection_identity=lineage_id,
    )
    return with_content_hash(
        cursor.model_copy(
            update={
                "last_event_id": last_trade_id,
                "last_sequence": last_sequence,
                "last_event_at": last_event_at,
                "reconnect_state": ReconnectState.CONTINUOUS,
                "gap_state": GapState.NONE,
                "warm_up_status": WarmUpStatus.COMPLETE,
                "updated_at": observed_at,
            }
        )
    )

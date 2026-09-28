"""Closed-bar aggregates left behind after a verified trade tape is released.

The coverage proof still binds every trade's content hash. Evaluation reads
these bar sums instead of the trade objects. The sums are the exact Decimal
totals of the trades that fell in each closed bar.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from pydantic import AwareDatetime, Field, model_validator

from app.market_contracts.models import CanonicalDecimal, CanonicalModel, PositiveCanonicalDecimal


class ClosedBarFlow(CanonicalModel):
    """Signed quote flow for one closed bar. Trades are not retained."""

    interval_start: AwareDatetime
    interval_end: AwareDatetime
    signed_quote_delta: CanonicalDecimal
    total_quote_volume: CanonicalDecimal
    buy_quote_volume: CanonicalDecimal
    sell_quote_volume: CanonicalDecimal
    event_count: int = Field(ge=0)
    event_time_max: AwareDatetime
    terminal_price: PositiveCanonicalDecimal

    @model_validator(mode="after")
    def _bounds(self) -> ClosedBarFlow:
        if self.interval_end <= self.interval_start:
            raise ValueError("Closed bar flow must end after it starts.")
        if self.event_count < 1:
            raise ValueError("Closed bar flow requires at least one trade.")
        return self


class ReleasedTradeTape(CanonicalModel):
    """Verified trade-set summary. The trade objects themselves are gone."""

    window_start: AwareDatetime
    window_end: AwareDatetime
    trade_set_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    event_set_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    event_count: int = Field(ge=1)
    signed_quote_delta: CanonicalDecimal
    total_quote_volume: CanonicalDecimal
    first_trade_id: str = Field(min_length=1, max_length=40)
    last_trade_id: str = Field(min_length=1, max_length=40)
    first_sequence: int = Field(ge=0)
    last_sequence: int = Field(ge=0)
    event_time_max: AwareDatetime
    receive_time_max: AwareDatetime
    terminal_price: PositiveCanonicalDecimal
    bars: tuple[ClosedBarFlow, ...]

    @model_validator(mode="after")
    def _reconciles(self) -> ReleasedTradeTape:
        if self.window_end <= self.window_start:
            raise ValueError("Released trade tape window must end after it starts.")
        if self.last_sequence < self.first_sequence:
            raise ValueError("Released trade tape sequence bounds are reversed.")
        signed = Decimal("0")
        total = Decimal("0")
        count = 0
        previous_end: datetime | None = None
        start = self.window_start.astimezone(UTC)
        end = self.window_end.astimezone(UTC)
        for bar in self.bars:
            if previous_end is not None and bar.interval_start < previous_end:
                raise ValueError("Released bar flows overlap or are out of order.")
            if bar.interval_start < start or bar.interval_end > end:
                raise ValueError("Released bar flow falls outside the trade tape window.")
            signed += bar.signed_quote_delta
            total += bar.total_quote_volume
            count += bar.event_count
            previous_end = bar.interval_end
        if count != self.event_count:
            raise ValueError("Released bar flows do not count every trade.")
        if signed != self.signed_quote_delta or total != self.total_quote_volume:
            raise ValueError("Released bar flows do not reconcile to the trade tape.")
        return self


def closed_bar_covering(
    tape: ReleasedTradeTape,
    *,
    interval_start: datetime,
    interval_end: datetime,
) -> ClosedBarFlow | None:
    """Return the closed bar whose bounds equal the requested half-open interval."""

    start = interval_start.astimezone(UTC)
    end = interval_end.astimezone(UTC)
    for bar in tape.bars:
        if bar.interval_start.astimezone(UTC) == start and bar.interval_end.astimezone(UTC) == end:
            return bar
    return None


def bars_signed_quote(
    tape: ReleasedTradeTape,
    *,
    window_start: datetime,
    bar_end: datetime,
) -> Decimal:
    """Sum signed quote for closed bars fully inside ``[window_start, bar_end)``."""

    start = window_start.astimezone(UTC)
    end = bar_end.astimezone(UTC)
    signed = Decimal("0")
    for bar in tape.bars:
        if bar.interval_start >= start and bar.interval_end <= end:
            signed += bar.signed_quote_delta
    return signed

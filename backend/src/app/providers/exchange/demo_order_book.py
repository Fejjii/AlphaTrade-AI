"""Executable BloFin demo REST depth; all sizes are contracts, never base coins."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.providers.exchange.demo_quote import quote_time_at_receipt
from app.schemas.trade_plan import EntrySide

BOOK_DEPTH = 100
MAXIMUM_QUOTE_BPS = Decimal("10")  # Existing demo slippage allowance.


def venue_decimal(value: Any) -> Decimal:
    """Bound venue arithmetic before Decimal modulo/multiplication."""
    if type(value) not in (str, int) or len(str(value)) > 64:
        raise ValueError("Demo quote value malformed.")
    try:
        parsed = Decimal(str(value))
    except InvalidOperation:
        raise ValueError("Demo quote value malformed.") from None
    if (
        not parsed.is_finite()
        or parsed <= 0
        or len(parsed.as_tuple().digits) > 24
        or abs(int(parsed.as_tuple().exponent)) > 18
    ):
        raise ValueError("Demo quote value malformed.")
    return parsed


@dataclass(frozen=True)
class DemoOrderBook:
    observed_at: datetime
    side: EntrySide
    bids: tuple[tuple[Decimal, Decimal], ...]
    asks: tuple[tuple[Decimal, Decimal], ...]

    @property
    def levels(self) -> tuple[tuple[Decimal, Decimal], ...]:
        return self.asks if self.side is EntrySide.BUY else self.bids

    @property
    def price(self) -> Decimal:
        return self.levels[0][0]

    def worst_price(
        self, quantity: Decimal, *, lot: Decimal, minimum: Decimal, maximum: Decimal
    ) -> Decimal:
        quantity = venue_decimal(str(quantity))
        if quantity < minimum or quantity > maximum or quantity % lot != 0:
            raise ValueError("Demo quote quantity violates contract increments or limits.")
        remaining = quantity
        for price, contracts in self.levels:
            if abs(price - self.price) / self.price * 10000 > MAXIMUM_QUOTE_BPS:
                break
            remaining -= min(remaining, contracts)
            if remaining == 0:
                return price
        raise ValueError("Demo order book has insufficient depth within the slippage limit.")


def parse_demo_book(
    data: Any,
    *,
    instrument: str,
    side: EntrySide,
    tick: Decimal,
    lot: Decimal,
    received_at: datetime,
    request_duration_ms: float,
) -> DemoOrderBook:
    if not isinstance(side, EntrySide):
        raise ValueError("Demo quote side must be BUY or SELL.")
    if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
        raise ValueError("Demo order book unavailable or ambiguous.")
    row = data[0]
    # REST books identify the instrument in the request; reject a conflicting echo.
    if "instId" in row and row["instId"] != instrument:
        raise ValueError("Demo order book instrument mismatch.")
    observed = quote_time_at_receipt(
        row.get("ts"), received_at, request_duration_ms=request_duration_ms
    )

    def levels(name: str) -> tuple[tuple[Decimal, Decimal], ...]:
        raw = row.get(name)
        if not isinstance(raw, list) or not 0 < len(raw) <= BOOK_DEPTH:
            raise ValueError("Demo order book depth unavailable.")
        parsed: list[tuple[Decimal, Decimal]] = []
        for level in raw:
            if not isinstance(level, list) or len(level) != 2:
                raise ValueError("Demo order book level malformed.")
            price, size = venue_decimal(level[0]), venue_decimal(level[1])
            if price % tick != 0 or size % lot != 0:
                raise ValueError("Demo order book level violates venue increments.")
            if parsed and (price <= parsed[-1][0] if name == "asks" else price >= parsed[-1][0]):
                raise ValueError("Demo order book levels unordered or duplicated.")
            parsed.append((price, size))
        return tuple(parsed)

    bids, asks = levels("bids"), levels("asks")
    bid, ask = bids[0][0], asks[0][0]
    if bid >= ask:
        raise ValueError("Demo order book spread crossed or locked.")
    if (ask - bid) / bid * 10000 > MAXIMUM_QUOTE_BPS:
        raise ValueError("Demo order book spread exceeds the slippage limit.")
    return DemoOrderBook(observed, side, bids, asks)

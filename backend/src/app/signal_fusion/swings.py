"""Confirmed fractal swing highs for first-slice setup truth.

Uses strict left=2/right=2 uniqueness on FINAL OHLCV highs. Float structure
helpers are not used; Decimal comparison keeps evaluation deterministic.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.market_contracts.enums import Finality
from app.market_contracts.models import CanonicalModel
from app.market_contracts.ohlcv import OhlcvBar

SWING_ALGORITHM = "fractal-swing/v1"
SWING_LEFT = 2
SWING_RIGHT = 2


class ConfirmedSwingHigh(CanonicalModel):
    """One confirmed L2/R2 swing high. Index is into the ordered FINAL series."""

    algorithm: str = SWING_ALGORITHM
    left: int = SWING_LEFT
    right: int = SWING_RIGHT
    index: int = Field(ge=0)
    price: Decimal
    bar: OhlcvBar


def confirmed_fractal_swing_highs(
    bars: Sequence[OhlcvBar],
    *,
    left: int = SWING_LEFT,
    right: int = SWING_RIGHT,
) -> tuple[ConfirmedSwingHigh, ...]:
    """Return confirmed swing highs with a strictly unique pivot high.

    Bar ``i`` is confirmed only when ``left`` prior and ``right`` later FINAL
    bars exist and every neighbor high is strictly below ``bars[i].high``.
    """
    ordered = list(bars)
    size = len(ordered)
    if size < left + right + 1:
        return ()
    found: list[ConfirmedSwingHigh] = []
    for index in range(left, size - right):
        pivot = ordered[index]
        if pivot.finality is not Finality.FINAL:
            continue
        price = pivot.high
        neighbors = list(range(index - left, index)) + list(range(index + 1, index + right + 1))
        if any(ordered[neighbor].finality is not Finality.FINAL for neighbor in neighbors):
            continue
        if any(ordered[neighbor].high >= price for neighbor in neighbors):
            continue
        found.append(
            ConfirmedSwingHigh(
                index=index,
                price=price,
                bar=pivot,
            )
        )
    return tuple(found)


def most_recent_confirmed_swing_high(
    bars: Sequence[OhlcvBar],
    *,
    window_start: datetime | None = None,
    before_bar: OhlcvBar | None = None,
) -> ConfirmedSwingHigh | None:
    """Most recent confirmed swing high inside the CVD window and before trigger T."""
    selected = confirmed_fractal_swing_highs(bars)
    for item in reversed(selected):
        if before_bar is not None and item.bar.interval_end > before_bar.interval_start:
            continue
        if window_start is not None and item.bar.interval_start < window_start:
            continue
        return item
    return None

"""No-trade filters: deterministic vetoes on new entries.

Each returns a :class:`NoTradeFilter`; ``blocked=True`` means new entries should
be suppressed. Time-based conditions (weekend, staleness) are passed in as
booleans so the functions stay pure and wall-clock independent.
"""

from __future__ import annotations

from app.analysis.types import NoTradeFilter

DEFAULT_MIN_BARS = 30
DEFAULT_LOW_VOLUME_RATIO = 0.5
DEFAULT_EXTREME_FUNDING = 0.001  # 0.1% per interval


def evaluate_no_trade_filters(
    *,
    bar_count: int,
    volume_ratio: float | None,
    funding_rate: float | None,
    is_weekend: bool = False,
    is_stale: bool = False,
    min_bars: int = DEFAULT_MIN_BARS,
    low_volume_ratio: float = DEFAULT_LOW_VOLUME_RATIO,
    extreme_funding: float = DEFAULT_EXTREME_FUNDING,
) -> list[NoTradeFilter]:
    """Return all filters; callers treat any ``blocked`` as a hard veto."""
    filters: list[NoTradeFilter] = []

    filters.append(
        NoTradeFilter(
            name="insufficient_data",
            blocked=bar_count < min_bars,
            reason=f"Need >= {min_bars} bars, have {bar_count}.",
        )
    )
    filters.append(
        NoTradeFilter(
            name="stale_data",
            blocked=is_stale,
            reason="Latest market data is stale.",
        )
    )
    filters.append(
        NoTradeFilter(
            name="low_volume",
            blocked=volume_ratio is not None and volume_ratio < low_volume_ratio,
            reason=f"Volume ratio below {low_volume_ratio}.",
        )
    )
    filters.append(
        NoTradeFilter(
            name="extreme_funding",
            blocked=funding_rate is not None and abs(funding_rate) > extreme_funding,
            reason=f"Absolute funding rate above {extreme_funding}.",
        )
    )
    filters.append(
        NoTradeFilter(
            name="weekend",
            blocked=is_weekend,
            reason="Weekend session.",
        )
    )
    return filters

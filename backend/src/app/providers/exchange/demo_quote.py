"""Strict venue milliseconds and bounded public timing evidence; no freshness fallback."""

import re
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

logger = structlog.get_logger(__name__)
_NUMERIC_TIMESTAMP = re.compile(r"-?[0-9]{1,16}\Z")


class DemoQuoteTimingError(ValueError):
    def __init__(self, message: str, timing: dict[str, Any]) -> None:
        self.timing = timing
        super().__init__(message)


def quote_time_at_receipt(value: Any, received_at: datetime) -> datetime:
    """Never guess seconds/microseconds or replace venue time with receipt time."""
    raw: int | None = None
    if type(value) is int or isinstance(value, str):
        text = str(value)
        if _NUMERIC_TIMESTAMP.fullmatch(text):
            raw = int(text)
    timing: dict[str, Any] = {
        "raw_timestamp_ms": raw,
        "timestamp_unit": "unix_milliseconds",
        "parsed_timestamp_utc": None,
        "receipt_timestamp_utc": None,
        "quote_age_seconds": None,
        "freshness_status": "malformed_timestamp",
    }
    if received_at.tzinfo is None or received_at.utcoffset() is None:
        timing["freshness_status"] = "invalid_receipt_clock"
        raise DemoQuoteTimingError("Demo quote receipt clock must be timezone aware.", timing)
    receipt = received_at.astimezone(UTC)
    timing["receipt_timestamp_utc"] = receipt.isoformat()
    try:
        if raw is None or raw < 0:
            raise ValueError("Invalid timestamp.")
        # Integer timedelta preserves millisecond boundaries without float rounding.
        observed = datetime(1970, 1, 1, tzinfo=UTC) + timedelta(milliseconds=raw)
    except (ValueError, OverflowError):
        raise DemoQuoteTimingError("Demo quote timestamp invalid.", timing) from None
    age = (receipt - observed).total_seconds()
    timing.update(
        parsed_timestamp_utc=observed.isoformat(),
        quote_age_seconds=age,
        freshness_status="future" if age < 0 else "stale" if age >= 10 else "fresh",
    )
    # Only the constructed allowlist is logged; never the ticker, price or credentials.
    logger.info("blofin_demo_quote_timing", **timing)
    if not 0 <= age < 10:
        raise DemoQuoteTimingError("Demo quote stale or future dated.", timing)
    return observed

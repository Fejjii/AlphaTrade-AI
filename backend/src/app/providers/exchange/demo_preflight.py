"""Bounded demo preflight diagnostics; never include exception text or venue payloads."""

from collections.abc import Iterator
from contextlib import contextmanager
from decimal import InvalidOperation
from typing import Any

from app.providers.exchange.demo_quote import DemoQuoteTimingError
from app.providers.exchange.errors import (
    ExchangeAuthError,
    ExchangeError,
    ExchangeRateLimitError,
    ExchangeRequestError,
    ExchangeUnavailableError,
)

_VALIDATION_REASONS = {
    "Verified read/trade-only demo permissions required.": "permissions_not_read_trade_only",
    "Governed demo requires the existing NET account mode.": "position_mode_not_net",
    "Demo instrument unavailable.": "instrument_unavailable",
    "Only base-valued linear USDT contracts are supported.": "unsupported_contract",
    "Demo perpetual instrument required.": "instrument_not_perpetual",
    "Positive finite venue value required.": "invalid_instrument_or_quote_value",
    "Demo account must already use leverage 1; no leverage mutation.": "leverage_not_one",
    "Demo account state incomplete or unreadable.": "account_state_incomplete",
    "Demo position already open or unreadable; new entry refused.": "account_not_flat",
    "Demo pending orders or protection; new entry refused.": "pending_orders_present",
    "Demo USDT equity unavailable.": "usdt_balance_unavailable",
    "Demo quote unavailable.": "quote_unavailable",
    "Demo quote stale or future dated.": "quote_stale_or_future",
    "Demo quote timestamp invalid.": "malformed_or_unsupported_response",
    "Demo quote receipt clock must be timezone aware.": "invalid_receipt_clock",
}


def failure_diagnostics(
    exc: Exception, *, stage: str, endpoint: str | None = None
) -> dict[str, Any]:
    """Copy only fixed labels and bounded numeric protocol fields, never messages."""
    if isinstance(exc, DemoPreflightError):
        return dict(exc.diagnostics)
    error_type = "UnexpectedError"
    reason = "unexpected_failure"
    for cls, code in (
        (ExchangeAuthError, "venue_auth_or_permission_rejected"),
        (ExchangeRateLimitError, "venue_rate_limited"),
        (ExchangeUnavailableError, "venue_unavailable"),
        (ExchangeRequestError, "venue_request_rejected"),
    ):
        if isinstance(exc, cls):
            error_type, reason = cls.__name__, code
            break
    else:
        if isinstance(exc, (ValueError, TypeError, KeyError, InvalidOperation, OverflowError)):
            error_type = "InvalidVenueData"
            reason = _VALIDATION_REASONS.get(str(exc), "malformed_or_unsupported_response")
    diagnostics: dict[str, Any] = {
        "stage": stage,
        "reason_code": reason,
        "error_type": error_type,
    }
    if endpoint is not None:
        diagnostics["endpoint_name"] = endpoint
    if isinstance(exc, DemoQuoteTimingError):
        diagnostics.update(exc.timing)
    if isinstance(exc, ExchangeError) and exc.details is not None:
        status = exc.details.http_status
        if type(status) is int and 100 <= status <= 599:
            diagnostics["http_status"] = status
        venue_code = exc.details.venue_error_code
        if (
            isinstance(venue_code, str)
            and 0 < len(venue_code) <= 16
            and venue_code.isascii()
            and venue_code.isdecimal()
        ):
            diagnostics["venue_error_code"] = venue_code
    return diagnostics


class DemoPreflightError(ValueError):
    """A refusal with safe stage evidence, compatible with existing ValueError callers."""

    def __init__(self, exc: Exception, *, stage: str, endpoint: str) -> None:
        self.diagnostics = failure_diagnostics(exc, stage=stage, endpoint=endpoint)
        # Preserve known fixed validation copy; arbitrary exception text stays private.
        message = str(exc) if str(exc) in _VALIDATION_REASONS else "Demo preflight failed."
        super().__init__(message)


@contextmanager
def preflight_stage(stage: str, endpoint: str) -> Iterator[None]:
    try:
        yield
    except DemoPreflightError:
        raise
    except Exception as exc:
        raise DemoPreflightError(exc, stage=stage, endpoint=endpoint) from exc

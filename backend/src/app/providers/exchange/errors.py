"""Exchange client error types.

All messages are expected to be passed through ``redact_text`` before logging or
surfacing to operators so credentials never leak.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VenueErrorDetails:
    """Structured, operator-safe fields extracted from a venue failure."""

    venue_error_code: str | None = None
    venue_error_message: str | None = None
    http_status: int | None = None
    endpoint_name: str | None = None


class ExchangeError(Exception):
    """Base class for all exchange-provider errors."""

    def __init__(
        self,
        message: str,
        *,
        details: VenueErrorDetails | None = None,
    ) -> None:
        super().__init__(message)
        self.details = details


class ExchangeAuthError(ExchangeError):
    """Authentication/permission failure (bad key, missing scope)."""


class ExchangeRateLimitError(ExchangeError):
    """The venue rate-limited the request (HTTP 429 / venue code)."""


class ExchangeUnavailableError(ExchangeError):
    """The venue was unreachable or returned a 5xx after retries."""


class ExchangeRequestError(ExchangeError):
    """The venue rejected the request (4xx other than auth/rate limit)."""

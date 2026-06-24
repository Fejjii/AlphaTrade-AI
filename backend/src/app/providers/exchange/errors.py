"""Exchange client error types.

All messages are expected to be passed through ``redact_text`` before logging or
surfacing to operators so credentials never leak.
"""

from __future__ import annotations


class ExchangeError(Exception):
    """Base class for all exchange-provider errors."""


class ExchangeAuthError(ExchangeError):
    """Authentication/permission failure (bad key, missing scope)."""


class ExchangeRateLimitError(ExchangeError):
    """The venue rate-limited the request (HTTP 429 / venue code)."""


class ExchangeUnavailableError(ExchangeError):
    """The venue was unreachable or returned a 5xx after retries."""


class ExchangeRequestError(ExchangeError):
    """The venue rejected the request (4xx other than auth/rate limit)."""

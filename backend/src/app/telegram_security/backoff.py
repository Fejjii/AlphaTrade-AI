"""Outbox retry delays. The default schedule retries immediately.

Paper activation supplies a non-zero schedule. ``RATE_LIMITED`` waits without
consuming an attempt. Delays are computed from ``attempt`` and ``updated_at``,
which are already durable, so a restart keeps the same backoff.
"""

from __future__ import annotations

from datetime import timedelta

RATE_LIMITED_ERROR = "RATE_LIMITED"
_MIN_RATE_DEFER = timedelta(seconds=1)


class DeliveryBackoff:
    """Per-attempt wait before a ``RETRYABLE`` outbox row may be claimed again."""

    def __init__(
        self,
        *,
        delays: tuple[timedelta, ...] = (),
        defer: timedelta = timedelta(0),
    ) -> None:
        if any(delay < timedelta(0) for delay in delays):
            raise ValueError("backoff delays must be >= 0")
        if defer < timedelta(0):
            raise ValueError("backoff defer must be >= 0")
        self.delays = delays
        self.defer = defer

    def delay_for(self, attempt: int) -> timedelta:
        """Wait after a failed attempt. Attempt 0 and an empty schedule wait 0."""
        if attempt <= 0 or not self.delays:
            return timedelta(0)
        index = min(attempt, len(self.delays)) - 1
        return self.delays[index]

    def rate_limit_delay(self) -> timedelta:
        """Wait after a rate-limit defer. Always at least one second."""
        if self.defer > timedelta(0):
            return self.defer
        return _MIN_RATE_DEFER

    def retry_delay(self, *, attempt: int, last_error: str | None) -> timedelta:
        if last_error == RATE_LIMITED_ERROR:
            return self.rate_limit_delay()
        return self.delay_for(attempt)

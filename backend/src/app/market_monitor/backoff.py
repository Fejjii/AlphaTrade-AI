"""Reconnect and rate-limit backoff. Transport-only; never hashed."""

from __future__ import annotations

from dataclasses import dataclass

# Binance documents IP bans from 2 minutes through 3 days. Waiting out a
# Retry-After inside that ceiling does not send another request during the ban.
UPSTREAM_BAN_BACKOFF_CEILING_SECONDS = 3 * 24 * 60 * 60


@dataclass(frozen=True, slots=True)
class BackoffPolicy:
    initial_seconds: float = 0.25
    max_seconds: float = 30.0
    multiplier: float = 2.0


def delay_seconds(
    attempt: int,
    policy: BackoffPolicy,
    *,
    retry_after_seconds: float | None = None,
    honor_full_retry_after: bool = False,
) -> float:
    """Bounded exponential delay. Retry-After wins when present and finite.

    Rate-limit waits stay inside ``policy.max_seconds``. An upstream ban
    honors Retry-After up to the Binance ban ceiling so the next read is not
    sent while the ban is still in force.
    """
    if retry_after_seconds is not None:
        wait = max(retry_after_seconds, 0.0)
        if honor_full_retry_after:
            return min(wait, UPSTREAM_BAN_BACKOFF_CEILING_SECONDS)
        return min(wait, policy.max_seconds)
    exponent = max(attempt, 0)
    return min(policy.initial_seconds * (policy.multiplier**exponent), policy.max_seconds)

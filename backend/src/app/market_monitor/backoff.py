"""Reconnect and rate-limit backoff. Transport-only; never hashed."""

from __future__ import annotations

from dataclasses import dataclass


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
) -> float:
    """Bounded exponential delay. Retry-After wins when present and finite."""
    if retry_after_seconds is not None:
        return min(max(retry_after_seconds, 0.0), policy.max_seconds)
    exponent = max(attempt, 0)
    return min(policy.initial_seconds * (policy.multiplier**exponent), policy.max_seconds)

"""Injectable clocks so expiry and rate-limit tests stay deterministic."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime:
        """Return a timezone-aware instant."""


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FrozenClock:
    """Mutable test clock. ``now`` is always timezone-aware UTC."""

    def __init__(self, instant: datetime | None = None) -> None:
        if instant is None:
            self._now = datetime(2026, 9, 16, 16, 0, tzinfo=UTC)
        elif instant.tzinfo is None or instant.utcoffset() is None:
            raise ValueError("FrozenClock instant must be timezone-aware.")
        else:
            self._now = instant.astimezone(UTC)

    def now(self) -> datetime:
        return self._now

    def set(self, instant: datetime) -> None:
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise ValueError("FrozenClock instant must be timezone-aware.")
        self._now = instant.astimezone(UTC)

    def advance(self, delta: timedelta) -> None:
        self._now = self._now + delta

"""Setup-lifetime pins. Independent of quote, stream, and closed-evidence clocks.

Product assembly remembers the original trigger bar identity so later final 15m
bars become subsequent bars for expiry instead of a new trigger. Callers do not
pass ``setup_trigger_end``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock
from uuid import UUID

from app.signal_fusion.first_slice_types import FIRST_SLICE_EXPIRY_BARS


@dataclass(frozen=True, slots=True)
class SetupLifetimeKey:
    """Tenant + instrument + strategy version identity for one live setup."""

    organization_id: UUID
    symbol: str
    strategy_version_id: UUID


@dataclass(frozen=True, slots=True)
class SetupTriggerPin:
    """Original setup trigger identity required for deterministic expiry."""

    trigger_end: datetime
    trigger_bar_hash: str


class SetupLifetimeStore:
    """Process-local pins. Watcher stays unwired; this is not a second evidence hash."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._pins: dict[tuple[UUID, str, UUID], SetupTriggerPin] = {}

    def active_trigger_end(self, key: SetupLifetimeKey) -> datetime | None:
        pin = self.get(key)
        return None if pin is None else pin.trigger_end

    def get(self, key: SetupLifetimeKey) -> SetupTriggerPin | None:
        with self._lock:
            return self._pins.get(_index(key))

    def remember(self, key: SetupLifetimeKey, pin: SetupTriggerPin) -> None:
        with self._lock:
            self._pins[_index(key)] = pin

    def clear(self, key: SetupLifetimeKey) -> None:
        with self._lock:
            self._pins.pop(_index(key), None)


def utc_trigger_end(value: datetime) -> datetime:
    return value.astimezone(UTC) if value.tzinfo is not None else value.replace(tzinfo=UTC)


def expiry_bars() -> int:
    return FIRST_SLICE_EXPIRY_BARS


def _index(key: SetupLifetimeKey) -> tuple[UUID, str, UUID]:
    return (key.organization_id, key.symbol.upper(), key.strategy_version_id)


__all__ = [
    "SetupLifetimeKey",
    "SetupLifetimeStore",
    "SetupTriggerPin",
    "expiry_bars",
    "utc_trigger_end",
]

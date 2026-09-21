"""Setup-lifetime pins. Independent of quote, stream, and closed-evidence clocks.

Product assembly remembers the original trigger bar identity so later final 15m
bars become subsequent bars for expiry instead of a new trigger. Callers do not
pass ``setup_trigger_end``. Semantic identity excludes transport metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock
from typing import Protocol
from uuid import UUID

from app.schemas.common import Timeframe
from app.services.canonical_serialization import canonical_sha256
from app.signal_fusion.first_slice_types import FIRST_SLICE_EXPIRY_BARS


@dataclass(frozen=True, slots=True)
class SetupLifetimeKey:
    """Tenant + instrument + compiled setup identity for one live setup."""

    organization_id: UUID
    symbol: str
    timeframe: Timeframe
    strategy_version_id: UUID
    compiled_setup_definition_id: UUID
    compiled_content_hash: str


@dataclass(frozen=True, slots=True)
class SetupTriggerPin:
    """Original setup trigger identity required for deterministic expiry."""

    trigger_end: datetime
    trigger_bar_hash: str
    expired: bool = False
    required_lineage_hash: str = ""


class SetupLifetimePort(Protocol):
    """Process or durable pin store. Duplicate writes must converge."""

    def active_trigger_end(self, key: SetupLifetimeKey) -> datetime | None: ...

    def get(self, key: SetupLifetimeKey) -> SetupTriggerPin | None: ...

    def remember(self, key: SetupLifetimeKey, pin: SetupTriggerPin) -> None: ...

    def expire(self, key: SetupLifetimeKey) -> None: ...

    def clear(self, key: SetupLifetimeKey) -> None: ...


class SetupLifetimeStore:
    """Process-local pins. Watcher stays unwired; this is not a second evidence hash."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._pins: dict[_Index, SetupTriggerPin] = {}

    def active_trigger_end(self, key: SetupLifetimeKey) -> datetime | None:
        pin = self.get(key)
        return None if pin is None else pin.trigger_end

    def get(self, key: SetupLifetimeKey) -> SetupTriggerPin | None:
        with self._lock:
            return self._pins.get(_index(key))

    def remember(self, key: SetupLifetimeKey, pin: SetupTriggerPin) -> None:
        stored = bind_setup_trigger_pin(key, pin)
        with self._lock:
            current = self._pins.get(_index(key))
            merged = converge_setup_trigger_pin(current, stored)
            if merged is None:
                return
            self._pins[_index(key)] = merged

    def expire(self, key: SetupLifetimeKey) -> None:
        with self._lock:
            current = self._pins.get(_index(key))
            if current is None:
                return
            self._pins[_index(key)] = SetupTriggerPin(
                trigger_end=current.trigger_end,
                trigger_bar_hash=current.trigger_bar_hash,
                expired=True,
                required_lineage_hash=current.required_lineage_hash,
            )

    def clear(self, key: SetupLifetimeKey) -> None:
        with self._lock:
            self._pins.pop(_index(key), None)


def utc_trigger_end(value: datetime) -> datetime:
    return value.astimezone(UTC) if value.tzinfo is not None else value.replace(tzinfo=UTC)


def expiry_bars() -> int:
    return FIRST_SLICE_EXPIRY_BARS


def setup_lifetime_lineage_hash(
    key: SetupLifetimeKey,
    *,
    trigger_end: datetime,
    trigger_bar_hash: str,
) -> str:
    """Semantic lineage only: no connection id, receive time, or adapter transport."""

    return canonical_sha256(
        {
            "organization_id": str(key.organization_id),
            "symbol": key.symbol.upper(),
            "timeframe": key.timeframe.value,
            "strategy_version_id": str(key.strategy_version_id),
            "compiled_setup_definition_id": str(key.compiled_setup_definition_id),
            "compiled_content_hash": key.compiled_content_hash,
            "trigger_end": utc_trigger_end(trigger_end).isoformat(),
            "trigger_bar_hash": trigger_bar_hash,
        }
    )


def lifetime_key_from_policy(
    *,
    organization_id: UUID,
    symbol: str,
    timeframe: Timeframe,
    strategy_version_id: UUID,
    compiled_setup_definition_id: UUID,
    compiled_content_hash: str,
) -> SetupLifetimeKey:
    return SetupLifetimeKey(
        organization_id=organization_id,
        symbol=symbol.upper(),
        timeframe=timeframe,
        strategy_version_id=strategy_version_id,
        compiled_setup_definition_id=compiled_setup_definition_id,
        compiled_content_hash=compiled_content_hash,
    )


def bind_setup_trigger_pin(key: SetupLifetimeKey, pin: SetupTriggerPin) -> SetupTriggerPin:
    trigger_end = utc_trigger_end(pin.trigger_end)
    lineage = pin.required_lineage_hash or setup_lifetime_lineage_hash(
        key, trigger_end=trigger_end, trigger_bar_hash=pin.trigger_bar_hash
    )
    return SetupTriggerPin(
        trigger_end=trigger_end,
        trigger_bar_hash=pin.trigger_bar_hash,
        expired=pin.expired,
        required_lineage_hash=lineage,
    )


def converge_setup_trigger_pin(
    current: SetupTriggerPin | None, incoming: SetupTriggerPin
) -> SetupTriggerPin | None:
    """Duplicate writes converge. An expired pin cannot resurrect."""

    if current is None:
        return incoming
    same_trigger = (
        current.trigger_end == incoming.trigger_end
        and current.trigger_bar_hash == incoming.trigger_bar_hash
    )
    if current.expired and same_trigger:
        return current
    if current.expired and incoming.trigger_end <= current.trigger_end:
        return current
    if not current.expired and not same_trigger and incoming.trigger_end != current.trigger_end:
        return current
    if current.expired and incoming.trigger_end > current.trigger_end:
        return incoming
    return SetupTriggerPin(
        trigger_end=incoming.trigger_end,
        trigger_bar_hash=incoming.trigger_bar_hash,
        expired=current.expired or incoming.expired,
        required_lineage_hash=incoming.required_lineage_hash or current.required_lineage_hash,
    )


_Index = tuple[UUID, str, str, UUID, UUID, str]


def _index(key: SetupLifetimeKey) -> _Index:
    return (
        key.organization_id,
        key.symbol.upper(),
        key.timeframe.value,
        key.strategy_version_id,
        key.compiled_setup_definition_id,
        key.compiled_content_hash,
    )


__all__ = [
    "SetupLifetimeKey",
    "SetupLifetimePort",
    "SetupLifetimeStore",
    "SetupTriggerPin",
    "bind_setup_trigger_pin",
    "converge_setup_trigger_pin",
    "expiry_bars",
    "lifetime_key_from_policy",
    "setup_lifetime_lineage_hash",
    "utc_trigger_end",
]

"""Process-shared cache for one closed Binance USD-M aggTrade window.

The key is the public retrieval identity (policy, symbol, start, end). It does
not include a tenant. Closed windows are public market data; tenant evidence
stays outside this cache. Entries expire, stay bounded, and a corrected
payload replaces the previous rows instead of merging with them.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.market_contracts.adapters.aggtrades import AGGTRADE_RETRIEVAL_POLICY_VERSION
from app.market_contracts.errors import WrongMarketError
from app.services.canonical_serialization import canonical_sha256

CacheKey = tuple[str, str, str, str]


def closed_agg_trade_window_key(symbol: str, start: datetime, end: datetime) -> CacheKey:
    """Canonical identity of one closed aggTrade window. Time zones collapse to UTC."""

    return (
        AGGTRADE_RETRIEVAL_POLICY_VERSION,
        symbol.upper(),
        _utc_token(start),
        _utc_token(end),
    )


def agg_trade_fingerprint(rows: tuple[Any, ...] | list[Any]) -> str:
    """Semantic fingerprint of aggTrade rows. Receive time is not part of it."""

    projected: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            projected.append({"raw": str(row)})
            continue
        projected.append(
            {
                "a": row.get("a"),
                "p": "" if row.get("p") is None else str(row.get("p")),
                "q": "" if row.get("q") is None else str(row.get("q")),
                "T": row.get("T"),
                "m": bool(row.get("m")),
            }
        )
    return canonical_sha256({"rows": projected})


@dataclass(frozen=True, slots=True)
class _CacheEntry:
    rows: tuple[Any, ...]
    fingerprint: str
    stored_at: float


class ClosedAggTradeCache:
    """Bounded TTL cache. Same-key fetches serialize so one window is one read."""

    def __init__(
        self,
        *,
        max_entries: int,
        ttl_seconds: float,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if max_entries < 1:
            raise ValueError("aggTrade cache must keep at least one entry.")
        if ttl_seconds <= 0:
            raise ValueError("aggTrade cache TTL must be positive.")
        self._max_entries = max_entries
        self._ttl_seconds = ttl_seconds
        self._clock = clock or time.monotonic
        self._entries: OrderedDict[CacheKey, _CacheEntry] = OrderedDict()
        self._locks: dict[CacheKey, threading.Lock] = {}
        self._guard = threading.Lock()
        self._corrections = 0

    @property
    def corrections(self) -> int:
        with self._guard:
            return self._corrections

    def __len__(self) -> int:
        with self._guard:
            return len(self._entries)

    def lock_for(self, key: CacheKey) -> threading.Lock:
        """Return the lock that serializes fetches for ``key``."""

        with self._guard:
            current = self._locks.get(key)
            if current is None:
                current = threading.Lock()
                self._locks[key] = current
            return current

    def get(self, key: CacheKey) -> tuple[Any, ...] | None:
        """Return fresh rows. Expired rows are a miss and are not served."""

        with self._guard:
            entry = self._fresh_entry(key)
            if entry is None:
                return None
            self._entries.move_to_end(key)
            return entry.rows

    def put(self, key: CacheKey, rows: tuple[Any, ...]) -> bool:
        """Store ``rows``. Return True when they correct a different cached payload."""

        fingerprint = agg_trade_fingerprint(rows)
        stored_at = self._clock()
        with self._guard:
            prior = self._entries.get(key)
            corrected = prior is not None and prior.fingerprint != fingerprint
            if corrected:
                self._corrections += 1
            self._entries[key] = _CacheEntry(
                rows=rows,
                fingerprint=fingerprint,
                stored_at=stored_at,
            )
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)
            self._prune_locks()
            return corrected

    def _fresh_entry(self, key: CacheKey) -> _CacheEntry | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        age = self._clock() - entry.stored_at
        if age > self._ttl_seconds:
            return None
        return entry

    def _prune_locks(self) -> None:
        for key, lock in list(self._locks.items()):
            if key in self._entries or lock.locked():
                continue
            self._locks.pop(key, None)


def _utc_token(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise WrongMarketError("AggTrade window bounds must be timezone-aware.")
    return value.astimezone(UTC).isoformat(timespec="microseconds")

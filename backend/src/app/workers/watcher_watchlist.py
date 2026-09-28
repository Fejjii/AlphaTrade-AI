"""Configurable paper Watcher watchlist.

Symbols are added and removed through ``WATCHER_PAPER_SYMBOLS``. Nothing else
is monitored until ``WATCHER_MULTI_SYMBOL_ENABLED`` is true. The default and
every staging/Render process that leaves the flag false keep BTCUSDT only.

Historical candle and trade windows are loaded one symbol at a time.
"""

from __future__ import annotations

import threading
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from app.core.config import Settings
from app.market_contracts.errors import WrongInstrumentError
from app.market_contracts.identity import require_linear_usdt_symbol
from app.workers.watcher_paper_targets import FIRST_SLICE_SYMBOL, normalize_paper_symbols

WATCHLIST_SYMBOL_CAP = 10
SYMBOL_HISTORY_CONCURRENCY = 1

WatchlistActivation = Literal["btc_only", "configured"]


@dataclass(frozen=True, slots=True)
class WatchlistResolution:
    """Configured symbols versus the set this process may actually scan."""

    active: tuple[str, ...]
    configured: tuple[str, ...]
    rejected: tuple[str, ...]
    multi_symbol_enabled: bool
    activation: WatchlistActivation


@dataclass(frozen=True, slots=True)
class SymbolObservation:
    """Source and freshness copied off one symbol scan. Not a price."""

    source: str = "unknown"
    freshness: str = "unknown"
    freshness_seconds: float | None = None

    @classmethod
    def unknown(cls) -> SymbolObservation:
        return cls()


class SymbolHistoryBudget:
    """Allows one historical window in memory at a time."""

    def __init__(self) -> None:
        if SYMBOL_HISTORY_CONCURRENCY != 1:
            raise ValueError("Watcher historical loads stay sequential.")
        self._held: str | None = None
        self._lock = threading.Lock()
        self.peak_in_flight = 0
        self.completed: list[str] = []
        self.rejected_overlaps = 0

    @property
    def held_symbol(self) -> str | None:
        with self._lock:
            return self._held

    def acquire(self, symbol: str) -> None:
        token = symbol.strip().upper()
        with self._lock:
            if self._held is not None:
                self.rejected_overlaps += 1
                raise RuntimeError(
                    f"Refusing to load historical data for {token} "
                    f"while {self._held} is still in memory."
                )
            self._held = token
            self.peak_in_flight = 1

    def release(self, symbol: str) -> None:
        token = symbol.strip().upper()
        with self._lock:
            if self._held != token:
                return
            self._held = None
            self.completed.append(token)


def is_linear_usdt_symbol(symbol: str) -> bool:
    try:
        require_linear_usdt_symbol(symbol)
    except WrongInstrumentError:
        return False
    return True


def resolve_watchlist(
    settings: Settings,
    *,
    symbols: Sequence[str] | None = None,
) -> WatchlistResolution:
    """Resolve the active watchlist. Extra symbols stay inactive while the flag is false."""

    raw = settings.watcher_paper_symbols if symbols is None else symbols
    configured = normalize_paper_symbols(raw)
    rejected = tuple(symbol for symbol in configured if not is_linear_usdt_symbol(symbol))
    rejected_set = set(rejected)
    valid = tuple(symbol for symbol in configured if symbol not in rejected_set)
    if not settings.watcher_multi_symbol_enabled:
        return WatchlistResolution(
            active=(FIRST_SLICE_SYMBOL,),
            configured=configured,
            rejected=rejected,
            multi_symbol_enabled=False,
            activation="btc_only",
        )
    cap = min(int(settings.watcher_paper_max_symbols), WATCHLIST_SYMBOL_CAP)
    active = valid[:cap]
    if FIRST_SLICE_SYMBOL not in active:
        active = (FIRST_SLICE_SYMBOL, *active)[:cap]
    return WatchlistResolution(
        active=active,
        configured=configured,
        rejected=rejected,
        multi_symbol_enabled=True,
        activation="configured",
    )


def effective_watch_symbols(
    settings: Settings,
    *,
    symbols: Sequence[str] | None = None,
) -> tuple[str, ...]:
    """Symbols this process may scan. BTCUSDT only unless multi-symbol is enabled."""

    return resolve_watchlist(settings, symbols=symbols).active

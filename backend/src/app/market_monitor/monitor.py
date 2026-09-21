"""Process-local perpetual market monitor. Tick-driven, no Watcher start."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from threading import Lock

from app.core.errors import ValidationAppError
from app.market_contracts.adapters.protocol import PerpetualMarketSource
from app.market_contracts.catalog import PerpetualInstrumentCatalog, default_perpetual_catalog
from app.market_contracts.errors import WrongInstrumentError
from app.market_contracts.first_slice import canonical_first_slice_clock
from app.market_contracts.identity import InstrumentIdentity
from app.market_monitor.backoff import BackoffPolicy
from app.market_monitor.runtime import SymbolMonitorRuntime
from app.market_monitor.types import SymbolMonitorSnapshot

Clock = Callable[[], datetime]


def _wall_clock() -> datetime:
    return datetime.now(UTC)


class PerpetualMarketMonitor:
    """Continuous read-only snapshots for configured USD-M symbols.

    BTCUSDT is the catalog default. Additional symbols can be registered on the
    catalog without rewriting this monitor. Replay uses the first-slice clock so
    fixture prices stay deterministic and are never live marks.
    """

    def __init__(
        self,
        source: PerpetualMarketSource,
        *,
        replay: bool,
        catalog: PerpetualInstrumentCatalog | None = None,
        backoff: BackoffPolicy | None = None,
        clock: Clock | None = None,
        poll_seconds: float = 2.0,
    ) -> None:
        self._source = source
        self._replay = replay
        self._catalog = catalog if catalog is not None else default_perpetual_catalog()
        self._backoff = backoff if backoff is not None else BackoffPolicy()
        self._clock = clock or _wall_clock
        self._poll = timedelta(seconds=poll_seconds)
        self._runtimes: dict[str, SymbolMonitorRuntime] = {}
        self._last_tick_at: dict[str, datetime] = {}
        self._lock = Lock()

    @property
    def replay(self) -> bool:
        return self._replay

    @property
    def source_name(self) -> str:
        return self._source.name

    def enabled_symbols(self) -> tuple[str, ...]:
        return self._catalog.enabled_symbols()

    def tick(
        self, symbol: str = "BTCUSDT", *, now: datetime | None = None
    ) -> SymbolMonitorSnapshot:
        instrument = self._require(symbol)
        evaluated = self._evaluated_at(now)
        with self._lock:
            runtime = self._runtime_locked(instrument.provider_symbol, evaluated)
            snapshot = runtime.tick(evaluated)
            self._last_tick_at[instrument.provider_symbol] = evaluated
            return snapshot

    def latest(self, symbol: str = "BTCUSDT") -> SymbolMonitorSnapshot:
        """Force a current-quote/stream snapshot for Watcher gating."""

        return self.snapshot(symbol, force=True)

    def snapshot(
        self,
        symbol: str = "BTCUSDT",
        *,
        now: datetime | None = None,
        force: bool = False,
    ) -> SymbolMonitorSnapshot:
        instrument = self._require(symbol)
        evaluated = self._evaluated_at(now)
        with self._lock:
            last = self._last_tick_at.get(instrument.provider_symbol)
            stale_tick = last is None or evaluated - last >= self._poll
            runtime = self._runtime_locked(instrument.provider_symbol, evaluated)
            if force or stale_tick:
                result = runtime.tick(evaluated)
                self._last_tick_at[instrument.provider_symbol] = evaluated
                return result
            return runtime.project(evaluated)

    def restart(self) -> None:
        """Drop all connection epochs. Used by tests to simulate process restart."""
        with self._lock:
            self._runtimes.clear()
            self._last_tick_at.clear()

    def _evaluated_at(self, now: datetime | None) -> datetime:
        if now is not None:
            return now.astimezone(UTC)
        if self._replay:
            return canonical_first_slice_clock().evaluated_at
        return self._clock().astimezone(UTC)

    def _require(self, symbol: str) -> InstrumentIdentity:
        try:
            return self._catalog.require(symbol)
        except WrongInstrumentError as exc:
            raise ValidationAppError(str(exc), code="unknown_perpetual_instrument") from exc

    def _runtime_locked(self, symbol: str, now: datetime) -> SymbolMonitorRuntime:
        runtime = self._runtimes.get(symbol)
        if runtime is None:
            runtime = SymbolMonitorRuntime(
                instrument=self._catalog.require(symbol),
                source=self._source,
                replay=self._replay,
                backoff=self._backoff,
                connected_at=now,
            )
            self._runtimes[symbol] = runtime
        return runtime

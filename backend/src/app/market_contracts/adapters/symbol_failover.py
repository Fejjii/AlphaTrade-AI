"""Per-symbol Binance to Bybit failover.

A primary failure switches only the symbol that failed. Other symbols stay on
the primary venue. The secondary payload is never labelled with the primary
instrument. Secondary clients are created lazily and only for symbols that
actually switch, up to the configured watchlist.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from threading import Lock
from typing import NoReturn
from uuid import UUID

from app.market_contracts.adapters.protocol import PerpetualMarketSource
from app.market_contracts.errors import (
    EvidenceSourceSwitchRequiredError,
    RateLimitedError,
    RegionalProviderFailureError,
    UpstreamBanError,
    WrongInstrumentError,
    WrongSourceError,
)
from app.market_contracts.identity import EvidenceMarketIdentity, InstrumentIdentity
from app.market_contracts.ohlcv import ClosedOhlcvSeries
from app.market_contracts.trades import OrderedTradeBatch
from app.providers.base import ProviderHealth, ProviderKind, ProviderStatus
from app.schemas.common import Timeframe

_SWITCH_ERRORS = (UpstreamBanError, RegionalProviderFailureError, RateLimitedError)

InstrumentForSymbol = Callable[[str], InstrumentIdentity]
SecondaryFactory = Callable[[str], PerpetualMarketSource]


class PerSymbolFailoverSource:
    """One primary source, with an independent secondary switch per symbol."""

    def __init__(
        self,
        primary: PerpetualMarketSource,
        *,
        symbols: tuple[str, ...] | list[str],
        primary_instrument_for: InstrumentForSymbol,
        secondary_instrument_for: InstrumentForSymbol,
        secondary_factory: SecondaryFactory,
    ) -> None:
        if primary.kind is not ProviderKind.MARKET_DATA:
            raise WrongSourceError(
                "Primary perpetual source must report the market_data provider kind."
            )
        ordered: list[str] = []
        seen: set[str] = set()
        for raw in symbols:
            token = raw.strip().upper()
            if not token or token in seen:
                continue
            seen.add(token)
            ordered.append(token)
        if not ordered:
            raise WrongInstrumentError("Per-symbol failover requires at least one symbol.")
        self._primary = primary
        self._symbols = tuple(ordered)
        self._primary_instrument_for = primary_instrument_for
        self._secondary_instrument_for = secondary_instrument_for
        self._secondary_factory = secondary_factory
        self._using_secondary = dict.fromkeys(self._symbols, False)
        self._secondary: dict[str, PerpetualMarketSource] = {}
        self._lock = Lock()
        self.name = primary.name
        self.kind: ProviderKind = ProviderKind.MARKET_DATA

    @property
    def symbols(self) -> tuple[str, ...]:
        return self._symbols

    def using_secondary(self, symbol: str) -> bool:
        token = self._require_symbol(symbol)
        with self._lock:
            return self._using_secondary[token]

    def active_instrument_for(self, symbol: str) -> InstrumentIdentity:
        token = self._require_symbol(symbol)
        with self._lock:
            secondary = self._using_secondary[token]
        if secondary:
            return self._secondary_instrument_for(token)
        return self._primary_instrument_for(token)

    def active_instrument(self) -> InstrumentIdentity:
        if len(self._symbols) == 1:
            return self.active_instrument_for(self._symbols[0])
        raise WrongInstrumentError(
            "Per-symbol failover has no single active instrument. "
            "Use active_instrument_for(symbol)."
        )

    def fetch_closed_ohlcv(
        self,
        *,
        identity: EvidenceMarketIdentity,
        instrument: InstrumentIdentity,
        timeframe: Timeframe,
        min_final_bars: int,
        evaluated_at: datetime,
    ) -> ClosedOhlcvSeries:
        symbol = instrument.provider_symbol
        self._require_active_identity(identity, instrument)
        try:
            return self._active_source(symbol).fetch_closed_ohlcv(
                identity=identity,
                instrument=instrument,
                timeframe=timeframe,
                min_final_bars=min_final_bars,
                evaluated_at=evaluated_at,
            )
        except _SWITCH_ERRORS as exc:
            self._switch(symbol, exc)

    def fetch_ordered_trades(
        self,
        *,
        identity: EvidenceMarketIdentity,
        instrument: InstrumentIdentity,
        start: datetime,
        end: datetime,
        source_connection_id: UUID,
        receive_at: datetime,
    ) -> OrderedTradeBatch:
        symbol = instrument.provider_symbol
        self._require_active_identity(identity, instrument)
        try:
            return self._active_source(symbol).fetch_ordered_trades(
                identity=identity,
                instrument=instrument,
                start=start,
                end=end,
                source_connection_id=source_connection_id,
                receive_at=receive_at,
            )
        except _SWITCH_ERRORS as exc:
            self._switch(symbol, exc)

    def status(self) -> ProviderStatus:
        base = self._primary.status()
        with self._lock:
            switched = [symbol for symbol, active in self._using_secondary.items() if active]
        self.name = self._primary.name
        if not switched:
            return base
        detail = f"secondary active for {', '.join(switched)}"
        return ProviderStatus(
            name=self.name,
            kind=self.kind,
            health=base.health,
            using_fallback=True,
            is_mock=base.is_mock,
            detail=detail,
            last_success_at=base.last_success_at,
            error_message=base.error_message,
        )

    def try_recover_primary(self, symbol: str | None = None) -> InstrumentIdentity | None:
        """Recover one symbol when the primary is healthy. Leave the others."""

        if symbol is None:
            return None
        token = self._require_symbol(symbol)
        with self._lock:
            if not self._using_secondary[token]:
                return None
        report = self._primary.status()
        if report.health is not ProviderHealth.HEALTHY or report.using_fallback or report.is_mock:
            return None
        with self._lock:
            self._using_secondary[token] = False
        self.name = self._primary.name
        return self._primary_instrument_for(token)

    def _require_symbol(self, symbol: str) -> str:
        token = symbol.strip().upper()
        if token not in self._using_secondary:
            enabled = ", ".join(self._symbols)
            raise WrongInstrumentError(
                f"Per-symbol failover does not include {token}. Enabled: {enabled}."
            )
        return token

    def _active_source(self, symbol: str) -> PerpetualMarketSource:
        token = self._require_symbol(symbol)
        with self._lock:
            secondary = self._using_secondary[token]
        if secondary:
            return self._secondary_for(token)
        return self._primary

    def _secondary_for(self, symbol: str) -> PerpetualMarketSource:
        with self._lock:
            existing = self._secondary.get(symbol)
            if existing is not None:
                return existing
            if len(self._secondary) >= len(self._symbols):
                raise WrongInstrumentError("Secondary perpetual clients exceed the watchlist.")
        source = self._secondary_factory(symbol)
        if source.kind is not ProviderKind.MARKET_DATA:
            raise WrongSourceError(
                "Secondary perpetual source must report the market_data provider kind."
            )
        with self._lock:
            current = self._secondary.get(symbol)
            if current is not None:
                return current
            self._secondary[symbol] = source
            return source

    def _require_active_identity(
        self,
        identity: EvidenceMarketIdentity,
        instrument: InstrumentIdentity,
    ) -> None:
        active = self.active_instrument_for(instrument.provider_symbol)
        if identity.venue is active.venue and instrument.instrument_id == active.instrument_id:
            return
        if self.using_secondary(instrument.provider_symbol):
            raise EvidenceSourceSwitchRequiredError(
                "Previous venue identity cannot label the secondary source.",
                instrument=active,
            )
        raise WrongSourceError("Evidence identity does not match the active perpetual source.")

    def _switch(self, symbol: str, exc: Exception) -> NoReturn:
        token = self._require_symbol(symbol)
        with self._lock:
            if self._using_secondary[token]:
                raise exc
            self._using_secondary[token] = True
        secondary_instrument = self._secondary_instrument_for(token)
        raise EvidenceSourceSwitchRequiredError(
            "Primary perpetual source failed for one symbol. "
            "The primary payload was not published.",
            instrument=secondary_instrument,
        ) from exc

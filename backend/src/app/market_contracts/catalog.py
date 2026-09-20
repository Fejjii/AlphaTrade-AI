"""Enabled USD-M perpetual instruments for the evidence pipeline.

BTCUSDT is the first vertical slice. Additional symbols can be registered on a
catalog copy without rewriting the assembler. Unregistered symbols fail closed.
Spot and Coin-M identities cannot be registered.
"""

from __future__ import annotations

from app.market_contracts.enums import MarketType, ProductFamily, VenueId
from app.market_contracts.errors import WrongInstrumentError, WrongMarketError
from app.market_contracts.identity import InstrumentIdentity, binance_usdm_btcusdt


class PerpetualInstrumentCatalog:
    """Immutable enabled-set of USD-M perpetual instruments."""

    def __init__(self, enabled: tuple[InstrumentIdentity, ...] | None = None) -> None:
        instruments = enabled if enabled is not None else (binance_usdm_btcusdt(),)
        by_symbol: dict[str, InstrumentIdentity] = {}
        for instrument in instruments:
            _require_usdm_perpetual(instrument)
            previous = by_symbol.get(instrument.provider_symbol)
            if previous is not None and previous.instrument_id != instrument.instrument_id:
                raise WrongInstrumentError(
                    f"Conflicting catalog identity for {instrument.provider_symbol}."
                )
            by_symbol[instrument.provider_symbol] = instrument
        if not by_symbol:
            raise WrongInstrumentError("Perpetual evidence catalog cannot be empty.")
        self._by_symbol = by_symbol

    def enabled_symbols(self) -> tuple[str, ...]:
        return tuple(sorted(self._by_symbol))

    def get(self, symbol: str) -> InstrumentIdentity | None:
        return self._by_symbol.get(symbol.strip().upper())

    def require(self, symbol: str) -> InstrumentIdentity:
        token = symbol.strip().upper()
        instrument = self._by_symbol.get(token)
        if instrument is None:
            enabled = ", ".join(self.enabled_symbols())
            raise WrongInstrumentError(
                f"Perpetual evidence instrument {token} is not enabled. Enabled: {enabled}."
            )
        return instrument

    def extend(self, instrument: InstrumentIdentity) -> PerpetualInstrumentCatalog:
        """Return a new catalog including ``instrument``. Does not mutate self."""
        _require_usdm_perpetual(instrument)
        merged: dict[str, InstrumentIdentity] = dict(self._by_symbol)
        merged[instrument.provider_symbol] = instrument
        return PerpetualInstrumentCatalog(enabled=tuple(merged.values()))


def _require_usdm_perpetual(instrument: InstrumentIdentity) -> None:
    if instrument.venue is not VenueId.BINANCE:
        raise WrongMarketError("Perpetual evidence catalog is Binance USD-M only.")
    if instrument.market_type is not MarketType.PERPETUAL:
        raise WrongMarketError("Spot or delivery instruments cannot enter the perpetual catalog.")
    if instrument.product_family is not ProductFamily.USDM_FUTURES:
        raise WrongMarketError("Coin-M or spot product families cannot enter the USD-M catalog.")


def default_perpetual_catalog() -> PerpetualInstrumentCatalog:
    """Production default: BTCUSDT first slice only."""
    return PerpetualInstrumentCatalog()

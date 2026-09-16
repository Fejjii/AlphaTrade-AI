"""Fail-closed errors for perpetual market source contracts."""

from __future__ import annotations


class MarketContractError(ValueError):
    """Base error for evidence that cannot be used."""


class FormingCandleError(MarketContractError):
    """A forming (non-final) candle was supplied where FINAL is required."""


class WrongMarketError(MarketContractError):
    """Venue or market type is incompatible with the requested evidence contract."""


class WrongInstrumentError(MarketContractError):
    """Instrument identity does not match the requested canonical instrument."""


class GapDetectedError(MarketContractError):
    """A sequence or interval gap was detected in the selected evidence."""


class UnrecoverableGapError(GapDetectedError):
    """A gap remains after bounded reconnect backfill and must fail closed."""


class DuplicateDataError(MarketContractError):
    """The same natural event arrived with conflicting semantic content."""


class OutOfOrderTradesError(MarketContractError):
    """Trades arrived out of venue sequence without an explicit reconnect."""


class StaleEvidenceError(MarketContractError):
    """Evidence exceeded the versioned freshness policy."""


class UnknownAggressorError(MarketContractError):
    """Aggressor side or convention is missing, so signed flow is unusable."""


class IncompleteWarmUpError(MarketContractError):
    """CVD/flow was requested before contiguous warm-up completed."""


class SpotFallbackRejectedError(MarketContractError):
    """Spot (or other incompatible) market data cannot satisfy perpetual evidence."""


class RegionalProviderFailureError(MarketContractError):
    """The preferred perpetual source is unreachable in this runtime region."""


class NetworkMutationForbiddenError(MarketContractError):
    """The read-only adapter refused a non-GET or non-allowlisted path."""


class CursorRecoveryError(MarketContractError):
    """Reconnect recovery could not prove contiguous coverage."""


class FallbackForbiddenError(MarketContractError):
    """Silent fallback across providers, markets, or mock substitutes is forbidden."""

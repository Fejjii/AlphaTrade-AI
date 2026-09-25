"""Versioned enumerations for market source contracts."""

from __future__ import annotations

from enum import StrEnum


class VenueId(StrEnum):
    BINANCE = "binance"
    BLOFIN = "blofin"
    BYBIT = "bybit"


class MarketType(StrEnum):
    PERPETUAL = "perpetual"
    SPOT = "spot"
    DELIVERY = "delivery"
    COIN_M_PERPETUAL = "coin_m_perpetual"
    OPTION = "option"


class ContractStyle(StrEnum):
    LINEAR = "linear"
    INVERSE = "inverse"


class ProductFamily(StrEnum):
    USDM_FUTURES = "usdm_futures"
    COINM_FUTURES = "coinm_futures"
    SPOT = "spot"


class Finality(StrEnum):
    FINAL = "final"
    FORMING = "forming"
    CORRECTED = "corrected"
    UNKNOWN = "unknown"


class FreshnessState(StrEnum):
    FRESH = "fresh"
    AGING = "aging"
    STALE = "stale"
    GAP = "gap"
    UNKNOWN = "unknown"


class GapState(StrEnum):
    NONE = "none"
    SUSPECTED = "suspected"
    CONFIRMED = "confirmed"
    UNRECOVERABLE = "unrecoverable"


class ReconnectState(StrEnum):
    INITIAL = "initial"
    CONTINUOUS = "continuous"
    RECONNECTING = "reconnecting"
    RECOVERED = "recovered"


class WarmUpStatus(StrEnum):
    EMPTY = "empty"
    BACKFILLING = "backfilling"
    COMPLETE = "complete"
    FAILED = "failed"


class AggressorSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class DataCompleteness(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class ObservationType(StrEnum):
    OHLCV = "ohlcv"
    TRADE = "trade"
    CVD = "cvd"
    ORDER_BOOK = "order_book"
    VOLUME = "volume"
    STRUCTURE = "structure"


class QuantityKind(StrEnum):
    BASE = "base"
    CONTRACT = "contract"
    QUOTE = "quote"
    SETTLEMENT = "settlement"
    TRADE_COUNT = "trade_count"


class PrivacyClass(StrEnum):
    PUBLIC_MARKET_DATA = "public_market_data"


class SourceFamily(StrEnum):
    BINANCE_USDM_FUTURES_PUBLIC = "binance_usdm_futures_public"
    BYBIT_USDT_PERPETUAL_PUBLIC = "bybit_usdt_perpetual_public"
    REPLAY_FIXTURE = "replay_fixture"

"""Read-only BloFin demo market data provider.

Implements the platform's :class:`MarketDataProvider` protocol against BloFin
public (demo) endpoints, with a deterministic mock fallback so the system stays
runnable when the venue is unreachable. No API key is used for public data.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import structlog

from app.providers.base import ProviderHealth, ProviderKind, ProviderStatus
from app.providers.exchange.blofin_client import BloFinClient
from app.providers.exchange.errors import ExchangeError
from app.providers.exchange.mapping import timeframe_to_bar, to_blofin_inst_id
from app.providers.market_data import (
    TIMEFRAME_SECONDS,
    FundingRateData,
    MarketDataEnvelope,
    MockMarketDataProvider,
    OHLCVBar,
    OHLCVData,
    OpenInterestData,
    OrderBookLevel,
    OrderBookSnapshot,
    TickerData,
    _is_stale,
    normalize_symbol,
)
from app.schemas.common import Timeframe

logger = structlog.get_logger(__name__)

TICKER_STALE_SECONDS = 60


class BloFinMarketDataProvider:
    """BloFin demo market data with mock fallback (read-only)."""

    name = "blofin-demo-market-data"
    kind = ProviderKind.MARKET_DATA

    def __init__(
        self,
        client: BloFinClient,
        *,
        fallback: MockMarketDataProvider | None = None,
    ) -> None:
        self._client = client
        self._fallback = fallback or MockMarketDataProvider()
        self._using_fallback = False
        self._last_success_at: datetime | None = None
        self._last_error: str | None = None

    def _envelope(
        self,
        *,
        symbol: str,
        exchange: str,
        timeframe: Timeframe | None,
        timestamp: datetime,
        is_stale: bool = False,
        stale_reason: str | None = None,
    ) -> MarketDataEnvelope:
        return MarketDataEnvelope(
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            timestamp=timestamp,
            source="blofin-demo",
            is_live=True,
            is_stale=is_stale,
            stale_reason=stale_reason,
            provider_name=self.name,
            fallback_used=False,
        )

    def _record_failure(self, exc: Exception) -> None:
        self._using_fallback = True
        self._last_error = str(exc)[:200]

    def get_ticker(self, symbol: str, *, exchange: str = "blofin") -> TickerData:
        sym = normalize_symbol(symbol)
        try:
            data = self._client.request(
                "GET", "/api/v1/market/tickers", params={"instId": to_blofin_inst_id(symbol)}
            )
            row = data[0] if isinstance(data, list) and data else data
            if not isinstance(row, dict):
                raise ExchangeError("Unexpected ticker payload.")
            self._using_fallback = False
            self._last_success_at = datetime.now(UTC)
            self._last_error = None
            ts = datetime.now(UTC)
            is_stale, reason = _is_stale(
                ts, max_age_seconds=TICKER_STALE_SECONDS, reason="Ticker older than 60s"
            )
            last = Decimal(str(row.get("last", row.get("lastPrice", "0"))))
            return TickerData(
                envelope=self._envelope(
                    symbol=sym,
                    exchange=exchange,
                    timeframe=None,
                    timestamp=ts,
                    is_stale=is_stale,
                    stale_reason=reason,
                ),
                last_price=last,
                bid=Decimal(str(row.get("bidPrice", last))),
                ask=Decimal(str(row.get("askPrice", last))),
                volume_24h=Decimal(str(row.get("vol24h", row.get("volCurrency24h", "0")))),
                change_24h_pct=float(row.get("changePercent24h", 0) or 0),
            )
        except Exception as exc:  # fall back to deterministic mock on any failure
            logger.warning("blofin_ticker_failed", symbol=sym, error=str(exc)[:200])
            self._record_failure(exc)
            return self._fallback.get_ticker(symbol, exchange=exchange)

    def get_ohlcv(
        self,
        symbol: str,
        timeframe: Timeframe,
        *,
        exchange: str = "blofin",
        limit: int = 100,
    ) -> OHLCVData:
        sym = normalize_symbol(symbol)
        try:
            data = self._client.request(
                "GET",
                "/api/v1/market/candles",
                params={
                    "instId": to_blofin_inst_id(symbol),
                    "bar": timeframe_to_bar(timeframe),
                    "limit": min(limit, 1000),
                },
            )
            if not isinstance(data, list):
                raise ExchangeError("Unexpected candles payload.")
            bars = [self._parse_candle(row) for row in data]
            # BloFin returns newest-first; platform expects oldest-first.
            bars = [b for b in bars if b is not None][::-1]
            self._using_fallback = False
            self._last_success_at = datetime.now(UTC)
            self._last_error = None
            latest_ts = bars[-1].timestamp if bars else datetime.now(UTC)
            max_age = TIMEFRAME_SECONDS.get(timeframe, 3600) * 2
            is_stale, reason = _is_stale(
                latest_ts, max_age_seconds=max_age, reason=f"Latest candle older than {max_age}s"
            )
            return OHLCVData(
                envelope=self._envelope(
                    symbol=sym,
                    exchange=exchange,
                    timeframe=timeframe,
                    timestamp=latest_ts,
                    is_stale=is_stale,
                    stale_reason=reason,
                ),
                bars=bars,
            )
        except Exception as exc:
            logger.warning("blofin_ohlcv_failed", symbol=sym, error=str(exc)[:200])
            self._record_failure(exc)
            return self._fallback.get_ohlcv(symbol, timeframe, exchange=exchange, limit=limit)

    @staticmethod
    def _parse_candle(row: Any) -> OHLCVBar | None:
        try:
            ts = datetime.fromtimestamp(int(row[0]) / 1000, tz=UTC)
            return OHLCVBar(
                open=Decimal(str(row[1])),
                high=Decimal(str(row[2])),
                low=Decimal(str(row[3])),
                close=Decimal(str(row[4])),
                volume=Decimal(str(row[5])),
                timestamp=ts,
            )
        except (IndexError, ValueError, TypeError):
            return None

    def get_funding_rate(self, symbol: str, *, exchange: str = "blofin") -> FundingRateData | None:
        sym = normalize_symbol(symbol)
        try:
            data = self._client.request(
                "GET", "/api/v1/market/funding-rate", params={"instId": to_blofin_inst_id(symbol)}
            )
            row = data[0] if isinstance(data, list) and data else data
            if not isinstance(row, dict):
                raise ExchangeError("Unexpected funding payload.")
            self._using_fallback = False
            self._last_success_at = datetime.now(UTC)
            return FundingRateData(
                envelope=self._envelope(
                    symbol=sym, exchange=exchange, timeframe=None, timestamp=datetime.now(UTC)
                ),
                funding_rate=Decimal(str(row.get("fundingRate", "0"))),
            )
        except Exception as exc:
            logger.warning("blofin_funding_failed", symbol=sym, error=str(exc)[:200])
            self._record_failure(exc)
            return self._fallback.get_funding_rate(symbol, exchange=exchange)

    def get_open_interest(
        self, symbol: str, *, exchange: str = "blofin"
    ) -> OpenInterestData | None:
        # BloFin open interest is not mapped yet; use deterministic fallback.
        return self._fallback.get_open_interest(symbol, exchange=exchange)

    def get_order_book_snapshot(
        self,
        symbol: str,
        *,
        exchange: str = "blofin",
        depth: int = 10,
    ) -> OrderBookSnapshot | None:
        sym = normalize_symbol(symbol)
        try:
            data = self._client.request(
                "GET",
                "/api/v1/market/books",
                params={"instId": to_blofin_inst_id(symbol), "size": min(depth, 100)},
            )
            row = data[0] if isinstance(data, list) and data else data
            if not isinstance(row, dict):
                raise ExchangeError("Unexpected order book payload.")
            self._using_fallback = False
            self._last_success_at = datetime.now(UTC)
            bids = [
                OrderBookLevel(price=Decimal(str(p)), size=Decimal(str(s)))
                for p, s, *_ in row.get("bids", [])[:depth]
            ]
            asks = [
                OrderBookLevel(price=Decimal(str(p)), size=Decimal(str(s)))
                for p, s, *_ in row.get("asks", [])[:depth]
            ]
            return OrderBookSnapshot(
                envelope=self._envelope(
                    symbol=sym, exchange=exchange, timeframe=None, timestamp=datetime.now(UTC)
                ),
                bids=bids,
                asks=asks,
            )
        except Exception as exc:
            logger.warning("blofin_orderbook_failed", symbol=sym, error=str(exc)[:200])
            self._record_failure(exc)
            return self._fallback.get_order_book_snapshot(symbol, exchange=exchange, depth=depth)

    def status(self) -> ProviderStatus:
        if self._using_fallback and self._last_error:
            return ProviderStatus(
                name=self.name,
                kind=self.kind,
                health=ProviderHealth.DEGRADED,
                using_fallback=True,
                is_mock=False,
                detail="BloFin demo market data unavailable — mock fallback active.",
                last_success_at=self._last_success_at,
                error_message=self._client.last_error,
            )
        return ProviderStatus(
            name=self.name,
            kind=self.kind,
            health=ProviderHealth.HEALTHY,
            using_fallback=False,
            is_mock=False,
            detail="BloFin demo market data (read-only).",
            last_success_at=self._last_success_at,
        )

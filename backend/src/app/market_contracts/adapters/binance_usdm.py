"""Binance USD-M Futures public REST adapter (read-only, no fallback)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

import httpx

from app.market_contracts.adapters.aggtrades import fetch_complete_agg_trade_rows
from app.market_contracts.adapters.http import ReadOnlyHttpGetClient
from app.market_contracts.coverage import build_complete_trade_window_coverage
from app.market_contracts.enums import MarketType, ProductFamily, SourceFamily, VenueId
from app.market_contracts.errors import (
    FallbackForbiddenError,
    FormingCandleError,
    RegionalProviderFailureError,
    SpotFallbackRejectedError,
    WrongInstrumentError,
    WrongMarketError,
)
from app.market_contracts.first_slice import first_slice_identity
from app.market_contracts.freshness import first_slice_freshness_policy
from app.market_contracts.hashing import with_content_hash
from app.market_contracts.identity import (
    ADAPTER_VERSION,
    EvidenceMarketIdentity,
    InstrumentIdentity,
    binance_usdm_btcusdt,
    require_instrument,
    require_perpetual,
)
from app.market_contracts.ohlcv import (
    ClosedOhlcvSeries,
    OhlcvBar,
    build_ohlcv_bar,
    require_closed_series,
)
from app.market_contracts.trades import (
    OrderedTradeBatch,
    TradeEvent,
    build_trade_event,
    order_trades,
)
from app.providers.base import ProviderHealth, ProviderKind, ProviderStatus
from app.schemas.common import Timeframe

_BINANCE_INTERVAL = {
    Timeframe.M15: "15m",
    Timeframe.H4: "4h",
}


class BinanceUsdmPerpetualSource:
    """Preferred first-slice evidence source: Binance USD-M perpetual public REST."""

    name = "binance-usdm-perpetual"
    kind = ProviderKind.MARKET_DATA

    def __init__(
        self,
        *,
        base_url: str = "https://fapi.binance.com",
        timeout_seconds: float = 10.0,
        transport: httpx.BaseTransport | None = None,
        client: ReadOnlyHttpGetClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._http = client or ReadOnlyHttpGetClient(
            base_url=self._base_url,
            timeout_seconds=timeout_seconds,
            transport=transport,
        )
        self._last_success_at: datetime | None = None
        self._last_error: str | None = None
        self._regional_failure = False

    def fetch_closed_ohlcv(
        self,
        *,
        identity: EvidenceMarketIdentity,
        instrument: InstrumentIdentity,
        timeframe: Timeframe,
        min_final_bars: int,
        evaluated_at: datetime,
    ) -> ClosedOhlcvSeries:
        self._assert_request(identity, instrument, timeframe)
        interval = _BINANCE_INTERVAL.get(timeframe)
        if interval is None:
            raise WrongMarketError(
                f"Timeframe {timeframe.value} is not contracted for USD-M evidence."
            )
        limit = min(max(min_final_bars + 2, min_final_bars), 1500)
        payload = self._get(
            "/fapi/v1/klines",
            {
                "symbol": instrument.provider_symbol,
                "interval": interval,
                "limit": limit,
            },
        )
        if not isinstance(payload, list):
            raise WrongMarketError("USD-M kline payload is not a list.")
        grace = timedelta(seconds=first_slice_freshness_policy().ohlcv_post_close_grace_seconds)
        bars: list[OhlcvBar] = []
        for row in payload:
            bars.append(
                self._parse_kline(
                    row,
                    instrument=instrument,
                    timeframe=timeframe,
                    evaluated_at=evaluated_at,
                    grace=grace,
                )
            )
        final_bars = [bar for bar in bars if bar.finality.value == "final"]
        if len(final_bars) < min_final_bars:
            raise FormingCandleError(
                f"Need {min_final_bars} final {timeframe.value} candles; "
                f"received {len(final_bars)} final and {len(bars) - len(final_bars)} non-final."
            )
        return require_closed_series(
            final_bars,
            identity=identity,
            timeframe=timeframe,
            evaluated_at=evaluated_at,
            min_bars=min_final_bars,
        )

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
        self._assert_request(identity, instrument, identity.timeframe)
        if end <= start:
            raise WrongMarketError("Trade window end must be after start.")
        rows = fetch_complete_agg_trade_rows(
            get_json=self._get,
            symbol=instrument.provider_symbol,
            start=start,
            end=end,
        )
        raw_trades = [
            self._parse_agg_trade(
                row,
                instrument=instrument,
                source_connection_id=source_connection_id,
                receive_at=receive_at,
            )
            for row in rows
        ]
        ordered = order_trades(raw_trades)
        coverage = build_complete_trade_window_coverage(
            identity=identity,
            lineage_id=source_connection_id,
            requested_start=start,
            requested_end=end,
            trades=ordered,
        )
        batch = OrderedTradeBatch(
            identity=identity,
            trades=ordered,
            source_connection_id=source_connection_id,
            coverage=coverage,
            content_hash="0" * 64,
        )
        return with_content_hash(batch)

    def status(self) -> ProviderStatus:
        try:
            self._get("/fapi/v1/ping", None)
            self._regional_failure = False
            self._last_error = None
            self._last_success_at = datetime.now(UTC)
            return ProviderStatus(
                name=self.name,
                kind=self.kind,
                health=ProviderHealth.HEALTHY,
                using_fallback=False,
                is_mock=False,
                detail="Binance USD-M futures public REST (read-only, no spot fallback).",
                last_success_at=self._last_success_at,
                error_message=None,
            )
        except RegionalProviderFailureError as exc:
            self._regional_failure = True
            self._last_error = str(exc)[:200]
            return ProviderStatus(
                name=self.name,
                kind=self.kind,
                health=ProviderHealth.UNAVAILABLE,
                using_fallback=False,
                is_mock=False,
                detail="Preferred USD-M perpetual source unreachable; no spot fallback.",
                last_success_at=self._last_success_at,
                error_message=self._last_error,
            )
        except (SpotFallbackRejectedError, WrongMarketError, FallbackForbiddenError) as exc:
            self._last_error = str(exc)[:200]
            return ProviderStatus(
                name=self.name,
                kind=self.kind,
                health=ProviderHealth.UNAVAILABLE,
                using_fallback=False,
                is_mock=False,
                detail="Perpetual evidence source misconfigured; refusing incompatible market.",
                last_success_at=self._last_success_at,
                error_message=self._last_error,
            )

    def verify_exchange_info(self, instrument: InstrumentIdentity) -> None:
        payload = self._get("/fapi/v1/exchangeInfo", {"symbol": instrument.provider_symbol})
        if not isinstance(payload, dict):
            raise WrongMarketError("exchangeInfo payload is not an object.")
        symbols = payload.get("symbols")
        if not isinstance(symbols, list) or not symbols:
            raise WrongInstrumentError(f"USD-M exchangeInfo missing {instrument.provider_symbol}.")
        info = symbols[0]
        if str(info.get("symbol", "")).upper() != instrument.provider_symbol:
            raise WrongInstrumentError(
                "exchangeInfo symbol does not match the requested instrument."
            )
        contract_type = str(info.get("contractType", "")).upper()
        if contract_type != "PERPETUAL":
            raise WrongMarketError(f"USD-M contractType {contract_type} is not PERPETUAL.")
        quote = str(info.get("quoteAsset", "")).upper()
        if quote != instrument.quote_asset:
            raise WrongMarketError("USD-M quote asset does not match the contracted instrument.")

    def _assert_request(
        self,
        identity: EvidenceMarketIdentity,
        instrument: InstrumentIdentity,
        timeframe: Timeframe | None,
    ) -> None:
        require_perpetual(identity)
        require_instrument(identity, instrument)
        expected = binance_usdm_btcusdt()
        if instrument.instrument_id != expected.instrument_id:
            raise WrongInstrumentError(
                "This adapter is contracted for Binance USD-M BTCUSDT perpetual only."
            )
        if identity.venue is not VenueId.BINANCE:
            raise WrongMarketError("Binance USD-M adapter cannot serve a non-Binance venue.")
        if identity.instrument.product_family is not ProductFamily.USDM_FUTURES:
            raise WrongMarketError("Binance USD-M adapter cannot serve a non-USD-M product.")
        if identity.instrument.market_type is not MarketType.PERPETUAL:
            raise WrongMarketError("Binance USD-M adapter cannot serve non-perpetual markets.")
        if identity.source.family is SourceFamily.REPLAY_FIXTURE:
            raise FallbackForbiddenError(
                "Live USD-M adapter cannot be labelled as a replay source."
            )
        if identity.provenance.fallback_used:
            raise FallbackForbiddenError("Live USD-M evidence cannot record fallback_used=true.")
        if timeframe is not None and identity.timeframe not in {None, timeframe}:
            raise WrongMarketError("Identity timeframe does not match the requested timeframe.")

    def _parse_kline(
        self,
        row: Any,
        *,
        instrument: InstrumentIdentity,
        timeframe: Timeframe,
        evaluated_at: datetime,
        grace: timedelta,
    ) -> OhlcvBar:
        if not isinstance(row, list) or len(row) < 8:
            raise WrongMarketError("USD-M kline row is malformed.")
        open_ms = int(row[0])
        interval_start = datetime.fromtimestamp(open_ms / 1000, tz=UTC)
        quote_volume = Decimal(str(row[7]))
        trade_count = int(row[8]) if len(row) > 8 else None
        return build_ohlcv_bar(
            instrument=instrument,
            timeframe=timeframe,
            interval_start=interval_start,
            open_=Decimal(str(row[1])),
            high=Decimal(str(row[2])),
            low=Decimal(str(row[3])),
            close=Decimal(str(row[4])),
            base_volume=Decimal(str(row[5])),
            quote_volume=quote_volume,
            evaluated_at=evaluated_at,
            grace=grace,
            trade_count=trade_count,
            adapter_version=ADAPTER_VERSION,
        )

    def _parse_agg_trade(
        self,
        row: Any,
        *,
        instrument: InstrumentIdentity,
        source_connection_id: UUID,
        receive_at: datetime,
    ) -> TradeEvent:
        if not isinstance(row, dict):
            raise WrongMarketError("USD-M aggTrade row is malformed.")
        if "m" not in row:
            raise WrongMarketError("USD-M aggTrade is missing buyer-is-maker flag.")
        venue_trade_id = str(row["a"])
        event_ms = int(row["T"])
        return build_trade_event(
            instrument=instrument,
            venue_trade_id=venue_trade_id,
            sequence=int(row["a"]),
            price=Decimal(str(row["p"])),
            quantity=Decimal(str(row["q"])),
            buyer_is_maker=bool(row["m"]),
            event_timestamp=datetime.fromtimestamp(event_ms / 1000, tz=UTC),
            receive_timestamp=receive_at.astimezone(UTC),
            source_connection_id=source_connection_id,
            adapter_version=ADAPTER_VERSION,
        )

    def _get(self, path: str, params: Mapping[str, str | int] | None) -> Any:
        try:
            payload = self._http.get_json(path, params)
        except RegionalProviderFailureError:
            self._regional_failure = True
            raise
        except SpotFallbackRejectedError:
            raise
        self._last_success_at = datetime.now(UTC)
        self._last_error = None
        self._regional_failure = False
        return payload


def live_first_slice_identity(timeframe: Timeframe) -> EvidenceMarketIdentity:
    return first_slice_identity(timeframe=timeframe, replay=False, is_live=True)

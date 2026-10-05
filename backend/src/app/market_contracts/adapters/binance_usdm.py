"""Binance USD-M Futures public REST adapter (read-only, no fallback)."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

import httpx

from app.market_contracts.adapters.aggtrade_cache import (
    ClosedAggTradeCache,
    TtlValueCache,
    closed_agg_trade_window_key,
)
from app.market_contracts.adapters.aggtrades import (
    fetch_complete_agg_trade_rows,
    iter_contiguous_agg_trade_rows,
)
from app.market_contracts.adapters.http import ReadOnlyHttpGetClient
from app.market_contracts.adapters.request_budget import SlidingWeightBudget, record_cache_hit
from app.market_contracts.catalog import PerpetualInstrumentCatalog, default_perpetual_catalog
from app.market_contracts.coverage import build_complete_trade_window_coverage
from app.market_contracts.cursor import TradeStreamSnapshot
from app.market_contracts.derivatives import (
    DerivativeMetric,
    DerivativeObservation,
    derivative_observation,
)
from app.market_contracts.enums import MarketType, ProductFamily, SourceFamily, VenueId
from app.market_contracts.errors import (
    FallbackForbiddenError,
    FormingCandleError,
    RegionalProviderFailureError,
    SpotFallbackRejectedError,
    UnsupportedTradeContractError,
    UpstreamBanError,
    WrongInstrumentError,
    WrongMarketError,
    WrongSourceError,
)
from app.market_contracts.first_slice import first_slice_identity
from app.market_contracts.freshness import first_slice_freshness_policy
from app.market_contracts.hashing import with_content_hash
from app.market_contracts.identity import (
    ADAPTER_VERSION,
    EvidenceMarketIdentity,
    InstrumentIdentity,
    binance_usdm_perpetual,
    require_instrument,
    require_perpetual,
)
from app.market_contracts.ohlcv import (
    ClosedOhlcvSeries,
    OhlcvBar,
    build_ohlcv_bar,
    require_closed_series,
)
from app.market_contracts.order_flow import require_order_flow_request
from app.market_contracts.provider_contracts import contract_from_binance_exchange_info
from app.market_contracts.trade_reduction import build_released_trade_snapshot
from app.market_contracts.trades import (
    OrderedTradeBatch,
    TradeEvent,
    build_trade_event,
    order_trades,
)
from app.providers.base import ProviderHealth, ProviderKind, ProviderStatus
from app.schemas.common import Timeframe
from app.schemas.nested_continuation import EvidenceAvailability

# Native intervals explicitly contracted by this adapter. A future enum addition
# must be verified before it can become provider evidence.
_BINANCE_INTERVAL = {
    Timeframe.M1: "1m",
    Timeframe.M3: "3m",
    Timeframe.M5: "5m",
    Timeframe.M15: "15m",
    Timeframe.M30: "30m",
    Timeframe.H1: "1h",
    Timeframe.H2: "2h",
    Timeframe.H4: "4h",
    Timeframe.H6: "6h",
    Timeframe.H12: "12h",
    Timeframe.D1: "1d",
    Timeframe.D3: "3d",
    Timeframe.W1: "1w",
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
        catalog: PerpetualInstrumentCatalog | None = None,
        max_retries: int = 3,
        weight_per_minute: int = 1800,
        max_backoff_seconds: float = 30.0,
        trade_cache_entries: int = 8,
        cache_ttl_seconds: float = 120.0,
        max_cached_rows: int = 4096,
        trade_cache: ClosedAggTradeCache | None = None,
        reduced_cache: TtlValueCache | None = None,
        budget: SlidingWeightBudget | None = None,
        progress_interval_seconds: float = 5.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._http = client or ReadOnlyHttpGetClient(
            base_url=self._base_url,
            timeout_seconds=timeout_seconds,
            transport=transport,
            max_retries=max_retries,
            weight_per_minute=weight_per_minute,
            max_backoff_seconds=max_backoff_seconds,
            budget=budget,
            progress_interval_seconds=progress_interval_seconds,
        )
        self._catalog = catalog if catalog is not None else default_perpetual_catalog()
        # An empty cache is still a cache. ``or`` would replace it because len is 0.
        if trade_cache is None:
            self._trade_cache = ClosedAggTradeCache(
                max_entries=max(trade_cache_entries, 1),
                ttl_seconds=cache_ttl_seconds,
                max_rows=max_cached_rows,
            )
        else:
            self._trade_cache = trade_cache
        if reduced_cache is None:
            self._reduced_cache = TtlValueCache(
                max_entries=max(trade_cache_entries, 1),
                ttl_seconds=cache_ttl_seconds,
            )
        else:
            self._reduced_cache = reduced_cache
        self._last_success_at: datetime | None = None
        self._last_error: str | None = None
        self._regional_failure = False

    def fetch_derivative_observation(
        self,
        *,
        identity: EvidenceMarketIdentity,
        instrument: InstrumentIdentity,
        metric: DerivativeMetric,
        observed_at: datetime,
    ) -> DerivativeObservation:
        self._assert_request(identity, instrument, None)
        try:
            self.verify_exchange_info(instrument)
        except (WrongInstrumentError, WrongMarketError):
            return derivative_observation(
                identity=identity,
                metric=metric,
                observed_at=observed_at,
                availability=EvidenceAvailability.UNSUPPORTED,
                reason="provider_contract_not_verified",
            )
        params: dict[str, str | int] = {"symbol": instrument.provider_symbol}
        if metric is DerivativeMetric.OPEN_INTEREST:
            payload = self._get("/fapi/v1/openInterest", params)
            row = payload if isinstance(payload, dict) else None
            value_key, time_key = "openInterest", "time"
            malformed = row is None or row.get("symbol") != instrument.provider_symbol
        else:
            params.update({"limit": 1, "endTime": int(observed_at.timestamp() * 1000)})
            payload = self._get("/fapi/v1/fundingRate", params)
            row = payload[0] if isinstance(payload, list) and len(payload) == 1 else None
            malformed = (
                not isinstance(payload, list)
                or len(payload) > 1
                or (bool(payload) and not isinstance(row, dict))
            )
            if isinstance(row, dict) and row.get("symbol") != instrument.provider_symbol:
                malformed = True
            value_key, time_key = "fundingRate", "fundingTime"
        return derivative_observation(
            identity=identity,
            metric=metric,
            observed_at=observed_at,
            row=row if isinstance(row, dict) else None,
            value_key=value_key,
            time_key=time_key,
            availability=EvidenceAvailability.INCOMPLETE if malformed else None,
            reason="malformed_provider_payload" if malformed else None,
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

    def fetch_closed_ohlcv_history(
        self,
        *,
        identity: EvidenceMarketIdentity,
        instrument: InstrumentIdentity,
        timeframe: Timeframe,
        evaluated_at: datetime,
        limit: int = 1000,
    ) -> ClosedOhlcvSeries:
        """Bounded historical tail, allowing shorter actual listing history.

        This read does not change the live evidence minimum or freshness policy.
        The caller verifies exchangeInfo. A fixed UTC cutoff makes the requested
        window repeatable; no forming bar, gap, duplicate or substituted interval
        can enter the returned series.
        """
        self._assert_request(identity, instrument, timeframe)
        interval = _BINANCE_INTERVAL.get(timeframe)
        if interval is None:
            raise WrongMarketError(f"Timeframe {timeframe.value} is not contracted for USD-M.")
        if evaluated_at.tzinfo is None or not 1 <= limit <= 1498:
            raise ValueError("History requires an aware cutoff and limit between 1 and 1498.")
        grace = timedelta(seconds=first_slice_freshness_policy().ohlcv_post_close_grace_seconds)
        payload = self._get(
            "/fapi/v1/klines",
            {
                "symbol": instrument.provider_symbol,
                "interval": interval,
                "limit": limit + 2,
                "endTime": int((evaluated_at - grace).timestamp() * 1000) - 1,
            },
        )
        if not isinstance(payload, list):
            raise WrongMarketError("USD-M kline payload is not a list.")
        bars: list[OhlcvBar] = []
        for row in payload:
            bar = self._parse_kline(
                row,
                instrument=instrument,
                timeframe=timeframe,
                evaluated_at=evaluated_at,
                grace=grace,
            )
            if int(row[6]) + 1 != int(bar.interval_end.timestamp() * 1000):
                raise WrongMarketError("USD-M provider close time differs from requested interval.")
            if bar.finality.value == "final":
                bars.append(bar)
        if not bars:
            raise FormingCandleError("No final candles in the requested historical window.")
        # Validate the entire response before selecting the bounded tail.
        complete = require_closed_series(
            bars,
            identity=identity,
            timeframe=timeframe,
            evaluated_at=evaluated_at,
            min_bars=len(bars),
        )
        selected = complete.bars[-limit:]
        return require_closed_series(
            selected,
            identity=identity,
            timeframe=timeframe,
            evaluated_at=evaluated_at,
            min_bars=len(selected),
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
        rows = self._cached_agg_trades(
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

    def reduce_ordered_trades(
        self,
        *,
        identity: EvidenceMarketIdentity,
        instrument: InstrumentIdentity,
        start: datetime,
        end: datetime,
        source_connection_id: UUID,
        receive_at: datetime,
    ) -> TradeStreamSnapshot:
        """Stream aggTrades into a coverage-bound snapshot and drop the tape."""

        self._assert_request(identity, instrument, identity.timeframe)
        if end <= start:
            raise WrongMarketError("Trade window end must be after start.")
        key = closed_agg_trade_window_key(instrument.provider_symbol, start, end)
        key_lock = self._trade_cache.lock_for(key)
        try:
            with key_lock:
                reduced_key = (key[0] + ":" + str(identity.timeframe), *key[1:])
                cached = self._reduced_cache.get(reduced_key)
                if isinstance(cached, TradeStreamSnapshot):
                    record_cache_hit()
                    return cached.model_copy(update={"trades": []})
                snapshot = build_released_trade_snapshot(
                    self._iter_reduced_trades(
                        instrument=instrument,
                        start=start,
                        end=end,
                        source_connection_id=source_connection_id,
                        receive_at=receive_at,
                    ),
                    identity=identity,
                    lineage_id=source_connection_id,
                    window_start=start,
                    window_end=end,
                    observed_at=receive_at,
                )
                self._reduced_cache.put(reduced_key, snapshot)
                return snapshot
        finally:
            self._trade_cache.release_idle(key)

    def fetch_order_flow_snapshot(
        self,
        *,
        identity: EvidenceMarketIdentity,
        instrument: InstrumentIdentity,
        start: datetime,
        end: datetime,
        source_connection_id: UUID,
        receive_at: datetime,
    ) -> TradeStreamSnapshot:
        require_order_flow_request(
            identity=identity,
            start=start,
            end=end,
            observed_at=receive_at,
        )
        self._assert_request(identity, instrument, identity.timeframe)
        try:
            self.verify_exchange_info(instrument)
        except (WrongMarketError, WrongInstrumentError) as exc:
            raise UnsupportedTradeContractError("Trade contract not verified.") from exc
        return self.reduce_ordered_trades(
            identity=identity,
            instrument=instrument,
            start=start,
            end=end,
            source_connection_id=source_connection_id,
            receive_at=receive_at,
        )

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
        except UpstreamBanError as exc:
            self._last_error = str(exc)[:200]
            return ProviderStatus(
                name=self.name,
                kind=self.kind,
                health=ProviderHealth.DEGRADED,
                using_fallback=False,
                is_mock=False,
                detail="Binance USD-M temporarily banned this client; no spot fallback.",
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

    def release_symbol_history(self, symbol: str) -> None:
        """Release cached trade windows for one symbol after its evaluation."""

        self._trade_cache.drop_symbol(symbol)
        self._reduced_cache.drop_symbol(symbol)

    def allow_verified_contract(self, symbol: str) -> None:
        """Add one catalog identity after that exact USD-M contract is verified."""

        instrument = binance_usdm_perpetual(symbol)
        self._catalog = self._catalog.extend(instrument)

    def verify_exchange_info(self, instrument: InstrumentIdentity) -> None:
        payload = self._get("/fapi/v1/exchangeInfo", {"symbol": instrument.provider_symbol})
        if not isinstance(payload, dict):
            raise WrongSourceError("exchangeInfo payload is not an object.")
        rows = payload.get("symbols")
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise WrongSourceError("exchangeInfo symbols are malformed.")
        required_fields = {"symbol", "contractType", "quoteAsset", "baseAsset", "status"}
        for row in rows:
            if (
                row.get("symbol") == instrument.provider_symbol
                and not required_fields <= row.keys()
            ):
                raise WrongSourceError("exchangeInfo contract fields are incomplete.")
        contract = contract_from_binance_exchange_info(
            payload,
            requested_symbol=instrument.provider_symbol,
        )
        if contract.quote_asset != instrument.quote_asset:
            raise WrongMarketError("USD-M quote asset does not match the contracted instrument.")
        if contract.base_asset != instrument.base_asset:
            raise WrongInstrumentError("USD-M base asset does not match the contracted instrument.")

    def _assert_request(
        self,
        identity: EvidenceMarketIdentity,
        instrument: InstrumentIdentity,
        timeframe: Timeframe | None,
    ) -> None:
        require_perpetual(identity)
        require_instrument(identity, instrument)
        enabled = self._catalog.require(instrument.provider_symbol)
        if instrument.instrument_id != enabled.instrument_id:
            raise WrongInstrumentError(
                "Requested instrument does not match the enabled USD-M catalog identity."
            )
        if identity.venue is not VenueId.BINANCE:
            raise WrongMarketError("Binance USD-M adapter cannot serve a non-Binance venue.")
        if identity.instrument.product_family is not ProductFamily.USDM_FUTURES:
            raise WrongMarketError("Binance USD-M adapter cannot serve a non-USD-M product.")
        if identity.instrument.market_type is not MarketType.PERPETUAL:
            raise WrongMarketError("Binance USD-M adapter cannot serve non-perpetual markets.")
        source = identity.source
        provenance = identity.provenance
        if (
            source.family is not SourceFamily.BINANCE_USDM_FUTURES_PUBLIC
            or source.provider_name != self.name
            or provenance.source_family is not SourceFamily.BINANCE_USDM_FUTURES_PUBLIC
            or provenance.provider_name != self.name
            or not provenance.is_live
            or provenance.is_mock
        ):
            raise WrongSourceError(
                "Live USD-M evidence identity must exactly identify the live Binance provider."
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
        if not isinstance(row.get("m"), bool):
            raise WrongMarketError("USD-M aggTrade is missing buyer-is-maker flag.")
        venue_trade_id = str(row["a"])
        event_ms = int(row["T"])
        return build_trade_event(
            instrument=instrument,
            venue_trade_id=venue_trade_id,
            sequence=int(row["a"]),
            price=Decimal(str(row["p"])),
            quantity=Decimal(str(row["q"])),
            buyer_is_maker=row["m"],
            event_timestamp=datetime.fromtimestamp(event_ms / 1000, tz=UTC),
            receive_timestamp=receive_at.astimezone(UTC),
            source_connection_id=source_connection_id,
            adapter_version=ADAPTER_VERSION,
        )

    @property
    def evidence_cache(self) -> ClosedAggTradeCache:
        return self._trade_cache

    @property
    def request_budget(self) -> SlidingWeightBudget:
        return self._http.budget

    def close(self) -> None:
        self._http.close()

    def _iter_reduced_trades(
        self,
        *,
        instrument: InstrumentIdentity,
        start: datetime,
        end: datetime,
        source_connection_id: UUID,
        receive_at: datetime,
    ) -> Iterator[TradeEvent]:
        rows = iter_contiguous_agg_trade_rows(
            get_json=self._get,
            symbol=instrument.provider_symbol,
            start=start,
            end=end,
        )
        for row in rows:
            yield self._parse_agg_trade(
                row,
                instrument=instrument,
                source_connection_id=source_connection_id,
                receive_at=receive_at,
            )

    def _cached_agg_trades(
        self,
        *,
        symbol: str,
        start: datetime,
        end: datetime,
    ) -> tuple[Any, ...]:
        """Reuse one closed aggTrade window. The key is the window, not the tenant."""

        key = closed_agg_trade_window_key(symbol, start, end)
        key_lock = self._trade_cache.lock_for(key)
        try:
            with key_lock:
                cached = self._trade_cache.get(key)
                if cached is not None:
                    record_cache_hit()
                    return cached
                rows = tuple(
                    fetch_complete_agg_trade_rows(
                        get_json=self._get,
                        symbol=symbol,
                        start=start,
                        end=end,
                    )
                )
                self._trade_cache.put(key, rows)
                return rows
        finally:
            self._trade_cache.release_idle(key)

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

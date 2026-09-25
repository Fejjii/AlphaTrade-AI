"""OKX public USDT linear swap adapter (read-only, no spot, no fabricated fills)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

import httpx

from app.market_contracts.adapters.http import ReadOnlyHttpGetClient
from app.market_contracts.coverage import build_complete_trade_window_coverage
from app.market_contracts.enums import MarketType, ProductFamily, SourceFamily, VenueId
from app.market_contracts.errors import (
    FormingCandleError,
    GapDetectedError,
    IncompleteTradeWindowError,
    RateLimitedError,
    RegionalProviderFailureError,
    SpotFallbackRejectedError,
    WrongInstrumentError,
    WrongMarketError,
    WrongSourceError,
)
from app.market_contracts.freshness import first_slice_freshness_policy
from app.market_contracts.hashing import with_content_hash
from app.market_contracts.identity import (
    OKX_ADAPTER_VERSION,
    OKX_AGGRESSOR_CONVENTION,
    EvidenceMarketIdentity,
    InstrumentIdentity,
    okx_usdt_swap_btcusdt,
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

OKX_INST_ID = "BTC-USDT-SWAP"
OKX_ALLOWED_PATHS = frozenset(
    {
        "/api/v5/public/time",
        "/api/v5/public/instruments",
        "/api/v5/market/candles",
        "/api/v5/market/history-trades",
    }
)
OKX_ALLOWED_HOSTS = frozenset({"www.okx.com"})
_OKX_BAR = {Timeframe.M15: "15m", Timeframe.H4: "4H"}
_HISTORY_PAGE_LIMIT = 100


class OkxUsdtSwapPerpetualSource:
    """Public OKX BTC-USDT-SWAP evidence. Spot BTC-USDT is rejected."""

    name = "okx-usdt-swap-perpetual"
    kind = ProviderKind.MARKET_DATA

    def __init__(
        self,
        *,
        base_url: str = "https://www.okx.com",
        timeout_seconds: float = 10.0,
        transport: httpx.BaseTransport | None = None,
        client: ReadOnlyHttpGetClient | None = None,
        max_retries: int = 3,
        max_backoff_seconds: float = 30.0,
        max_trade_pages: int = 8,
    ) -> None:
        self._instrument = okx_usdt_swap_btcusdt()
        self._max_trade_pages = max_trade_pages
        self._http = client or ReadOnlyHttpGetClient(
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            transport=transport,
            allowed_hosts=OKX_ALLOWED_HOSTS,
            allowed_paths=OKX_ALLOWED_PATHS,
            failure_label="OKX USDT swap",
            max_retries=max_retries,
            max_backoff_seconds=max_backoff_seconds,
            weight_per_minute=240,
        )
        self._last_success_at: datetime | None = None
        self._last_error: str | None = None

    def active_instrument(self) -> InstrumentIdentity:
        return self._instrument

    def fetch_closed_ohlcv(
        self,
        *,
        identity: EvidenceMarketIdentity,
        instrument: InstrumentIdentity,
        timeframe: Timeframe,
        min_final_bars: int,
        evaluated_at: datetime,
    ) -> ClosedOhlcvSeries:
        self._assert_request(identity, instrument)
        bar = _OKX_BAR.get(timeframe)
        if bar is None:
            raise WrongMarketError(
                f"Timeframe {timeframe.value} is not contracted for OKX swap evidence."
            )
        limit = min(max(min_final_bars + 2, min_final_bars), 300)
        payload = self._public_data(
            "/api/v5/market/candles",
            {"instId": OKX_INST_ID, "bar": bar, "limit": limit},
        )
        if not isinstance(payload, list):
            raise WrongMarketError("OKX candle payload is not a list.")
        grace = timedelta(seconds=first_slice_freshness_policy().ohlcv_post_close_grace_seconds)
        bars: list[OhlcvBar] = []
        for row in payload:
            bars.append(
                self._parse_candle(
                    row,
                    instrument=instrument,
                    timeframe=timeframe,
                    evaluated_at=evaluated_at,
                    grace=grace,
                )
            )
        bars.sort(key=lambda item: item.interval_start)
        final_bars = [item for item in bars if item.finality.value == "final"]
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
        self._assert_request(identity, instrument)
        if end <= start:
            raise WrongMarketError("Trade window end must be after start.")
        rows = self._history_covering(start, end)
        raw_trades = [
            self._parse_trade(
                row,
                instrument=instrument,
                source_connection_id=source_connection_id,
                receive_at=receive_at,
            )
            for row in rows
        ]
        ordered = order_trades(raw_trades)
        _require_contiguous_ids(ordered)
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
            self._public_data("/api/v5/public/time", None)
            self._last_error = None
            self._last_success_at = datetime.now(UTC)
            return ProviderStatus(
                name=self.name,
                kind=self.kind,
                health=ProviderHealth.HEALTHY,
                using_fallback=False,
                is_mock=False,
                detail="OKX USDT linear swap public REST (read-only, no spot fallback).",
                last_success_at=self._last_success_at,
                error_message=None,
            )
        except (RegionalProviderFailureError, RateLimitedError) as exc:
            self._last_error = str(exc)[:200]
            return ProviderStatus(
                name=self.name,
                kind=self.kind,
                health=ProviderHealth.UNAVAILABLE,
                using_fallback=False,
                is_mock=False,
                detail="OKX USDT swap source unreachable; no spot or fabricated fallback.",
                last_success_at=self._last_success_at,
                error_message=self._last_error,
            )

    def _history_covering(self, start: datetime, end: datetime) -> list[Mapping[str, Any]]:
        """Page public history until the window start is proven, or fail closed."""

        start_ms = int(start.astimezone(UTC).timestamp() * 1000)
        end_ms = int(end.astimezone(UTC).timestamp() * 1000)
        collected: list[Mapping[str, Any]] = []
        after: str | None = None
        reached_start = False
        for _page in range(self._max_trade_pages):
            params: dict[str, str | int] = {"instId": OKX_INST_ID, "limit": _HISTORY_PAGE_LIMIT}
            if after is not None:
                params["after"] = after
            payload = self._public_data("/api/v5/market/history-trades", params)
            if not isinstance(payload, list) or not payload:
                break
            page_rows = [row for row in payload if isinstance(row, dict)]
            if len(page_rows) != len(payload):
                raise WrongMarketError("OKX trade history row is malformed.")
            oldest_id: int | None = None
            oldest_ts: int | None = None
            for row in page_rows:
                trade_id = int(str(row["tradeId"]))
                trade_ms = int(str(row["ts"]))
                if oldest_id is None or trade_id < oldest_id:
                    oldest_id = trade_id
                    oldest_ts = trade_ms
                if start_ms <= trade_ms < end_ms:
                    collected.append(row)
            if oldest_ts is not None and oldest_ts <= start_ms:
                reached_start = True
                break
            if oldest_id is None or len(page_rows) < _HISTORY_PAGE_LIMIT:
                break
            after = str(oldest_id)
        if not reached_start:
            raise IncompleteTradeWindowError(
                "OKX trade history does not prove the requested window. "
                "Refusing to fabricate the missing prefix."
            )
        if not collected:
            raise IncompleteTradeWindowError(
                "OKX trade history has no prints inside the requested window."
            )
        return collected

    def _assert_request(
        self,
        identity: EvidenceMarketIdentity,
        instrument: InstrumentIdentity,
    ) -> None:
        require_perpetual(identity)
        require_instrument(identity, instrument)
        if instrument.instrument_id != self._instrument.instrument_id:
            raise WrongInstrumentError("OKX adapter only serves BTC-USDT-SWAP.")
        if identity.venue is not VenueId.OKX:
            raise WrongMarketError("OKX adapter cannot serve a non-OKX venue.")
        if identity.instrument.product_family is not ProductFamily.USDM_FUTURES:
            raise SpotFallbackRejectedError(
                "OKX spot or coin-margined books are not swap evidence."
            )
        if identity.instrument.market_type is not MarketType.PERPETUAL:
            raise WrongMarketError("OKX adapter cannot serve non-perpetual markets.")
        source = identity.source
        provenance = identity.provenance
        if (
            source.family is not SourceFamily.OKX_USDT_SWAP_PUBLIC
            or source.provider_name != self.name
            or provenance.source_family is not SourceFamily.OKX_USDT_SWAP_PUBLIC
            or provenance.provider_name != self.name
            or provenance.fallback_used
            or not provenance.is_live
            or provenance.is_mock
        ):
            raise WrongSourceError(
                "Live OKX evidence identity must exactly identify the OKX swap provider."
            )
        if source.aggressor_convention != OKX_AGGRESSOR_CONVENTION:
            raise WrongSourceError("OKX aggressor convention does not match the adapter.")

    def _parse_candle(
        self,
        row: Any,
        *,
        instrument: InstrumentIdentity,
        timeframe: Timeframe,
        evaluated_at: datetime,
        grace: timedelta,
    ) -> OhlcvBar:
        if not isinstance(row, list) or len(row) < 9:
            raise WrongMarketError("OKX candle row is malformed.")
        confirm = str(row[8])
        if confirm not in {"0", "1"}:
            raise WrongMarketError("OKX candle confirm flag is missing.")
        interval_start = datetime.fromtimestamp(int(row[0]) / 1000, tz=UTC)
        return build_ohlcv_bar(
            instrument=instrument,
            timeframe=timeframe,
            interval_start=interval_start,
            open_=Decimal(str(row[1])),
            high=Decimal(str(row[2])),
            low=Decimal(str(row[3])),
            close=Decimal(str(row[4])),
            base_volume=Decimal(str(row[6])),
            quote_volume=Decimal(str(row[7])),
            evaluated_at=evaluated_at,
            grace=grace,
            provider_complete=confirm == "1",
            adapter_version=OKX_ADAPTER_VERSION,
        )

    def _parse_trade(
        self,
        row: Mapping[str, Any],
        *,
        instrument: InstrumentIdentity,
        source_connection_id: UUID,
        receive_at: datetime,
    ) -> TradeEvent:
        inst = str(row.get("instId", ""))
        if inst != OKX_INST_ID:
            if inst.endswith("-USDT") and "SWAP" not in inst:
                raise SpotFallbackRejectedError(
                    "OKX spot trades cannot satisfy perpetual swap evidence."
                )
            raise WrongInstrumentError(f"OKX trade instId {inst} is not BTC-USDT-SWAP.")
        side = str(row.get("side", "")).lower()
        if side == "buy":
            buyer_is_maker = False
        elif side == "sell":
            buyer_is_maker = True
        else:
            raise WrongMarketError("OKX trade is missing taker side.")
        return build_trade_event(
            instrument=instrument,
            venue_trade_id=str(row["tradeId"]),
            sequence=int(str(row["tradeId"])),
            price=Decimal(str(row["px"])),
            quantity=Decimal(str(row["sz"])),
            buyer_is_maker=buyer_is_maker,
            event_timestamp=datetime.fromtimestamp(int(str(row["ts"])) / 1000, tz=UTC),
            receive_timestamp=receive_at.astimezone(UTC),
            source_connection_id=source_connection_id,
            adapter_version=OKX_ADAPTER_VERSION,
            aggressor_convention=OKX_AGGRESSOR_CONVENTION,
        )

    def _public_data(self, path: str, params: Mapping[str, str | int] | None) -> Any:
        payload = self._http.get_json(path, params)
        if not isinstance(payload, dict):
            raise WrongMarketError("OKX payload is not an object.")
        code = str(payload.get("code", ""))
        if code == "50011":
            raise RateLimitedError("OKX public swap source rate-limited the read-only client.")
        if code != "0":
            raise RegionalProviderFailureError(f"OKX public swap source returned code {code}.")
        self._last_success_at = datetime.now(UTC)
        self._last_error = None
        return payload.get("data")

    def close(self) -> None:
        self._http.close()


def _require_contiguous_ids(trades: list[TradeEvent]) -> None:
    if len(trades) < 2:
        return
    previous = trades[0].sequence
    for trade in trades[1:]:
        if trade.sequence != previous + 1:
            raise GapDetectedError(
                f"OKX trade id gap {previous + 1}-{trade.sequence - 1}; refusing a partial CVD."
            )
        previous = trade.sequence

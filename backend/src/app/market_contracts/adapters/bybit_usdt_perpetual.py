"""Bybit public USDT linear perpetual adapter (read-only, no spot, no fabricated fills)."""

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
    DuplicateDataError,
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
    BYBIT_ADAPTER_VERSION,
    BYBIT_AGGRESSOR_CONVENTION,
    EvidenceMarketIdentity,
    InstrumentIdentity,
    bybit_usdt_perpetual_btcusdt,
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

BYBIT_SYMBOL = "BTCUSDT"
BYBIT_CATEGORY = "linear"
BYBIT_ALLOWED_PATHS = frozenset(
    {
        "/v5/market/time",
        "/v5/market/kline",
        "/v5/market/recent-trade",
    }
)
BYBIT_ALLOWED_HOSTS = frozenset({"api.bybit.com"})
_BYBIT_INTERVAL = {Timeframe.M15: "15", Timeframe.H4: "240"}
_RECENT_TRADE_LIMIT = 1000


class BybitUsdtPerpetualSource:
    """Public Bybit linear BTCUSDT perpetual. Spot and inverse books are rejected."""

    name = "bybit-usdt-perpetual"
    kind = ProviderKind.MARKET_DATA

    def __init__(
        self,
        *,
        base_url: str = "https://api.bybit.com",
        timeout_seconds: float = 10.0,
        transport: httpx.BaseTransport | None = None,
        client: ReadOnlyHttpGetClient | None = None,
        max_retries: int = 3,
        max_backoff_seconds: float = 30.0,
    ) -> None:
        self._instrument = bybit_usdt_perpetual_btcusdt()
        self._http = client or ReadOnlyHttpGetClient(
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            transport=transport,
            allowed_hosts=BYBIT_ALLOWED_HOSTS,
            allowed_paths=BYBIT_ALLOWED_PATHS,
            failure_label="Bybit USDT perpetual",
            max_retries=max_retries,
            max_backoff_seconds=max_backoff_seconds,
            weight_per_minute=240,
        )
        self._last_success_at: datetime | None = None
        self._last_error: str | None = None
        # Cross sequence is not a per-trade id. Ranks are stable per connection.
        self._rank_connection: UUID | None = None
        self._rank_by_exec: dict[str, int] = {}
        self._next_rank = 1
        self._anchor_exec_id: str | None = None

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
        interval = _BYBIT_INTERVAL.get(timeframe)
        if interval is None:
            raise WrongMarketError(
                f"Timeframe {timeframe.value} is not contracted for Bybit USDT perpetual evidence."
            )
        limit = min(max(min_final_bars + 2, min_final_bars), 1000)
        result = self._public_result(
            "/v5/market/kline",
            {
                "category": BYBIT_CATEGORY,
                "symbol": BYBIT_SYMBOL,
                "interval": interval,
                "limit": limit,
            },
        )
        self._assert_linear_btc(result)
        rows = result.get("list")
        if not isinstance(rows, list):
            raise WrongMarketError("Bybit kline payload is not a list.")
        grace = timedelta(seconds=first_slice_freshness_policy().ohlcv_post_close_grace_seconds)
        bars = [
            self._parse_kline(
                row,
                instrument=instrument,
                timeframe=timeframe,
                evaluated_at=evaluated_at,
                grace=grace,
            )
            for row in rows
        ]
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
        rows = self._recent_trades_covering(start, end, source_connection_id)
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
        _require_contiguous_sequences(ordered)
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
            self._public_result("/v5/market/time", None)
            self._last_error = None
            self._last_success_at = datetime.now(UTC)
            return ProviderStatus(
                name=self.name,
                kind=self.kind,
                health=ProviderHealth.HEALTHY,
                using_fallback=False,
                is_mock=False,
                detail="Bybit USDT linear perpetual public REST (read-only, no spot fallback).",
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
                detail="Bybit USDT perpetual source unreachable; no spot or fabricated fallback.",
                last_success_at=self._last_success_at,
                error_message=self._last_error,
            )

    def _recent_trades_covering(
        self,
        start: datetime,
        end: datetime,
        source_connection_id: UUID,
    ) -> list[dict[str, Any]]:
        """Prove one recent-trade tail, then keep only the requested half-open window.

        Bybit ``seq`` is a cross sequence. It is not a per-symbol trade id and is
        not required to increase by one. Coverage is the public buffer reaching
        ``start``, plus a stable rank per execution id on this connection.
        """

        start_ms = int(start.astimezone(UTC).timestamp() * 1000)
        end_ms = int(end.astimezone(UTC).timestamp() * 1000)
        result = self._public_result(
            "/v5/market/recent-trade",
            {"category": BYBIT_CATEGORY, "symbol": BYBIT_SYMBOL, "limit": _RECENT_TRADE_LIMIT},
        )
        self._assert_linear_btc(result)
        payload = result.get("list")
        if not isinstance(payload, list) or not payload:
            raise IncompleteTradeWindowError(
                "Bybit recent trades do not prove the requested window. "
                "Refusing to fabricate the missing prefix."
            )
        prints = [_normalize_print(row) for row in payload]
        prints.sort(key=lambda item: (item["time_ms"], item["exec_id"]))
        _reject_conflicting_exec_ids(prints)
        prints = _unique_exec_ids(prints)
        if int(prints[0]["time_ms"]) > start_ms:
            raise IncompleteTradeWindowError(
                "Bybit recent trades do not prove the requested window. "
                "Refusing to fabricate the missing prefix."
            )
        self._prepare_connection(source_connection_id)
        if self._anchor_exec_id is not None and all(
            item["exec_id"] != self._anchor_exec_id for item in prints
        ):
            raise GapDetectedError(
                "Bybit recent-trade buffer dropped the last proven print. "
                "Refusing to fabricate the missing interval."
            )
        for item in prints:
            exec_id = str(item["exec_id"])
            if exec_id in self._rank_by_exec:
                continue
            self._rank_by_exec[exec_id] = self._next_rank
            self._next_rank += 1
        ranks = [self._rank_by_exec[str(item["exec_id"])] for item in prints]
        if ranks != list(range(ranks[0], ranks[0] + len(ranks))):
            raise GapDetectedError(
                "Bybit recent-trade order is not a contiguous proven tail. Refusing a partial CVD."
            )
        window = [item for item in prints if start_ms <= int(item["time_ms"]) < end_ms]
        if not window:
            raise IncompleteTradeWindowError(
                "Bybit recent trades have no prints inside the requested window."
            )
        window_ranks = [self._rank_by_exec[str(item["exec_id"])] for item in window]
        if window_ranks != list(range(window_ranks[0], window_ranks[0] + len(window_ranks))):
            raise GapDetectedError(
                "Bybit trade window is not a contiguous proven tail. Refusing a partial CVD."
            )
        self._anchor_exec_id = str(window[-1]["exec_id"])
        for item in window:
            item["sequence"] = self._rank_by_exec[str(item["exec_id"])]
        return window

    def _assert_linear_btc(self, result: Mapping[str, Any]) -> None:
        category = str(result.get("category", "")).lower()
        if category == "spot":
            raise SpotFallbackRejectedError(
                "Bybit spot trades cannot satisfy USDT perpetual evidence."
            )
        if category != BYBIT_CATEGORY:
            raise WrongMarketError(
                f"Bybit category {category or 'missing'} is not linear perpetual evidence."
            )
        symbol = str(result.get("symbol", "")).upper()
        if symbol and symbol != BYBIT_SYMBOL:
            raise WrongInstrumentError(f"Bybit symbol {symbol} is not BTCUSDT perpetual.")

    def _assert_request(
        self,
        identity: EvidenceMarketIdentity,
        instrument: InstrumentIdentity,
    ) -> None:
        require_perpetual(identity)
        require_instrument(identity, instrument)
        if instrument.instrument_id != self._instrument.instrument_id:
            raise WrongInstrumentError("Bybit adapter only serves linear BTCUSDT perpetual.")
        if identity.venue is not VenueId.BYBIT:
            raise WrongMarketError("Bybit adapter cannot serve a non-Bybit venue.")
        if identity.instrument.product_family is not ProductFamily.USDM_FUTURES:
            raise SpotFallbackRejectedError(
                "Bybit spot or inverse books are not USDT perpetual evidence."
            )
        if identity.instrument.market_type is not MarketType.PERPETUAL:
            raise WrongMarketError("Bybit adapter cannot serve non-perpetual markets.")
        source = identity.source
        provenance = identity.provenance
        if (
            source.family is not SourceFamily.BYBIT_USDT_PERPETUAL_PUBLIC
            or source.provider_name != self.name
            or provenance.source_family is not SourceFamily.BYBIT_USDT_PERPETUAL_PUBLIC
            or provenance.provider_name != self.name
            or provenance.fallback_used
            or not provenance.is_live
            or provenance.is_mock
        ):
            raise WrongSourceError(
                "Live Bybit evidence identity must exactly identify the Bybit USDT perpetual."
            )
        if source.aggressor_convention != BYBIT_AGGRESSOR_CONVENTION:
            raise WrongSourceError("Bybit aggressor convention does not match the adapter.")

    def _parse_kline(
        self,
        row: Any,
        *,
        instrument: InstrumentIdentity,
        timeframe: Timeframe,
        evaluated_at: datetime,
        grace: timedelta,
    ) -> OhlcvBar:
        if not isinstance(row, list) or len(row) < 7:
            raise WrongMarketError("Bybit kline row is malformed.")
        interval_start = datetime.fromtimestamp(int(row[0]) / 1000, tz=UTC)
        return build_ohlcv_bar(
            instrument=instrument,
            timeframe=timeframe,
            interval_start=interval_start,
            open_=Decimal(str(row[1])),
            high=Decimal(str(row[2])),
            low=Decimal(str(row[3])),
            close=Decimal(str(row[4])),
            base_volume=Decimal(str(row[5])),
            quote_volume=Decimal(str(row[6])),
            evaluated_at=evaluated_at,
            grace=grace,
            adapter_version=BYBIT_ADAPTER_VERSION,
        )

    def _parse_trade(
        self,
        row: Mapping[str, Any],
        *,
        instrument: InstrumentIdentity,
        source_connection_id: UUID,
        receive_at: datetime,
    ) -> TradeEvent:
        symbol = str(row.get("symbol", "")).upper()
        if symbol != BYBIT_SYMBOL:
            raise WrongInstrumentError(f"Bybit trade symbol {symbol} is not BTCUSDT.")
        side = str(row.get("side", "")).lower()
        if side == "buy":
            buyer_is_maker = False
        elif side == "sell":
            buyer_is_maker = True
        else:
            raise WrongMarketError("Bybit trade is missing taker side.")
        exec_id = str(row["exec_id"])
        if len(exec_id) > 40:
            raise WrongMarketError("Bybit execution id is longer than the trade identity.")
        return build_trade_event(
            instrument=instrument,
            venue_trade_id=exec_id,
            sequence=int(row["sequence"]),
            price=Decimal(str(row["price"])),
            quantity=Decimal(str(row["size"])),
            buyer_is_maker=buyer_is_maker,
            event_timestamp=datetime.fromtimestamp(int(str(row["time"])) / 1000, tz=UTC),
            receive_timestamp=receive_at.astimezone(UTC),
            source_connection_id=source_connection_id,
            adapter_version=BYBIT_ADAPTER_VERSION,
            aggressor_convention=BYBIT_AGGRESSOR_CONVENTION,
        )

    def _public_result(self, path: str, params: Mapping[str, str | int] | None) -> dict[str, Any]:
        payload = self._http.get_json(path, params)
        if not isinstance(payload, dict):
            raise WrongMarketError("Bybit payload is not an object.")
        code = str(payload.get("retCode", ""))
        if code == "10006":
            raise RateLimitedError(
                "Bybit public perpetual source rate-limited the read-only client."
            )
        if code != "0":
            raise RegionalProviderFailureError(
                f"Bybit public perpetual source returned retCode {code}."
            )
        self._last_success_at = datetime.now(UTC)
        self._last_error = None
        result = payload.get("result", {})
        if not isinstance(result, dict):
            raise WrongMarketError("Bybit result is not an object.")
        return result

    def _prepare_connection(self, source_connection_id: UUID) -> None:
        if self._rank_connection == source_connection_id:
            return
        self._rank_connection = source_connection_id
        self._rank_by_exec = {}
        self._next_rank = 1
        self._anchor_exec_id = None

    def close(self) -> None:
        self._http.close()


def _normalize_print(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise WrongMarketError("Bybit trade row is malformed.")
    exec_id = str(row.get("execId", "")).strip()
    if not exec_id:
        raise WrongMarketError("Bybit trade is missing execId.")
    try:
        time_ms = int(str(row["time"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise WrongMarketError("Bybit trade is missing a timestamp.") from exc
    return {
        "exec_id": exec_id,
        "time_ms": time_ms,
        "symbol": row.get("symbol", ""),
        "price": row.get("price"),
        "size": row.get("size"),
        "side": row.get("side"),
        "time": row.get("time"),
    }


def _unique_exec_ids(prints: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in prints:
        exec_id = str(item["exec_id"])
        if exec_id in seen:
            continue
        seen.add(exec_id)
        unique.append(item)
    return unique


def _reject_conflicting_exec_ids(prints: list[dict[str, Any]]) -> None:
    seen: dict[str, tuple[object, object, object, object]] = {}
    for item in prints:
        signature = (item["time_ms"], item["price"], item["size"], item["side"])
        previous = seen.get(str(item["exec_id"]))
        if previous is None:
            seen[str(item["exec_id"])] = signature
            continue
        if previous != signature:
            raise DuplicateDataError(f"Conflicting content for Bybit execution {item['exec_id']}.")


def _require_contiguous_sequences(trades: list[TradeEvent]) -> None:
    if len(trades) < 2:
        return
    previous = trades[0].sequence
    for trade in trades[1:]:
        if trade.sequence != previous + 1:
            raise GapDetectedError(
                f"Bybit trade sequence gap {previous + 1}-{trade.sequence - 1}; "
                "refusing a partial CVD."
            )
        previous = trade.sequence

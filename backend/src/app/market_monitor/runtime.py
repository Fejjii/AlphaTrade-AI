"""Per-symbol trade-stream runtime with reconnect, backoff, and fail-closed gaps."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.evidence_pipeline.types import CurrentPriceQuote
from app.market_contracts.adapters.protocol import PerpetualMarketSource
from app.market_contracts.coverage import TradeWindowCoverageProof
from app.market_contracts.cursor import TradeStreamAssembler, TradeStreamSnapshot
from app.market_contracts.cvd import accumulate_signed_quote, event_set_hash
from app.market_contracts.enums import (
    DataCompleteness,
    Finality,
    GapState,
    ReconnectState,
    WarmUpStatus,
)
from app.market_contracts.errors import (
    CursorRecoveryError,
    DuplicateDataError,
    FormingCandleError,
    GapDetectedError,
    IncompleteWarmUpError,
    MarketContractError,
    OutOfOrderTradesError,
    RateLimitedError,
    RegionalProviderFailureError,
    SpotFallbackRejectedError,
    UnrecoverableGapError,
    WrongInstrumentError,
    WrongMarketError,
    WrongSourceError,
)
from app.market_contracts.first_slice import (
    FIRST_SLICE_MIN_FINAL_4H,
    FIRST_SLICE_MIN_FINAL_15M,
    first_slice_identity,
)
from app.market_contracts.freshness import first_slice_freshness_policy
from app.market_contracts.identity import EvidenceMarketIdentity, InstrumentIdentity
from app.market_contracts.ohlcv import ClosedOhlcvSeries
from app.market_contracts.trades import OrderedTradeBatch
from app.market_monitor.backoff import BackoffPolicy, delay_seconds
from app.market_monitor.identity import monitor_semantic_hash
from app.market_monitor.price import quote_from_terminal_trade
from app.market_monitor.types import (
    BackoffReport,
    CoverageReport,
    MarketAvailability,
    MarketMode,
    MonitorReason,
    OhlcvHealth,
    ProviderHealthReport,
    StreamCvdReport,
    StreamHealth,
    SymbolMonitorSnapshot,
)
from app.providers.base import ProviderHealth
from app.schemas.common import Timeframe

_MAX_LOOKBACK = timedelta(minutes=10)


class SymbolMonitorRuntime:
    """One catalog symbol. New process = new connection epoch."""

    def __init__(
        self,
        *,
        instrument: InstrumentIdentity,
        source: PerpetualMarketSource,
        replay: bool,
        backoff: BackoffPolicy,
        connected_at: datetime,
    ) -> None:
        self.instrument = instrument
        self._source = source
        self._replay = replay
        self._backoff_policy = backoff
        self.identity = first_slice_identity(
            timeframe=Timeframe.M15,
            replay=replay,
            is_live=not replay,
            instrument=instrument,
        )
        self._identity_4h = first_slice_identity(
            timeframe=Timeframe.H4,
            replay=replay,
            is_live=not replay,
            instrument=instrument,
        )
        self._assembler = TradeStreamAssembler(
            self.identity,
            connected_at=connected_at,
            connection_identity=uuid4(),
        )
        self._watermark_time: datetime | None = None
        self._last_batch: OrderedTradeBatch | None = None
        self._last_stream: TradeStreamSnapshot | None = None
        self._series_15m: ClosedOhlcvSeries | None = None
        self._series_4h: ClosedOhlcvSeries | None = None
        self._reason = MonitorReason.WARM_UP
        self._backoff_until: datetime | None = None
        self._backoff_attempt = 0
        self._last_error_class: str | None = None
        self._ohlcv_reason: str | None = None

    @property
    def replay(self) -> bool:
        return self._replay

    def tick(self, now: datetime) -> SymbolMonitorSnapshot:
        evaluated = now.astimezone(UTC)
        if self._in_backoff(evaluated):
            self._reason = MonitorReason.BACKOFF
            return self._project(evaluated)
        try:
            self._fetch_and_ingest(evaluated)
            self._refresh_ohlcv(evaluated)
            self._clear_backoff()
        except RateLimitedError as exc:
            self._last_error_class = type(exc).__name__
            self._apply_backoff(evaluated, retry_after_seconds=exc.retry_after_seconds)
            self._reason = MonitorReason.RATE_LIMITED
        except RegionalProviderFailureError as exc:
            self._last_error_class = type(exc).__name__
            self._begin_reconnect(evaluated)
            self._apply_backoff(evaluated)
            self._reason = MonitorReason.PROVIDER_UNAVAILABLE
        except SpotFallbackRejectedError as exc:
            self._last_error_class = type(exc).__name__
            self._reason = MonitorReason.SPOT_REJECTED
        except WrongInstrumentError as exc:
            self._last_error_class = type(exc).__name__
            self._reason = MonitorReason.SYMBOL_MISMATCH
        except WrongSourceError as exc:
            self._last_error_class = type(exc).__name__
            self._reason = MonitorReason.WRONG_SOURCE
        except OutOfOrderTradesError as exc:
            self._last_error_class = type(exc).__name__
            self._reason = MonitorReason.OUT_OF_ORDER
        except DuplicateDataError as exc:
            self._last_error_class = type(exc).__name__
            self._reason = MonitorReason.DUPLICATE_CONFLICT
        except UnrecoverableGapError as exc:
            self._last_error_class = type(exc).__name__
            self._reason = MonitorReason.UNRECOVERABLE_GAP
        except (GapDetectedError, CursorRecoveryError, IncompleteWarmUpError) as exc:
            self._last_error_class = type(exc).__name__
            if self._assembler.cursor.reconnect_state is not ReconnectState.RECONNECTING:
                self._begin_reconnect(evaluated)
            self._apply_backoff(evaluated)
            self._reason = (
                MonitorReason.UNRECOVERABLE_GAP
                if self._assembler.cursor.gap_state is GapState.UNRECOVERABLE
                else MonitorReason.GAP
            )
        except MarketContractError as exc:
            self._last_error_class = type(exc).__name__
            self._reason = MonitorReason.PROVIDER_ERROR
        return self._project(evaluated)

    def project(self, now: datetime) -> SymbolMonitorSnapshot:
        """Re-evaluate freshness without a provider fetch."""
        return self._project(now.astimezone(UTC))

    def _fetch_and_ingest(self, now: datetime) -> None:
        if self._assembler.cursor.gap_state is GapState.UNRECOVERABLE:
            raise UnrecoverableGapError("Stream is closed after an unrecoverable gap.")
        start, end = self._window(now)
        batch = self._source.fetch_ordered_trades(
            identity=self.identity,
            instrument=self.instrument,
            start=start,
            end=end,
            source_connection_id=self._assembler.connection_identity,
            receive_at=now,
        )
        self._assert_batch_identity(batch)
        self._last_batch = batch
        if self._assembler.cursor.reconnect_state is ReconnectState.RECONNECTING:
            self._last_stream = self._assembler.recover_from_backfill(batch.trades, observed_at=now)
            self._reason = MonitorReason.OK if batch.trades else MonitorReason.INCOMPLETE
            return
        if not batch.trades:
            if self._assembler.accepted_trades():
                self._last_stream = self._assembler.ingest([], observed_at=now, allow_empty=True)
                self._reason = MonitorReason.OK
            else:
                self._reason = MonitorReason.INCOMPLETE
            return
        self._last_stream = self._assembler.ingest(batch.trades, observed_at=now)
        self._reason = MonitorReason.OK

    def _refresh_ohlcv(self, now: datetime) -> None:
        self._ohlcv_reason = None
        self._series_15m = self._fetch_ohlcv(self.identity, Timeframe.M15, now)
        self._series_4h = self._fetch_ohlcv(self._identity_4h, Timeframe.H4, now)

    def _fetch_ohlcv(
        self,
        identity: EvidenceMarketIdentity,
        timeframe: Timeframe,
        now: datetime,
    ) -> ClosedOhlcvSeries | None:
        wanted = (
            FIRST_SLICE_MIN_FINAL_15M if timeframe is Timeframe.M15 else FIRST_SLICE_MIN_FINAL_4H
        )
        try:
            return self._source.fetch_closed_ohlcv(
                identity=identity,
                instrument=self.instrument,
                timeframe=timeframe,
                min_final_bars=wanted,
                evaluated_at=now,
            )
        except FormingCandleError:
            try:
                series = self._source.fetch_closed_ohlcv(
                    identity=identity,
                    instrument=self.instrument,
                    timeframe=timeframe,
                    min_final_bars=1,
                    evaluated_at=now,
                )
                self._ohlcv_reason = "partial"
                return series
            except MarketContractError as exc:
                self._ohlcv_reason = type(exc).__name__
                return None
        except MarketContractError as exc:
            self._ohlcv_reason = type(exc).__name__
            return None

    def _window(self, now: datetime) -> tuple[datetime, datetime]:
        freshness = timedelta(seconds=first_slice_freshness_policy().trade_max_age_seconds)
        cursor = self._assembler.cursor
        if cursor.reconnect_state is ReconnectState.RECONNECTING:
            start = self._watermark_time or (now - freshness)
        elif cursor.last_event_at is not None:
            start = cursor.last_event_at
        else:
            start = now - freshness
        if now - start > _MAX_LOOKBACK:
            start = now - _MAX_LOOKBACK
        if now <= start:
            start = now - freshness
        return start, now

    def _assert_batch_identity(self, batch: OrderedTradeBatch) -> None:
        if batch.identity != self.identity:
            raise WrongMarketError("Trade batch identity does not match the monitor identity.")
        if batch.identity.instrument.instrument_id != self.instrument.instrument_id:
            raise WrongInstrumentError("Trade batch instrument does not match the catalog symbol.")
        if batch.source_connection_id != self._assembler.connection_identity:
            raise WrongSourceError(
                "Trade batch lineage does not match the current connection epoch."
            )

    def _begin_reconnect(self, now: datetime) -> None:
        if self._assembler.cursor.gap_state is GapState.UNRECOVERABLE:
            return
        if self._assembler.cursor.reconnect_state is ReconnectState.RECONNECTING:
            return
        self._watermark_time = self._assembler.cursor.last_event_at
        self._assembler.begin_reconnect(observed_at=now)
        self._last_batch = None
        self._last_stream = None

    def _apply_backoff(self, now: datetime, *, retry_after_seconds: float | None = None) -> None:
        delay = delay_seconds(
            self._backoff_attempt,
            self._backoff_policy,
            retry_after_seconds=retry_after_seconds,
        )
        self._backoff_until = now + timedelta(seconds=delay)
        self._backoff_attempt += 1

    def _clear_backoff(self) -> None:
        self._backoff_until = None
        self._backoff_attempt = 0
        self._last_error_class = None

    def _in_backoff(self, now: datetime) -> bool:
        return self._backoff_until is not None and now < self._backoff_until

    def _project(self, now: datetime) -> SymbolMonitorSnapshot:
        cursor = self._assembler.cursor
        trades = self._assembler.accepted_trades()
        terminal = trades[-1] if trades else None
        stream_healthy = (
            cursor.gap_state is GapState.NONE
            and cursor.warm_up_status is WarmUpStatus.COMPLETE
            and cursor.reconnect_state in {ReconnectState.CONTINUOUS, ReconnectState.RECOVERED}
        )
        suppress_quote = (
            self._reason
            in {
                MonitorReason.PROVIDER_UNAVAILABLE,
                MonitorReason.PROVIDER_ERROR,
                MonitorReason.DUPLICATE_CONFLICT,
                MonitorReason.OUT_OF_ORDER,
                MonitorReason.SYMBOL_MISMATCH,
                MonitorReason.WRONG_SOURCE,
                MonitorReason.SPOT_REJECTED,
                MonitorReason.UNRECOVERABLE_GAP,
                MonitorReason.GAP,
            }
            or cursor.reconnect_state is ReconnectState.RECONNECTING
        )
        quote = (
            None
            if terminal is None or suppress_quote
            else quote_from_terminal_trade(
                terminal,
                identity=self.identity,
                instrument=self.instrument,
                evaluated_at=now,
                replay=self._replay,
                reconnect_state=cursor.reconnect_state,
                stream_healthy=stream_healthy,
            )
        )
        availability, reason = self._availability(now, quote)
        coverage = self._coverage()
        snapshot = SymbolMonitorSnapshot(
            symbol=self.instrument.provider_symbol,
            mode=MarketMode.REPLAY if self._replay else MarketMode.LIVE_PERPETUAL,
            availability=availability,
            reason=reason,
            current_price=quote,
            last_update=cursor.last_event_at or cursor.updated_at,
            evaluated_at=now,
            instrument_id=self.instrument.instrument_id,
            provider_symbol=self.instrument.provider_symbol,
            source_family=self.identity.source.family,
            provider_name=self.identity.provenance.provider_name,
            is_live=self.identity.provenance.is_live,
            is_mock=self.identity.provenance.is_mock,
            fallback_used=False,
            perpetual=True,
            watcher_activated=False,
            live_executable=False,
            stream=StreamHealth(
                reconnect_state=cursor.reconnect_state,
                gap_state=cursor.gap_state,
                warm_up_status=cursor.warm_up_status,
                last_sequence=cursor.last_sequence,
                last_event_id=cursor.last_event_id,
                last_event_at=cursor.last_event_at,
                reconnect_count=cursor.reconnect_count,
                connection_identity=cursor.connection_identity,
            ),
            coverage=coverage,
            cvd=self._cvd(stream_healthy),
            ohlcv=self._ohlcv_health(),
            provider=self._provider_health(),
            backoff=BackoffReport(
                active=self._in_backoff(now),
                attempt=self._backoff_attempt,
                next_retry_at=self._backoff_until,
                last_error_class=self._last_error_class,
            ),
            content_hash="0" * 64,
        )
        return snapshot.model_copy(update={"content_hash": monitor_semantic_hash(snapshot)})

    def _availability(
        self, now: datetime, quote: CurrentPriceQuote | None
    ) -> tuple[MarketAvailability, MonitorReason]:
        del now
        cursor = self._assembler.cursor
        if self._replay:
            return MarketAvailability.REPLAY, MonitorReason.REPLAY_FIXTURE
        if self._reason is MonitorReason.SPOT_REJECTED:
            return MarketAvailability.UNAVAILABLE, self._reason
        if self._reason is MonitorReason.SYMBOL_MISMATCH:
            return MarketAvailability.UNAVAILABLE, self._reason
        if self._reason is MonitorReason.WRONG_SOURCE:
            return MarketAvailability.UNAVAILABLE, self._reason
        if cursor.gap_state is GapState.UNRECOVERABLE:
            return MarketAvailability.UNAVAILABLE, MonitorReason.UNRECOVERABLE_GAP
        if self._reason is MonitorReason.PROVIDER_UNAVAILABLE:
            return MarketAvailability.UNAVAILABLE, self._reason
        if self._reason is MonitorReason.DUPLICATE_CONFLICT:
            return MarketAvailability.UNAVAILABLE, self._reason
        if self._reason is MonitorReason.OUT_OF_ORDER:
            return MarketAvailability.UNAVAILABLE, self._reason
        if self._reason is MonitorReason.PROVIDER_ERROR:
            return MarketAvailability.UNAVAILABLE, self._reason
        if cursor.reconnect_state is ReconnectState.RECONNECTING or self._reason in {
            MonitorReason.RATE_LIMITED,
            MonitorReason.BACKOFF,
            MonitorReason.GAP,
            MonitorReason.RECONNECTING,
        }:
            reason = self._reason
            if self._reason is MonitorReason.BACKOFF:
                reason = (
                    MonitorReason.RATE_LIMITED
                    if self._last_error_class == "RateLimitedError"
                    else MonitorReason.RECONNECTING
                )
            elif self._reason is MonitorReason.OK:
                reason = MonitorReason.RECONNECTING
            return MarketAvailability.DEGRADED, reason
        if quote is None:
            if self._reason is MonitorReason.INCOMPLETE:
                return MarketAvailability.UNAVAILABLE, MonitorReason.INCOMPLETE
            return MarketAvailability.STALE, MonitorReason.STALE_STREAM
        if quote.usable_as_current_market_price:
            return MarketAvailability.FRESH, MonitorReason.OK
        if quote.presentation.value == "stale":
            return MarketAvailability.STALE, MonitorReason.STALE_STREAM
        return MarketAvailability.DEGRADED, self._reason

    def _coverage(self) -> CoverageReport:
        proof: TradeWindowCoverageProof | None = None
        if self._last_batch is not None:
            proof = self._last_batch.coverage
        elif self._last_stream is not None:
            proof = self._last_stream.coverage
        if proof is None:
            return CoverageReport(
                completeness=DataCompleteness.UNKNOWN,
                gap_state=self._assembler.cursor.gap_state,
            )
        return CoverageReport(
            completeness=proof.completeness,
            gap_state=proof.gap_state,
            content_hash=proof.content_hash,
            first_trade_id=proof.first_trade_id,
            last_trade_id=proof.last_trade_id,
        )

    def _cvd(self, stream_healthy: bool) -> StreamCvdReport:
        batch = self._last_batch
        if (
            not stream_healthy
            or batch is None
            or not batch.trades
            or batch.coverage.completeness is not DataCompleteness.COMPLETE
            or batch.coverage.gap_state is not GapState.NONE
        ):
            return StreamCvdReport(available=False, reason="incomplete_or_unhealthy_stream")
        try:
            signed, total = accumulate_signed_quote(batch.trades)
        except MarketContractError as exc:
            return StreamCvdReport(available=False, reason=type(exc).__name__)
        ratio = None if total == 0 else str(signed / total)
        return StreamCvdReport(
            available=True,
            signed_quote_delta=str(signed),
            total_quote_volume=str(total),
            signed_flow_ratio=ratio,
            event_count=len(batch.trades),
            event_set_hash=event_set_hash(batch.trades),
        )

    def _ohlcv_health(self) -> OhlcvHealth:
        series_15 = self._series_15m
        series_4h = self._series_4h
        complete_15 = (
            DataCompleteness.COMPLETE
            if series_15 is not None and len(series_15.bars) >= FIRST_SLICE_MIN_FINAL_15M
            else DataCompleteness.PARTIAL
            if series_15 is not None
            else DataCompleteness.UNKNOWN
        )
        complete_4h = (
            DataCompleteness.COMPLETE
            if series_4h is not None and len(series_4h.bars) >= FIRST_SLICE_MIN_FINAL_4H
            else DataCompleteness.PARTIAL
            if series_4h is not None
            else DataCompleteness.UNKNOWN
        )
        latest = series_15.bars[-1] if series_15 is not None and series_15.bars else None
        latest_final = (
            None
            if latest is None
            else latest.finality is Finality.FINAL and latest.provider_complete
        )
        return OhlcvHealth(
            available=series_15 is not None or series_4h is not None,
            completeness_15m=complete_15,
            completeness_4h=complete_4h,
            latest_15m_close=str(latest.close) if latest is not None else None,
            latest_15m_end=latest.interval_end if latest is not None else None,
            latest_15m_final=latest_final,
            series_15m_hash=series_15.content_hash if series_15 is not None else None,
            series_4h_hash=series_4h.content_hash if series_4h is not None else None,
            reason=self._ohlcv_reason,
        )

    def _provider_health(self) -> ProviderHealthReport:
        try:
            status = self._source.status()
        except Exception:  # status probes must never crash the monitor
            return ProviderHealthReport(
                name=self._source.name,
                health=ProviderHealth.UNAVAILABLE,
                is_mock=self._replay,
                using_fallback=False,
                detail="Provider status probe failed closed.",
            )
        if status.using_fallback:
            return ProviderHealthReport(
                name=status.name,
                health=ProviderHealth.UNAVAILABLE,
                is_mock=status.is_mock,
                using_fallback=False,
                detail="Provider reported a fallback; monitor refuses fabricated substitutes.",
            )
        return ProviderHealthReport(
            name=status.name,
            health=status.health,
            is_mock=status.is_mock,
            using_fallback=False,
            detail=status.detail,
        )

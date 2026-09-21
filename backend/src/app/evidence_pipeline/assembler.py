"""Assemble first-slice USD-M evidence into CanonicalEvidenceWindowV1."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid5

from app.evidence_pipeline.canonical import (
    build_first_slice_assessment_command,
    first_slice_read_policy,
    timeframe_identity,
)
from app.evidence_pipeline.current_price import quote_current_price
from app.evidence_pipeline.types import (
    AssembledCanonicalEvidence,
    CompletenessReport,
    CurrentPriceQuote,
)
from app.market_contracts.adapters.protocol import PerpetualMarketSource
from app.market_contracts.catalog import PerpetualInstrumentCatalog, default_perpetual_catalog
from app.market_contracts.cursor import TradeStreamAssembler
from app.market_contracts.cvd import first_slice_baseline_open, first_slice_cvd_window
from app.market_contracts.enums import DataCompleteness, MarketType
from app.market_contracts.errors import (
    FallbackForbiddenError,
    FormingCandleError,
    IncompleteWarmUpError,
    SpotFallbackRejectedError,
    StaleEvidenceError,
    WrongSourceError,
)
from app.market_contracts.first_slice import (
    FIRST_SLICE_MIN_FINAL_4H,
    FIRST_SLICE_MIN_FINAL_15M,
    canonical_first_slice_clock,
    first_slice_identity,
    first_slice_spec,
)
from app.market_contracts.flow import bar_signed_quote_flow
from app.market_contracts.freshness import (
    evaluate_freshness,
    first_slice_freshness_policy,
    live_confirmation_window_open,
)
from app.market_contracts.identity import EvidenceMarketIdentity
from app.market_contracts.ohlcv import ClosedOhlcvSeries, OhlcvBar
from app.schemas.common import Timeframe
from app.signal_fusion.adapters import evidence_window_from_assessment_command
from app.signal_fusion.enums import EvidenceAdapterKind
from app.signal_fusion.first_slice_types import FirstSliceEvidenceBundle
from app.signal_fusion.observation import TenantExternalAssertion
from app.signal_fusion.policy import FusionPolicy
from app.signal_fusion.types import ManualLevelRevisionRef

_CONNECTION_NAMESPACE = UUID("a0640000-1111-4000-8000-000000000064")


class FirstSliceEvidenceAssembler:
    """Read-only assembler. BTCUSDT is the enabled first slice; catalog can grow."""

    def __init__(
        self,
        source: PerpetualMarketSource,
        *,
        replay: bool,
        catalog: PerpetualInstrumentCatalog | None = None,
    ) -> None:
        self._source = source
        self._replay = replay
        self._catalog = catalog if catalog is not None else default_perpetual_catalog()

    def assemble(
        self,
        *,
        organization_id: UUID,
        symbol: str = first_slice_spec().symbol,
        evaluated_at: datetime | None = None,
        policy: FusionPolicy | None = None,
        adapter_kind: EvidenceAdapterKind = EvidenceAdapterKind.DETECTOR,
        tenant_assertions: tuple[TenantExternalAssertion, ...] = (),
        manual_level_revision: ManualLevelRevisionRef | None = None,
        connection_id: UUID | None = None,
    ) -> AssembledCanonicalEvidence:
        instrument = self._catalog.require(symbol)
        clock = evaluated_at or self._default_clock()
        trigger_identity = first_slice_identity(
            timeframe=Timeframe.M15,
            replay=self._replay,
            is_live=not self._replay,
            instrument=instrument,
        )
        context_identity = timeframe_identity(trigger_identity, Timeframe.H4)
        self._assert_live_contract(trigger_identity)

        series_15m = self._source.fetch_closed_ohlcv(
            identity=trigger_identity,
            instrument=instrument,
            timeframe=Timeframe.M15,
            min_final_bars=FIRST_SLICE_MIN_FINAL_15M,
            evaluated_at=clock,
        )
        series_4h = self._source.fetch_closed_ohlcv(
            identity=context_identity,
            instrument=instrument,
            timeframe=Timeframe.H4,
            min_final_bars=FIRST_SLICE_MIN_FINAL_4H,
            evaluated_at=clock,
        )
        trigger = _last_final_bar(series_15m)
        context = _context_bar(series_4h, trigger)
        window_start = first_slice_baseline_open(trigger)
        window_end = trigger.interval_end
        lineage = connection_id or uuid5(
            _CONNECTION_NAMESPACE,
            f"{instrument.instrument_id}:{self._source.name}:"
            f"{window_start.isoformat()}:{window_end.isoformat()}",
        )
        batch = self._source.fetch_ordered_trades(
            identity=trigger_identity,
            instrument=instrument,
            start=window_start,
            end=window_end,
            source_connection_id=lineage,
            receive_at=clock,
        )
        assembler = TradeStreamAssembler(
            trigger_identity,
            connected_at=clock,
            connection_identity=lineage,
            expected_contiguous_count=len(batch.trades),
        )
        snapshot = assembler.ingest_batch(batch, observed_at=clock)
        live_window = live_confirmation_window_open(
            closed_interval_end=trigger.interval_end,
            evaluated_at=clock,
        )
        cvd = first_slice_cvd_window(
            identity=trigger_identity,
            series_15m=series_15m,
            snapshot=snapshot,
            created_at=clock,
            require_live_freshness=live_window,
        )
        signed_flow = bar_signed_quote_flow(
            identity=trigger_identity,
            bar=trigger,
            snapshot=snapshot,
            evaluated_at=clock,
            require_live_freshness=live_window,
        )
        freshness = evaluate_freshness(
            source_time=cvd.event_time_max or snapshot.trades[-1].event_timestamp,
            evaluated_at=clock,
            policy=first_slice_freshness_policy(),
            require_fresh=live_window,
        )
        current: CurrentPriceQuote | None
        try:
            current = quote_current_price(
                self._source,
                identity=trigger_identity,
                instrument=instrument,
                evaluated_at=clock,
                connection_id=lineage,
                replay=self._replay,
            )
        except (StaleEvidenceError, IncompleteWarmUpError):
            if live_window:
                raise
            current = None
        bound_policy = policy or first_slice_read_policy(organization_id)
        if bound_policy.organization_id != organization_id:
            raise WrongSourceError(
                "Fusion policy organization_id does not match the caller tenant."
            )
        command = build_first_slice_assessment_command(
            organization_id=organization_id,
            policy=bound_policy,
            trigger=trigger,
            context=context,
            trigger_identity=trigger_identity,
            context_identity=context_identity,
            evaluated_at=clock,
            freshness_state=freshness.state,
            adapter_kind=adapter_kind,
            cvd=cvd,
            signed_flow=signed_flow,
            coverage=snapshot.coverage,
            tenant_assertions=tenant_assertions,
            manual_level_revision=manual_level_revision,
        )
        window = evidence_window_from_assessment_command(command)
        bundle = FirstSliceEvidenceBundle(
            bars_15m=tuple(series_15m.bars),
            bars_4h=tuple(series_4h.bars),
            snapshot=snapshot,
        )
        completeness = CompletenessReport(
            ohlcv_15m=DataCompleteness.COMPLETE,
            ohlcv_4h=DataCompleteness.COMPLETE,
            cvd=cvd.data_completeness,
            signed_flow=DataCompleteness.COMPLETE,
            coverage_content_hash=snapshot.coverage.content_hash,
            cvd_content_hash=cvd.content_hash,
            signed_flow_content_hash=signed_flow.content_hash,
        )
        return AssembledCanonicalEvidence(
            organization_id=organization_id,
            replay=self._replay,
            evaluated_at=clock,
            identity=trigger_identity,
            trigger_bar=trigger,
            context_bar=context,
            series_15m=series_15m,
            series_4h=series_4h,
            cvd=cvd,
            signed_flow=signed_flow,
            current_price=current,
            completeness=completeness,
            freshness_state=freshness.state,
            bundle=bundle,
            assessment_command=command,
            evidence_window=window,
            evidence_window_hash=window.content_hash,
            connection_id=lineage,
            evaluation_mark=snapshot.trades[-1].price,
        )

    def _default_clock(self) -> datetime:
        if self._replay:
            return canonical_first_slice_clock().evaluated_at
        return datetime.now(UTC)

    def _assert_live_contract(self, identity: EvidenceMarketIdentity) -> None:
        if identity.market_type is not MarketType.PERPETUAL:
            raise SpotFallbackRejectedError("Spot market data cannot satisfy perpetual evidence.")
        if identity.provenance.fallback_used:
            raise FallbackForbiddenError("Assembled perpetual evidence cannot record fallback.")
        if self._replay and identity.provenance.is_live:
            raise WrongSourceError("Replay assembly cannot claim live provenance.")
        if not self._replay and (identity.provenance.is_mock or not identity.provenance.is_live):
            raise WrongSourceError("Live assembly cannot use mock or non-live provenance.")


def _last_final_bar(series: ClosedOhlcvSeries) -> OhlcvBar:
    if not series.bars:
        raise FormingCandleError("Closed OHLCV series is empty.")
    return series.bars[-1]


def _context_bar(series: ClosedOhlcvSeries, trigger: OhlcvBar) -> OhlcvBar:
    eligible = [bar for bar in series.bars if bar.interval_end <= trigger.interval_end]
    if not eligible:
        raise FormingCandleError("No final 4h context bar is closed at or before the 15m trigger.")
    return eligible[-1]

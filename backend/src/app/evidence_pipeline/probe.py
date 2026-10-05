"""Independent public exchange checks; no database, worker, Candidate or notification path."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import structlog

from app.evidence_pipeline.assembler import FirstSliceEvidenceAssembler, _required_derivative
from app.evidence_pipeline.current_price import quote_current_price
from app.evidence_pipeline.market_intelligence import read_order_flow
from app.market_contracts.adapters.binance_usdm import BinanceUsdmPerpetualSource
from app.market_contracts.adapters.bybit_usdt_perpetual import BybitUsdtPerpetualSource
from app.market_contracts.adapters.protocol import PerpetualMarketSource
from app.market_contracts.catalog import default_perpetual_catalog, instrument_for_source
from app.market_contracts.derivatives import DerivativeMetric
from app.market_contracts.evidence_diagnostics import (
    DiagnosticStatus,
    EvidenceComponent,
    EvidenceDiagnostics,
)
from app.market_contracts.first_slice import (
    FIRST_SLICE_MIN_FINAL_4H,
    FIRST_SLICE_MIN_FINAL_15M,
    first_slice_identity,
)
from app.schemas.common import Timeframe

_PROBE_ORG = UUID("a0640000-1111-4000-8000-000000000064")


def probe_exchange(
    source: PerpetualMarketSource,
    *,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> dict[str, object]:
    """Use the same validators and additionally check quotes/derivatives/5m independently.

    A fresh monitor or derivative cannot make an incomplete historical CVD pass.
    The report intentionally has no strategy, lease or Candidate authority.
    """
    now = clock()
    diagnostics = EvidenceDiagnostics(source, "BTCUSDT", now)
    instrument = diagnostics.run(
        EvidenceComponent.INSTRUMENT,
        lambda: instrument_for_source(source, default_perpetual_catalog(), "BTCUSDT"),
    )
    identity = first_slice_identity(
        timeframe=Timeframe.M15,
        instrument=instrument,
        replay=False,
        is_live=True,
    )
    diagnostics.identity = identity
    proof: dict[str, object] = {}
    assembler = FirstSliceEvidenceAssembler(source, replay=False, clock=clock)
    canonical_complete = False
    try:
        assembled = assembler.assemble(organization_id=_PROBE_ORG)
        canonical_complete = True
        proof.update(
            evidence_window_hash=assembled.evidence_window_hash,
            coverage_content_hash=assembled.completeness.coverage_content_hash,
            cvd_content_hash=assembled.completeness.cvd_content_hash,
            signed_flow_content_hash=assembled.completeness.signed_flow_content_hash,
            cvd_event_count=assembled.cvd.event_count,
            cvd_signed_quote_delta=str(assembled.cvd.signed_quote_delta),
            cvd_reset_policy=assembled.cvd.reset_policy_version,
            cvd_arithmetic_policy=assembled.cvd.arithmetic_policy_version,
            signed_flow_ratio=str(assembled.signed_flow.signed_flow_ratio),
        )
    except Exception:
        # Exact safe component reason is in the assembler's bounded diagnostics.
        pass
    core_rows = assembler.diagnostics
    # A core failure must not hide whether the other independent endpoints work.
    for component, timeframe, minimum in (
        (EvidenceComponent.OHLCV_15M, Timeframe.M15, FIRST_SLICE_MIN_FINAL_15M),
        (EvidenceComponent.OHLCV_4H, Timeframe.H4, FIRST_SLICE_MIN_FINAL_4H),
    ):
        if any(
            row.component is component and row.status is DiagnosticStatus.AVAILABLE
            for row in core_rows
        ):
            continue
        diagnostics.evaluated_at = clock()
        with suppress(Exception):
            diagnostics.run(
                component,
                lambda timeframe=timeframe, minimum=minimum: source.fetch_closed_ohlcv(
                    identity=identity.model_copy(update={"timeframe": timeframe}),
                    instrument=instrument,
                    timeframe=timeframe,
                    min_final_bars=minimum,
                    evaluated_at=diagnostics.evaluated_at,
                ),
                timeframe=timeframe,
            )
    diagnostics.evaluated_at = clock()
    try:
        quote = diagnostics.run(
            EvidenceComponent.PRICE,
            lambda: quote_current_price(
                source,
                identity=identity,
                instrument=instrument,
                evaluated_at=diagnostics.evaluated_at,
                connection_id=uuid4(),
                replay=False,
            ),
        )
        proof["current_price"] = str(quote.price)
    except Exception:
        pass
    for metric in DerivativeMetric:
        diagnostics.evaluated_at = clock()
        try:
            item = diagnostics.run(
                EvidenceComponent(metric.value),
                lambda metric=metric: _required_derivative(
                    source,
                    metric=metric,
                    identity=identity,
                    instrument=instrument,
                    observed_at=diagnostics.evaluated_at,
                ),
            )
            proof[metric.value] = {
                "content_hash": item.content_hash,
                "units": item.units,
                "calculation_method": item.calculation_method,
            }
        except Exception:
            pass
    diagnostics.evaluated_at = clock()
    try:
        with diagnostics.stage(EvidenceComponent.ORDER_FLOW, timeframe=Timeframe.M5) as probe:
            flow = read_order_flow(
                source,
                identity=identity,
                instrument=instrument,
                observed_at=diagnostics.evaluated_at,
            )
            from app.evidence_pipeline.assembler import _require_order_flow_diagnosed

            _require_order_flow_diagnosed(
                flow, identity=identity, evaluated_at=diagnostics.evaluated_at
            )
            probe.observe(flow, historical=True)
            proof["order_flow_5m"] = {
                "content_hash": flow.content_hash,
                "coverage_content_hash": flow.coverage_content_hash,
                "calculation_method": flow.calculation_method,
                "reset_semantics": flow.reset_semantics,
            }
    except Exception:
        pass
    finally:
        release = getattr(source, "release_symbol_history", None)
        if callable(release):
            release("BTCUSDT")
    independent = (
        EvidenceComponent.PRICE,
        EvidenceComponent.OPEN_INTEREST,
        EvidenceComponent.FUNDING,
        EvidenceComponent.ORDER_FLOW,
    )
    all_available = canonical_complete and all(
        any(
            row.component is component and row.status is DiagnosticStatus.AVAILABLE
            for row in diagnostics.items
        )
        for component in independent
    )
    return {
        "schema_version": "IndependentExchangeProbeV1",
        "canonical_market_window_complete": canonical_complete,
        "all_requested_components_available": all_available,
        "watcher_acceptance_verified": False,
        "source": {
            "provider": identity.source.provider_name,
            "source_family": identity.source.family.value,
            "adapter_version": identity.source.adapter_version,
            "venue": identity.venue.value,
            "market_type": identity.market_type.value,
            "instrument_id": instrument.instrument_id,
            "provider_symbol": instrument.provider_symbol,
        },
        "diagnostics": [row.model_dump(mode="json") for row in (*core_rows, *diagnostics.items)],
        "proof": proof,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--provider", choices=("binance_usdm", "bybit_usdt_perpetual"), required=True
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    structlog.configure(logger_factory=structlog.PrintLoggerFactory(file=sys.stderr))
    source = (
        BinanceUsdmPerpetualSource(max_retries=0)
        if args.provider == "binance_usdm"
        else BybitUsdtPerpetualSource(max_retries=0)
    )
    try:
        result = probe_exchange(source)
    finally:
        source.close()
    body = json.dumps(result, indent=2) + "\n"
    if args.output is not None:
        args.output.write_text(body)
    else:
        print(body, end="")
    return 0 if result["all_requested_components_available"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""OHLCV-only family assembly using Watcher's existing contracted source.

No CVD, flow, funding or open interest acquisition is required for detection.
Quote acquisition is optional here; existing paper execution still requires
fresh contracted live evidence and all existing account/risk gates.
"""

from contextlib import suppress
from datetime import timedelta
from uuid import uuid5

from sqlalchemy.orm import Session

from app.candidate_alerts.nested import NestedAlertSummary, required_evidence_fresh
from app.evidence_pipeline.canonical import semantic_source_from_identity
from app.evidence_pipeline.current_price import quote_current_price
from app.evidence_pipeline.types import (
    AssembledCanonicalEvidence,
    CompletenessReport,
    EvidenceClockReport,
)
from app.market_contracts.catalog import instrument_for_source
from app.market_contracts.enums import DataCompleteness, FreshnessState
from app.market_contracts.errors import MarketContractError, StaleEvidenceError
from app.market_contracts.first_slice import first_slice_identity
from app.market_contracts.hashing import with_content_hash
from app.market_contracts.identity import interval_timedelta
from app.market_contracts.observation import observation_from_ohlcv
from app.services.canonical_serialization import canonical_sha256
from app.signal_fusion.adapters import AssessmentCommand, evidence_window_from_assessment_command
from app.signal_fusion.enums import EvidenceAdapterKind, EvidenceRole
from app.signal_fusion.first_slice_types import FirstSliceEvidenceBundle
from app.signal_fusion.types import HalfOpenInterval, TriggerIdentity
from app.strategy_brain.detector import NAMESPACE, detect_nested
from app.strategy_brain.records import attach_paper_result, record_detections, scoped_setup_id


def assemble_nested(
    assembler: object,
    *,
    executable: object,
    organization_id: object,
    session: Session | None,
) -> AssembledCanonicalEvidence:
    spec = executable.authored_spec
    source, catalog = assembler._source, assembler._catalog
    replay = assembler._replay
    now = assembler._default_clock()
    instrument = instrument_for_source(source, catalog, spec.symbol)
    identity = first_slice_identity(
        timeframe=spec.trigger_timeframe, replay=replay, is_live=not replay, instrument=instrument
    )
    assembler._assert_live_contract(identity)
    series = source.fetch_closed_ohlcv(
        identity=identity,
        instrument=instrument,
        timeframe=spec.trigger_timeframe,
        min_final_bars=256,
        evaluated_at=now,
    )
    bars = tuple(series.bars)
    if not timedelta(0) <= now - bars[-1].interval_end < interval_timedelta(spec.trigger_timeframe):
        raise StaleEvidenceError("Required Nested OHLCV is stale.")
    events = detect_nested(bars, spec, evaluated_at=now)
    latest = events[-1] if events else None
    trigger = bars[-1]
    policy = executable.fusion_policy
    trigger_obs = observation_from_ohlcv(
        trigger,
        identity=identity,
        observed_at=now,
        receive_time=now,
        freshness_state=FreshnessState.FRESH,
    )
    # A typed OHLCV-series observation binds every causal bar to canonical evidence.
    history_hash = canonical_sha256([b.content_hash for b in bars])
    history_obs = with_content_hash(
        trigger_obs.model_copy(
            update={
                "observation_id": uuid5(NAMESPACE, history_hash),
                "source_event_id": f"history:{history_hash}",
                "interval_start": bars[0].interval_start,
                "payload_content_hash": history_hash,
                "content_hash": "0" * 64,
            }
        )
    )
    command = AssessmentCommand(
        organization_id=organization_id,
        strategy_version_id=policy.strategy_version_id,
        executable_setup=policy.executable_setup,
        fusion_policy_version=policy.policy_version,
        finality_policy_version=policy.finality_policy_version,
        freshness_policy_version=policy.freshness_policy_version,
        direction=spec.direction,
        evidence_identity=identity,
        interval=HalfOpenInterval(start=bars[0].interval_start, end=trigger.interval_end),
        trigger=TriggerIdentity(
            natural_event_id=trigger.source_event_id, revision=trigger.revision
        ),
        mandatory_evidence_roles=policy.required_roles,
        public_observations=(trigger_obs, history_obs),
        selected_roles=(EvidenceRole.TRIGGER_OHLCV, EvidenceRole.STRUCTURE),
        source_set=(semantic_source_from_identity(identity),),
        adapter_kind=EvidenceAdapterKind.WATCHER,
        role_timeframes=policy.role_timeframes,
    )
    window = evidence_window_from_assessment_command(command)
    if session is not None:
        record_detections(
            session,
            organization_id=organization_id,
            strategy_id=executable.strategy_id,
            version_id=executable.strategy_version_id,
            spec=spec,
            bars=bars,
            events=events,
            evidence_hash=window.content_hash,
            evaluated_at=now,
        )
    quote = None
    with suppress(MarketContractError):
        quote = quote_current_price(
            source,
            identity=identity,
            instrument=instrument,
            evaluated_at=now,
            connection_id=uuid5(NAMESPACE, window.content_hash),
            replay=replay,
        )
    return AssembledCanonicalEvidence(
        organization_id=organization_id,
        replay=replay,
        evaluated_at=now,
        identity=identity,
        trigger_bar=trigger,
        context_bar=None,
        series_15m=series,
        series_4h=None,
        cvd=None,
        signed_flow=None,
        current_price=quote,
        completeness=CompletenessReport(
            ohlcv_15m=DataCompleteness.COMPLETE,
            ohlcv_4h=DataCompleteness.UNKNOWN,
            cvd=DataCompleteness.UNKNOWN,
            signed_flow=DataCompleteness.UNKNOWN,
        ),
        freshness_state=FreshnessState.FRESH,
        clocks=EvidenceClockReport(
            quote_source_time=quote.source_time if quote else None,
            quote_fresh=quote is not None and quote.usable_as_current_market_price,
            live_confirmation_window_open=True,
            trigger_finality=trigger.finality,
            trigger_interval_end=trigger.interval_end,
            historical_closed_evidence=False,
            closed_evidence_valid=True,
            subsequent_final_15m_count=0,
            setup_expired=latest is not None and latest.state.value in {"EXPIRED", "INVALIDATED"},
            setup_lifetime_remaining_bars=spec.parameters.confirmation_window,
            setup_trigger_bar_hash=trigger.content_hash,
        ),
        bundle=FirstSliceEvidenceBundle(bars_15m=bars),
        assessment_command=command,
        evidence_window=window,
        evidence_window_hash=window.content_hash,
        connection_id=uuid5(NAMESPACE, window.content_hash),
        evaluation_mark=quote.price if quote else trigger.close,
    )


def record_paper_link(
    session: Session | None,
    *,
    target: object,
    report: object,
    evidence: object,
    now: object,
) -> NestedAlertSummary | None:
    if report.discussion is None:
        return
    last = getattr(evidence, "last_assembly", lambda: None)()
    if last is None:
        return
    assembled, policy = last
    from app.schemas.nested_continuation import NestedContinuationSpec

    if not isinstance(policy.authored_spec, NestedContinuationSpec):
        return
    events = detect_nested(
        assembled.bundle.bars_15m, policy.authored_spec, evaluated_at=assembled.evaluated_at
    )
    if not events:
        return
    identity = scoped_setup_id(
        target.organization_id, target.strategy_version_id, events[-1].setup_id
    )
    if session is not None:
        attach_paper_result(
            session,
            organization_id=target.organization_id,
            setup_id=identity,
            candidate_id=report.discussion.candidate.candidate_id,
            assessment_id=report.discussion.assessment.assessment_id,
            proof=report,
            now=now,
        )

    latest = events[-1]
    if (
        latest.state.value != "CONFIRMED"
        or latest.confirmed_index != len(assembled.bundle.bars_15m) - 1
        or not required_evidence_fresh(report.discussion.assessment, assembled.evidence_window, now)
    ):
        return None
    return NestedAlertSummary(
        organization_id=target.organization_id,
        strategy_version_id=target.strategy_version_id,
        setup_id=identity,
        symbol=policy.authored_spec.symbol,
        stage=latest.stage,
        evidence_at=latest.detected_at,
        decision=report.paper_loop_reason or "not_evaluated",
        risk_state=report.eligibility_state or "not_evaluated",
        reasons=tuple(dict.fromkeys([*latest.reason_codes, report.paper_loop_reason])),
    )

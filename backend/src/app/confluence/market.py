"""Read canonical payloads without acquiring data or calling detectors."""

from datetime import datetime
from decimal import Decimal
from typing import Any, cast

from app.confluence.contracts import ComponentName, ConfluenceComponent, EvidenceSource
from app.confluence.policy import ConfluencePolicy
from app.market_contracts.derivatives import DerivativeMetric, require_derivative_observations
from app.market_contracts.enums import FreshnessState
from app.market_contracts.errors import MarketContractError, StaleEvidenceError
from app.market_contracts.hashing import with_content_hash
from app.market_contracts.identity import EvidenceMarketIdentity, interval_timedelta
from app.market_contracts.ohlcv import OhlcvBar, assert_closed_series_bars
from app.market_contracts.order_flow import require_order_flow
from app.schemas.common import Timeframe, TradeDirection
from app.schemas.nested_continuation import EvidenceAvailability as Availability
from app.services.canonical_serialization import canonical_sha256
from app.signal_fusion.adapters import AssessmentCommand
from app.signal_fusion.first_slice_types import FirstSliceEvidenceBundle

ZERO, ONE = Decimal(0), Decimal(1)


def component(
    key: str,
    *,
    reason: str,
    availability: Availability = Availability.MISSING,
    value: Decimal | str | bool | None = None,
    unit: str = "not_measured",
    contribution: Decimal | None = None,
    source: tuple[EvidenceSource, ...] = (),
    timestamp: datetime | None = None,
    now: datetime,
) -> ConfluenceComponent:
    age = Decimal(str((now - timestamp).total_seconds())) if timestamp else None
    freshness = (
        FreshnessState.FRESH
        if availability is Availability.AVAILABLE
        else FreshnessState.STALE
        if availability is Availability.STALE
        else FreshnessState.UNKNOWN
    )
    return ConfluenceComponent(
        key=key,
        availability=availability,
        value=value,
        unit=unit,
        normalized_contribution=contribution if availability is Availability.AVAILABLE else None,
        source=source,
        timestamp=timestamp,
        freshness=freshness,
        age_seconds=age,
        reason=reason,
    )


def candle_status(
    bars: tuple[OhlcvBar, ...], identity: EvidenceMarketIdentity, now: datetime
) -> tuple[Availability, str]:
    if not bars:
        return Availability.MISSING, "No canonical closed candle payload supplied."
    try:
        assert_closed_series_bars(identity, bars[-1].timeframe, list(bars))
        for bar in bars:
            OhlcvBar.model_validate(bar.model_dump())
            if bar.instrument != identity.instrument or with_content_hash(bar) != bar:
                raise ValueError("Candle identity or content hash mismatch.")
            if bar.interval_end > now or bar.source_time > now:
                raise ValueError("Future candle evidence.")
    except (ValueError, MarketContractError) as exc:
        return Availability.INCOMPLETE, str(exc)
    if now - bars[-1].interval_end >= interval_timedelta(bars[-1].timeframe):
        return Availability.STALE, "Latest candle is at least one full interval old."
    return Availability.AVAILABLE, "Canonical closed contiguous candle payload verified."


def candle_sources(bars: tuple[OhlcvBar, ...]) -> tuple[EvidenceSource, ...]:
    return tuple(
        EvidenceSource(
            contract="OhlcvBar", record_id=b.source_event_id, content_hash=b.content_hash
        )
        for b in bars
    )


def market_components(
    command: AssessmentCommand,
    evidence: FirstSliceEvidenceBundle,
    policy: ConfluencePolicy,
    now: datetime,
) -> tuple[dict[ComponentName, ConfluenceComponent], ConfluenceComponent]:
    result: dict[ComponentName, ConfluenceComponent] = {}
    bars = evidence.bars_15m
    availability, reason = candle_status(bars, command.evidence_identity, now)
    if availability is Availability.AVAILABLE:
        payloads = {o.payload_content_hash for o in command.public_observations}
        bar_hashes = {b.content_hash for b in bars}
        history_hash = canonical_sha256(cast(Any, [b.content_hash for b in bars]))
        if (
            bars[-1].source_event_id != command.trigger.natural_event_id
            or bars[-1].revision != command.trigger.revision
            or bars[-1].interval_end != command.interval.end
            or bars[-1].content_hash not in payloads
            or not (bar_hashes <= payloads or history_hash in payloads)
        ):
            availability, reason = Availability.INCOMPLETE, "Candle payload not bound to command."
    candle = component(
        "required_closed_candles",
        availability=availability,
        value=bool(bars),
        unit="canonical_payload_present",
        source=candle_sources(bars),
        timestamp=bars[-1].interval_end if bars else None,
        now=now,
        reason=reason,
    )
    # Volume is a ratio of the trigger's base volume to the prior 20 bars.
    prior = bars[-(policy.volume_lookback + 1) : -1]
    mean = sum((b.base_volume for b in prior), ZERO) / len(prior) if prior else ZERO
    volume_status = availability
    if availability is Availability.AVAILABLE and (
        len(prior) < policy.volume_lookback or mean <= 0
    ):
        volume_status = Availability.INCOMPLETE
    ratio = bars[-1].base_volume / mean if mean > 0 and bars else None
    result[ComponentName.VOLUME] = component(
        ComponentName.VOLUME,
        availability=volume_status,
        value=ratio if volume_status is Availability.AVAILABLE else None,
        unit="trigger_base_volume/prior_mean_base_volume",
        contribution=min(ONE, ratio / policy.volume_reference_ratio) if ratio is not None else None,
        source=candle_sources((*prior, bars[-1])) if bars else (),
        timestamp=candle.timestamp,
        reason=(
            "Relative volume capped at the versioned reference; full lookback "
            "and positive mean required."
        ),
        now=now,
    )
    result[ComponentName.VOLATILITY] = component(
        ComponentName.VOLATILITY,
        availability=availability,
        value=(bars[-1].high - bars[-1].low) / bars[-1].close
        if bars and availability is Availability.AVAILABLE
        else None,
        unit="closed_candle_range/close",
        source=candle.source[-1:],
        timestamp=candle.timestamp,
        reason="Measured candle range only; no directional quality normalization or ATR claim.",
        now=now,
    )
    htf = evidence.bars_4h
    htf_identity = command.evidence_identity.model_copy(update={"timeframe": Timeframe.H4})
    status, htf_reason = candle_status(htf, htf_identity, now)
    if status is Availability.AVAILABLE and (
        len(htf) < 2
        or interval_timedelta(Timeframe.H4)
        <= interval_timedelta(command.evidence_identity.timeframe or Timeframe.M15)
    ):
        status, htf_reason = Availability.INCOMPLETE, "Two candles on a higher timeframe required."
    move = htf[-1].close - htf[-2].close if len(htf) >= 2 else None
    sign = ONE if command.direction is TradeDirection.LONG else -ONE
    alignment = ONE if move is not None and move * sign > 0 else ZERO
    if move == 0:
        alignment = Decimal("0.5")
    result[ComponentName.HTF] = component(
        ComponentName.HTF,
        availability=status,
        value="up"
        if move is not None and move > 0
        else "down"
        if move
        else "flat"
        if move is not None
        else None,
        unit="two_closed_4h_close_direction",
        contribution=alignment,
        source=candle_sources(htf[-2:]),
        timestamp=htf[-1].interval_end if htf else None,
        reason=htf_reason
        + " Two-close direction is an ordinal regime proxy, not a full trend model.",
        now=now,
    )
    flow = evidence.order_flow
    status, flow_reason = Availability.MISSING, "No canonical real-print flow payload."
    if flow is not None:
        try:
            require_order_flow(flow, identity=command.evidence_identity, evaluated_at=now)
            if flow.window_end != command.interval.end:
                raise ValueError("Flow window does not end at the canonical trigger close.")
            status, flow_reason = Availability.AVAILABLE, "Verified venue-bound real trade prints."
        except (ValueError, MarketContractError) as exc:
            status = (
                Availability.STALE
                if isinstance(exc, StaleEvidenceError)
                else (
                    flow.availability
                    if flow.availability is not Availability.AVAILABLE
                    else Availability.INCOMPLETE
                )
            )
            flow_reason = str(exc)
    source = (
        (EvidenceSource(contract="OrderFlowObservation", content_hash=flow.content_hash),)
        if flow
        else ()
    )
    imbalance = flow.windows[-1].buy_sell_imbalance_ratio if flow and flow.windows else None
    for name, value, unit, contribution, explanation in (
        (
            ComponentName.ORDER_FLOW,
            imbalance,
            "signed_quote_imbalance",
            (ONE + sign * imbalance) / 2 if imbalance is not None else None,
            "Directional quote imbalance maps [-1,1] to [0,1].",
        ),
        (
            ComponentName.CVD,
            flow.cvd_change if flow else None,
            flow.cvd_units if flow else "base_quantity",
            ONE
            if flow and flow.cvd_supportive_side == ("buy" if sign == ONE else "sell")
            else ZERO
            if flow and flow.cvd_supportive_side
            else None,
            "Current 5m delta sign only; bounded CVD resets at the 10m window start.",
        ),
    ):
        result[name] = component(
            name,
            availability=status,
            value=value,
            unit=unit,
            contribution=contribution,
            source=source,
            timestamp=flow.event_time if flow else None,
            now=now,
            reason=flow_reason + " " + explanation,
        )
    for name, metric in (
        (ComponentName.OI, DerivativeMetric.OPEN_INTEREST),
        (ComponentName.FUNDING, DerivativeMetric.FUNDING),
    ):
        matches = [d for d in evidence.market_intelligence if d.metric is metric]
        item = matches[0] if len(matches) == 1 else None
        status, reason = Availability.MISSING, "No unique canonical derivative observation."
        if item:
            try:
                require_derivative_observations(
                    matches,
                    required_metrics=(metric,),
                    identity=command.evidence_identity,
                    evaluated_at=now,
                )
                status, reason = (
                    Availability.AVAILABLE,
                    "Provider-reported measurement; context only.",
                )
            except (ValueError, MarketContractError) as exc:
                status = (
                    Availability.STALE
                    if isinstance(exc, StaleEvidenceError)
                    else (
                        item.availability
                        if item.availability is not Availability.AVAILABLE
                        else Availability.INCOMPLETE
                    )
                )
                reason = str(exc)
        elif len(matches) > 1:
            status = Availability.INCOMPLETE
        result[name] = component(
            name,
            availability=status,
            value=item.value if item else None,
            unit=item.units if item else "not_measured",
            now=now,
            source=(
                EvidenceSource(contract="DerivativeObservation", content_hash=item.content_hash),
            )
            if item
            else (),
            timestamp=item.event_time if item else None,
            reason=reason
            + " Absolute OI or settled funding is not normalized into directional strength.",
        )
    result[ComponentName.LIQUIDITY] = component(
        ComponentName.LIQUIDITY,
        now=now,
        availability=Availability.UNSUPPORTED,
        reason=(
            "No canonical depth/liquidity payload in this bundle; candle volume is not liquidity."
        ),
    )
    return result, candle

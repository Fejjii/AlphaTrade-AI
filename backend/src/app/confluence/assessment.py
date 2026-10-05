"""Pure assessment over canonical records. No writes, eligibility evaluation or execution."""

from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any, cast
from uuid import UUID

from app.confluence.arithmetic import research_arithmetic
from app.confluence.contracts import (
    AnalysisState,
    AssessmentCoverage,
    ComponentFact,
    ComponentName,
    ConfluenceAssessment,
    ConfluenceComponent,
    Coverage,
    DataQuality,
    EvidenceSource,
    HistoricalExpectancy,
    RiskEligibilityContext,
)
from app.confluence.market import candle_sources, candle_status, component, market_components
from app.confluence.policy import POLICY_V2_001, get_policy
from app.market_contracts.derivatives import DerivativeMetric
from app.market_contracts.enums import FreshnessState
from app.market_contracts.errors import MarketContractError
from app.market_contracts.hashing import with_content_hash
from app.market_contracts.observation import observation_from_derivative
from app.market_contracts.ohlcv import ClosedOhlcvSeries
from app.schemas.nested_continuation import EvidenceAvailability as Availability
from app.schemas.risk import DailyRiskState
from app.schemas.strategy_analytics import StrategyAnalyticsReport
from app.services.canonical_serialization import canonical_sha256
from app.signal_fusion.action_eligibility import PortfolioState
from app.signal_fusion.adapters import AssessmentCommand, evidence_window_from_assessment_command
from app.signal_fusion.assessment import SetupAssessment
from app.signal_fusion.eligibility import ActionEligibility
from app.signal_fusion.enums import EvidenceRole
from app.signal_fusion.first_slice_types import FirstSliceEvidenceBundle
from app.signal_fusion.order_flow_inputs import ORDER_FLOW_ROLES, require_bound_order_flow
from app.signal_fusion.strategy_evaluation_policy import ExecutableStrategyPolicy

ZERO, ONE = Decimal(0), Decimal(1)


def _coverage(items: tuple[ConfluenceComponent, ...]) -> Coverage:
    missing = tuple(c.key for c in items if c.availability is not Availability.AVAILABLE)
    return Coverage(
        available=len(items) - len(missing),
        total=len(items),
        missing_keys=missing,
        fraction=Decimal(len(items) - len(missing)) / len(items) if items else ONE,
    )


def _timed_status(at: datetime | None, now: datetime, max_age: int) -> Availability:
    if at is None:
        return Availability.INCOMPLETE
    if at.tzinfo is None or at.utcoffset() is None or at > now:
        return Availability.INCOMPLETE
    return Availability.STALE if (now - at).total_seconds() >= max_age else Availability.AVAILABLE


def _bind(
    executable: ExecutableStrategyPolicy, command: AssessmentCommand, setup: SetupAssessment
) -> None:
    window = evidence_window_from_assessment_command(command)
    fusion = executable.fusion_policy
    if (
        executable.adapter_id
        not in {"operational_nested_continuation/v1", "swing_failure_pattern/v1"}
        or executable.organization_id != command.organization_id
        or executable.strategy_version_id != command.strategy_version_id
        or fusion.organization_id != command.organization_id
        or fusion.strategy_version_id != command.strategy_version_id
        or fusion.executable_setup != command.executable_setup
        or fusion.policy_version != command.fusion_policy_version
        or fusion.finality_policy_version != command.finality_policy_version
        or fusion.freshness_policy_version != command.freshness_policy_version
        or fusion.correction_selection_policy != command.correction_selection_policy
        or fusion.required_roles != command.mandatory_evidence_roles
        or fusion.role_timeframes != command.role_timeframes
        or setup.organization_id != command.organization_id
        or setup.strategy_version_id != command.strategy_version_id
        or setup.executable_setup != command.executable_setup
        or setup.fusion_policy_version != command.fusion_policy_version
        or setup.evidence_window_hash != window.content_hash
        or setup.assessment_window != window.interval
        or tuple(dict.fromkeys(setup.observation_ids))
        != tuple(dict.fromkeys(o.observation_id for o in command.public_observations))
        or with_content_hash(setup).content_hash != setup.content_hash
        or with_content_hash(executable).content_hash != executable.content_hash
        or any(
            with_content_hash(o).content_hash != o.content_hash for o in command.public_observations
        )
    ):
        raise ValueError("Canonical setup, executable strategy and evidence lineage must match.")


def _required_roles(
    command: AssessmentCommand,
    evidence: FirstSliceEvidenceBundle,
    components: dict[ComponentName, ConfluenceComponent],
    candle: ConfluenceComponent,
    now: datetime,
) -> tuple[ConfluenceComponent, ...]:
    result = []
    mapping = {
        EvidenceRole.TRIGGER_OHLCV: candle,
        EvidenceRole.STRUCTURE: candle,
        EvidenceRole.CONTEXT_OHLCV: components[ComponentName.HTF],
        EvidenceRole.VOLUME: components[ComponentName.VOLUME],
        EvidenceRole.CVD_5M: components[ComponentName.CVD],
        EvidenceRole.ORDER_FLOW_5M: components[ComponentName.ORDER_FLOW],
        EvidenceRole.OPEN_INTEREST: components[ComponentName.OI],
        EvidenceRole.FUNDING: components[ComponentName.FUNDING],
    }
    for role in command.mandatory_evidence_roles:
        item = mapping.get(role) or component(
            role.value,
            now=now,
            availability=Availability.UNSUPPORTED,
            reason="Required role has no confluence payload adapter; analysis fails closed.",
        )
        if item.availability is Availability.AVAILABLE:
            try:
                if role in ORDER_FLOW_ROLES:
                    require_bound_order_flow(
                        evidence.order_flow,
                        command=command,
                        required_roles=(role,),
                        evaluated_at=now,
                        trigger_end=command.interval.end,
                    )
                if role in {EvidenceRole.OPEN_INTEREST, EvidenceRole.FUNDING}:
                    metric = DerivativeMetric(role.value)
                    derivative = next(d for d in evidence.market_intelligence if d.metric is metric)
                    selected = [
                        o
                        for o, r in zip(
                            command.public_observations, command.selected_roles, strict=True
                        )
                        if r is role
                    ]
                    if selected != [observation_from_derivative(derivative)]:
                        raise ValueError("Required derivative payload not selected by the command.")
                if role is EvidenceRole.CONTEXT_OHLCV:
                    payloads = {
                        o.payload_content_hash
                        for o, r in zip(
                            command.public_observations, command.selected_roles, strict=True
                        )
                        if r is role
                    }
                    hashes = {b.content_hash for b in evidence.bars_4h}
                    if not (
                        hashes <= payloads
                        or canonical_sha256(cast(Any, [b.content_hash for b in evidence.bars_4h]))
                        in payloads
                    ):
                        raise ValueError("Required HTF payload not selected by the command.")
            except (ValueError, MarketContractError) as exc:
                item = item.model_copy(
                    update={
                        "availability": Availability.INCOMPLETE,
                        "normalized_contribution": None,
                        "freshness": FreshnessState.UNKNOWN,
                        "reason": str(exc),
                    }
                )
        result.append(
            item.model_copy(
                update={
                    "key": f"required_role:{role.value}",
                    "weight": ZERO,
                    "normalized_contribution": None,
                    "passed": item.availability is Availability.AVAILABLE,
                }
            )
        )
    return tuple(result)


@research_arithmetic
def assess_confluence(
    *,
    executable: ExecutableStrategyPolicy,
    command: AssessmentCommand,
    setup: SetupAssessment,
    evidence: FirstSliceEvidenceBundle,
    user_id: UUID,
    account_id: UUID,
    assessed_at: datetime,
    policy_version: str = POLICY_V2_001.version,
    portfolio: PortfolioState | None = None,
    portfolio_observed_at: datetime | None = None,
    daily_risk: DailyRiskState | None = None,
    analytics: StrategyAnalyticsReport | None = None,
    eligibility: ActionEligibility | None = None,
    btc_context: ClosedOhlcvSeries | None = None,
) -> ConfluenceAssessment:
    """No I/O. Explicit timestamps make the same input reproducible in offline research.

    The caller supplies authorized canonical records. Untimestamped PortfolioState
    requires its actual snapshot time; the analysis clock never substitutes for it.
    No detectors run and no canonical setup, Candidate or ActionEligibility changes.
    """
    if assessed_at.tzinfo is None or assessed_at.utcoffset() is None:
        raise ValueError("Confluence assessment requires an aware explicit clock.")
    now, policy = assessed_at, get_policy(policy_version)
    _bind(executable, command, setup)
    for record in (portfolio, daily_risk, analytics, eligibility):
        if record is None:
            continue
        if record.organization_id != setup.organization_id:
            raise ValueError("Cross-organization context is forbidden.")
        if hasattr(record, "user_id") and record.user_id != user_id:
            raise ValueError("Cross-user context is forbidden.")
        if hasattr(record, "account_id") and record.account_id != account_id:
            raise ValueError("Cross-account context is forbidden.")
    if eligibility and (
        eligibility.assessment_id != setup.assessment_id
        or with_content_hash(eligibility).content_hash != eligibility.content_hash
    ):
        raise ValueError("Eligibility must reference the exact canonical setup assessment.")
    if analytics and (
        analytics.filters.strategy_version_id != setup.strategy_version_id
        or analytics.filters.strategy_id not in {None, executable.strategy_id}
    ):
        raise ValueError("Historical expectancy requires the exact strategy-version cohort.")

    components, candle = market_components(command, evidence, policy, now)
    source = (
        EvidenceSource(
            contract="SetupAssessment",
            record_id=str(setup.assessment_id),
            content_hash=setup.content_hash,
        ),
    )
    current = setup.assessed_at <= now < setup.valid_until
    status = (
        Availability.AVAILABLE
        if current
        else Availability.STALE
        if now >= setup.valid_until
        else Availability.INCOMPLETE
    )
    components[ComponentName.PATTERN] = component(
        ComponentName.PATTERN,
        now=now,
        availability=status,
        value=setup.state.value,
        unit="canonical_setup_state",
        contribution=ONE if setup.state.value == "confirmed_setup" else ZERO,
        source=source,
        timestamp=setup.assessed_at,
        reason=(
            "Canonical confirmation contributes one; all other states zero. "
            "Detector identity is preserved."
        ),
    )
    hard = [
        component(
            "canonical_assessment_current",
            now=now,
            availability=status,
            value=current,
            unit="validity_interval",
            source=source,
            timestamp=setup.assessed_at,
            reason="Canonical assessment must be causal and unexpired.",
        ).model_copy(update={"passed": current})
    ]
    hard.append(candle.model_copy(update={"passed": candle.availability is Availability.AVAILABLE}))
    causal_observations = all(
        o.observed_at <= setup.assessed_at and o.source_time <= now and o.event_time <= now
        for o in command.public_observations
    )
    hard.append(
        component(
            "canonical_observations_causal",
            now=now,
            availability=Availability.AVAILABLE if causal_observations else Availability.INCOMPLETE,
            value=causal_observations,
            unit="causal_public_observations",
            source=source,
            timestamp=setup.assessed_at,
            reason="Selected public observations must be available at the setup decision time.",
        ).model_copy(update={"passed": causal_observations})
    )
    hard.extend(_required_roles(command, evidence, components, candle, now))
    hard.extend(
        component(
            f"canonical_rule:{rule.rule_id}",
            now=now,
            availability=status,
            value=rule.passed,
            unit="canonical_requirement",
            source=source,
            timestamp=setup.assessed_at,
            reason=rule.reason_code
            or "Canonical requirement passed; independent of optional weights.",
        ).model_copy(update={"passed": rule.passed})
        for rule in setup.rule_results
    )
    if not setup.rule_results:
        hard.append(
            component(
                "canonical_rules_present", now=now, reason="Canonical hard checks are missing."
            ).model_copy(update={"passed": False})
        )

    exposure_status = (
        _timed_status(portfolio_observed_at, now, policy.account_context_max_age_seconds)
        if portfolio
        else Availability.MISSING
    )
    components[ComponentName.EXPOSURE] = component(
        ComponentName.EXPOSURE,
        now=now,
        availability=exposure_status,
        value=portfolio.open_exposure_notional if portfolio else None,
        unit="account_notional",
        source=(
            EvidenceSource(
                contract="PortfolioState",
                record_id=str(account_id),
                content_hash=canonical_sha256(portfolio),
            ),
        )
        if portfolio
        else (),
        timestamp=portfolio_observed_at if exposure_status is not Availability.INCOMPLETE else None,
        reason=(
            "Canonical existing exposure; not a capacity verdict. Actual "
            "snapshot timestamp required."
        ),
    )
    if portfolio:
        components[ComponentName.EXPOSURE] = components[ComponentName.EXPOSURE].model_copy(
            update={"facts": (ComponentFact(key="account_equity", value=portfolio.account_equity),)}
        )
    risk_status = (
        _timed_status(daily_risk.updated_at, now, policy.account_context_max_age_seconds)
        if daily_risk
        else Availability.MISSING
    )
    components[ComponentName.DAILY_RISK] = component(
        ComponentName.DAILY_RISK,
        now=now,
        availability=risk_status,
        value=daily_risk.locked if daily_risk else None,
        unit="canonical_daily_locked",
        source=(
            EvidenceSource(
                contract="DailyRiskState",
                record_id=f"{user_id}:{daily_risk.day}",
                content_hash=canonical_sha256(
                    {**daily_risk.model_dump(), "day": daily_risk.day.isoformat()}
                ),
            ),
        )
        if daily_risk
        else (),
        timestamp=daily_risk.updated_at
        if daily_risk and risk_status is not Availability.INCOMPLETE
        else None,
        reason=(
            "Recorded daily risk lock only; existing Risk and "
            "ActionEligibility remain authoritative."
        ),
    )
    if daily_risk:
        components[ComponentName.DAILY_RISK] = components[ComponentName.DAILY_RISK].model_copy(
            update={
                "facts": tuple(
                    ComponentFact(key=key, value=value)
                    for key, value in {
                        "day": daily_risk.day.isoformat(),
                        "realized_pnl": daily_risk.realized_pnl,
                        "unrealized_pnl": daily_risk.unrealized_pnl,
                        "daily_loss_limit": daily_risk.daily_loss_limit,
                        "daily_target": daily_risk.daily_target,
                        "trade_count": daily_risk.trade_count,
                        "max_trades_per_day": daily_risk.max_trades_per_day,
                    }.items()
                )
            }
        )
    btc_status, btc_reason = Availability.MISSING, "No measured canonical BTC context supplied."
    btc_bars = tuple(btc_context.bars) if btc_context else ()
    if btc_context:
        identity = btc_context.identity
        if (
            identity.instrument.provider_symbol != "BTCUSDT"
            or identity.venue != command.evidence_identity.venue
            or identity.market_type != command.evidence_identity.market_type
        ):
            raise ValueError("BTC context must be measured BTCUSDT on the same venue and market.")
        btc_status, btc_reason = candle_status(btc_bars, identity, now)
        if (
            btc_context.evaluated_at > now
            or with_content_hash(btc_context).content_hash != btc_context.content_hash
        ):
            btc_status, btc_reason = (
                Availability.INCOMPLETE,
                "BTC context has future time or invalid hash.",
            )
        if len(btc_bars) < 2:
            btc_status, btc_reason = Availability.INCOMPLETE, "Two closed BTC candles required."
    components[ComponentName.BTC] = component(
        ComponentName.BTC,
        now=now,
        availability=btc_status,
        value=btc_bars[-1].close / btc_bars[-2].close - ONE if len(btc_bars) >= 2 else None,
        unit="two_close_return",
        source=candle_sources(btc_bars[-2:]),
        timestamp=btc_bars[-1].interval_end if btc_bars else None,
        reason=btc_reason + " Context only; no inferred correlation or causality.",
    )
    history_status = (
        _timed_status(analytics.generated_at, now, policy.history_max_age_seconds)
        if analytics
        else Availability.MISSING
    )
    metrics = analytics.overall if analytics else None
    if history_status is Availability.AVAILABLE and (
        metrics is None or metrics.expectancy is None or metrics.pnl_sample_count == 0
    ):
        history_status = Availability.INCOMPLETE
    expectancy = component(
        ComponentName.EXPECTANCY,
        now=now,
        availability=history_status,
        value=metrics.expectancy if metrics else None,
        unit="recorded_net_pnl_per_trade",
        source=(
            EvidenceSource(
                contract="StrategyAnalyticsReport", record_id=str(setup.strategy_version_id)
            ),
        )
        if analytics
        else (),
        timestamp=analytics.generated_at
        if analytics and history_status is not Availability.INCOMPLETE
        else None,
        reason=(
            "Measured canonical version cohort; no scoring weight or "
            "prediction. Report truncation and sample size remain explicit."
        ),
    )
    history = HistoricalExpectancy(
        component=expectancy,
        sample_count=metrics.pnl_sample_count if metrics else 0,
        min_sample_size=analytics.min_sample_size if analytics else policy.history_min_sample_size,
        insufficient_history=(
            not metrics or not analytics or metrics.pnl_sample_count < analytics.min_sample_size
        ),
        truncated=analytics.truncated if analytics else False,
        cohort_filters=tuple(
            ComponentFact(key=key, value=value)
            for key, value in analytics.filters.model_dump(mode="json").items()
        )
        if analytics
        else (),
    )
    risk_availability = Availability.MISSING
    if eligibility:
        risk_availability = (
            Availability.AVAILABLE
            if eligibility.checked_at <= now < eligibility.valid_until
            else Availability.STALE
            if now >= eligibility.valid_until
            else Availability.INCOMPLETE
        )
    risk = RiskEligibilityContext(
        availability=risk_availability,
        canonical_record=eligibility,
        reason=(
            "Recorded canonical decision only; no eligibility is computed or granted by confluence."
        ),
    )
    weights = {w.component: w.weight for w in policy.weights if w.weight > 0}
    quality = tuple(
        components[name].model_copy(update={"weight": weight}) for name, weight in weights.items()
    )
    weighted = {c.key: c for c in quality}
    optional = tuple(
        weighted.get(name, components[name])
        for name in (
            ComponentName.HTF,
            ComponentName.VOLUME,
            ComponentName.ORDER_FLOW,
            ComponentName.CVD,
            ComponentName.OI,
            ComponentName.FUNDING,
            ComponentName.VOLATILITY,
            ComponentName.LIQUIDITY,
            ComponentName.BTC,
        )
    )
    context = tuple(
        components[name]
        for name in ComponentName
        if name not in weights and name is not ComponentName.EXPECTANCY
    )
    hard_items = tuple(hard)
    state = AnalysisState.READY
    if any(c.availability is not Availability.AVAILABLE for c in hard):
        state = AnalysisState.REQUIRED_DATA_UNAVAILABLE
    elif any(c.passed is not True for c in hard):
        state = AnalysisState.HARD_REQUIREMENTS_FAILED
    scored = [
        c
        for c in quality
        if c.availability is Availability.AVAILABLE and c.normalized_contribution is not None
    ]
    total_weight = sum(weights.values(), ZERO)
    available_weight = sum((c.weight for c in scored), ZERO)
    score = None
    if state is AnalysisState.READY and available_weight:
        score = (
            sum((c.weight * (c.normalized_contribution or ZERO) for c in scored), ZERO)
            / available_weight
            * 100
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
    coverage_fraction = available_weight / total_weight
    all_components = (*quality, *context, expectancy)
    payload = ConfluenceAssessment(
        organization_id=setup.organization_id,
        user_id=user_id,
        account_id=account_id,
        setup=setup,
        evidence_identity=command.evidence_identity,
        direction=command.direction,
        detector_kind=executable.adapter_id,
        policy_version=policy.version,
        policy_content_hash=policy.content_hash,
        state=state,
        hard_requirements=hard_items,
        optional_confluence=optional,
        quality_components=quality,
        context_components=context,
        quality_score=score,
        quality_band="unavailable"
        if score is None
        else "at_or_above_reference"
        if score >= policy.quality_reference_points
        else "below_reference",
        coverage=AssessmentCoverage(
            required=_coverage(hard_items),
            optional=_coverage(optional),
            context=_coverage(context),
            scored_weight_available=available_weight,
            scored_weight_total=total_weight,
            scored_weight_fraction=coverage_fraction,
        ),
        historical_expectancy=history,
        risk_eligibility=risk,
        data_quality=DataQuality(
            unavailable_keys=tuple(
                c.key for c in all_components if c.availability is not Availability.AVAILABLE
            ),
            stale_keys=tuple(c.key for c in all_components if c.availability is Availability.STALE),
            insufficient_score_coverage=coverage_fraction < policy.minimum_scored_coverage,
        ),
        assessed_at=now,
        content_hash="0" * 64,
    )
    return payload.model_copy(
        update={"content_hash": canonical_sha256(payload.model_dump(exclude={"content_hash"}))}
    )

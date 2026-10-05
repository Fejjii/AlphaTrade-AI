"""Descriptive offline filter comparisons over linked canonical journal outcomes."""

from collections.abc import Sequence
from decimal import Decimal
from typing import Literal

from pydantic import Field

from app.confluence.arithmetic import research_arithmetic
from app.confluence.contracts import AnalysisState, ComponentName, ConfluenceAssessment
from app.market_contracts.models import CanonicalDecimal, CanonicalModel
from app.schemas.common import JournalTradeStatus
from app.schemas.journal_trades import JournalTradeRead
from app.schemas.nested_continuation import EvidenceAvailability
from app.services.canonical_serialization import canonical_sha256


class ResearchCase(CanonicalModel):
    assessment: ConfluenceAssessment
    outcome: JournalTradeRead


class CohortSummary(CanonicalModel):
    trade_count: int = Field(ge=0)
    net_pnl_total: CanonicalDecimal | None
    expectancy: CanonicalDecimal | None
    insufficient_history: bool


class FilterComparison(CanonicalModel):
    contract_version: Literal["confluence-filter-comparison/v1"] = "confluence-filter-comparison/v1"
    descriptive_only: Literal[True] = True
    causal_claim: Literal[False] = False
    component: ComponentName
    filter_version: str
    filter_content_hash: str
    threshold: CanonicalDecimal
    units: str
    policy_content_hash: str | None
    baseline: CohortSummary
    with_filter: CohortSummary
    without_filter: CohortSummary
    filter_measured_count: int
    missing_filter_count: int
    excluded_outcome_count: int
    expectancy_difference: CanonicalDecimal | None
    limitations: tuple[str, ...] = (
        "Descriptive association only; no randomized treatment or causal inference.",
        "Filtered trades are a subset of baseline, not an independent control cohort.",
        "Selection, missing evidence, market regime and execution costs may confound differences.",
        "Only recorded closed canonical net PnL is used; costs are not invented or deducted twice.",
        "OI is an absolute provider measurement; its threshold does not "
        "imply bullish or bearish flow.",
    )


def _summary(values: list[Decimal], minimum: int) -> CohortSummary:
    total = sum(values, Decimal(0)) if values else None
    return CohortSummary(
        trade_count=len(values),
        net_pnl_total=total,
        expectancy=total / len(values) if total is not None else None,
        insufficient_history=len(values) < minimum,
    )


@research_arithmetic
def _compare(
    cases: Sequence[ResearchCase],
    *,
    name: ComponentName,
    threshold: Decimal,
    units: str,
    filter_version: str,
    minimum: int,
) -> FilterComparison:
    if not threshold.is_finite() or minimum < 1 or not filter_version.strip() or not units.strip():
        raise ValueError(
            "Finite threshold, explicit version/units and positive sample minimum required."
        )
    baseline: list[Decimal] = []
    included: list[Decimal] = []
    rejected: list[Decimal] = []
    seen = set()
    cohort = None
    measured = missing = excluded = 0
    policy_hash = None
    for case in cases:
        assessment, trade = case.assessment, case.outcome
        expected_hash = canonical_sha256(assessment.model_dump(exclude={"content_hash"}))
        if expected_hash != assessment.content_hash:
            raise ValueError("Research assessment content hash mismatch.")
        if trade.id in seen:
            raise ValueError("Duplicate canonical journal outcome would bias the comparison.")
        seen.add(trade.id)
        key = (
            assessment.organization_id,
            assessment.user_id,
            assessment.account_id,
            assessment.setup.strategy_version_id,
            assessment.setup.executable_setup,
            assessment.detector_kind,
            assessment.evidence_identity,
            assessment.direction,
            assessment.policy_content_hash,
            trade.source,
            trade.exchange,
        )
        if cohort is not None and cohort != key:
            raise ValueError(
                "Comparison requires one tenant, account, strategy, market, "
                "direction and policy cohort."
            )
        cohort, policy_hash = key, assessment.policy_content_hash
        if (
            trade.organization_id != assessment.organization_id
            or trade.user_id != assessment.user_id
            or trade.strategy_version_id != assessment.setup.strategy_version_id
            or trade.symbol != assessment.evidence_identity.instrument.provider_symbol
            or assessment.evidence_identity.timeframe is None
            or trade.timeframe != assessment.evidence_identity.timeframe.value
            or trade.direction != assessment.direction
        ):
            raise ValueError("Journal outcome does not match its canonical assessment cohort.")
        if (
            trade.status is not JournalTradeStatus.CLOSED
            or trade.net_pnl is None
            or not trade.net_pnl.is_finite()
            or trade.entry_time is None
            or trade.exit_time is None
            or trade.entry_time.tzinfo is None
            or trade.exit_time.tzinfo is None
            or not assessment.assessed_at <= trade.entry_time < trade.exit_time
            or assessment.state is not AnalysisState.READY
        ):
            excluded += 1
            continue
        baseline.append(trade.net_pnl)
        components = (*assessment.quality_components, *assessment.context_components)
        component = next((c for c in components if c.key == name), None)
        value = (
            None
            if component is None
            else (
                component.value if name is ComponentName.OI else component.normalized_contribution
            )
        )
        if (
            component is None
            or component.availability is not EvidenceAvailability.AVAILABLE
            or not isinstance(value, Decimal)
        ):
            missing += 1
            continue
        if name is ComponentName.OI and component.unit != units:
            raise ValueError("Open-interest comparison cannot mix quantity units.")
        measured += 1
        (included if value >= threshold else rejected).append(trade.net_pnl)
    base, filtered = _summary(baseline, minimum), _summary(included, minimum)
    fingerprint = canonical_sha256(
        {
            "component": name,
            "threshold": threshold,
            "units": units,
            "filter_version": filter_version,
            "minimum_sample_size": minimum,
            "operator": "greater_than_or_equal",
            "outcome_basis": "canonical_closed_net_pnl",
            "arithmetic_version": "decimal-28-half-even/v1",
        }
    )
    return FilterComparison(
        component=name,
        filter_version=filter_version,
        filter_content_hash=fingerprint,
        threshold=threshold,
        units=units,
        policy_content_hash=policy_hash,
        baseline=base,
        with_filter=filtered,
        without_filter=_summary(rejected, minimum),
        filter_measured_count=measured,
        missing_filter_count=missing,
        excluded_outcome_count=excluded,
        expectancy_difference=filtered.expectancy - base.expectancy
        if filtered.expectancy is not None and base.expectancy is not None
        else None,
    )


def compare_with_order_flow_filter(cases: Sequence[ResearchCase]) -> FilterComparison:
    return _compare(
        cases,
        name=ComponentName.ORDER_FLOW,
        threshold=Decimal("0.5"),
        units="normalized_directional_imbalance",
        filter_version="order-flow-nonopposing/v1",
        minimum=20,
    )


def compare_with_cvd_filter(cases: Sequence[ResearchCase]) -> FilterComparison:
    return _compare(
        cases,
        name=ComponentName.CVD,
        threshold=Decimal(1),
        units="normalized_directional_delta_sign",
        filter_version="cvd-supportive-sign/v1",
        minimum=20,
    )


def compare_with_oi_filter(
    cases: Sequence[ResearchCase],
    *,
    minimum_open_interest: Decimal,
    units: str,
    filter_version: str,
) -> FilterComparison:
    if minimum_open_interest < 0:
        raise ValueError("OI threshold cannot be negative.")
    return _compare(
        cases,
        name=ComponentName.OI,
        threshold=minimum_open_interest,
        units=units,
        filter_version=filter_version,
        minimum=20,
    )

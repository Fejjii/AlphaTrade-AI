"""Deterministic gross planned 1R floor; historical semantic models stay readable."""

from dataclasses import dataclass
from decimal import Decimal, localcontext
from fractions import Fraction

from pydantic import ValidationError

from app.schemas.trade_plan import ContractType, EntrySide, TradePlanExecutionTerms

POLICY_VERSION = "planned-gross-weighted-rr/v1"
MINIMUM_REWARD_RISK = Fraction(1)
MANUAL_CONNECTIVITY_RR_POLICY = "manual-demo-connectivity-no-minimum-rr"


class PlannedRewardRiskError(ValueError):
    def __init__(self, message: str, *, reason: str = "planned_reward_risk_invalid") -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True)
class PlannedRewardRisk:
    entry: Decimal
    reward_distance: Decimal
    risk_distance: Decimal
    ratio: Decimal
    meets_minimum: bool


def measure_planned_reward_risk(terms: TradePlanExecutionTerms) -> PlannedRewardRisk:
    """Use the worst permitted entry, full-position risk and allocation-weighted reward.

    Unpriced runners contribute zero reward. This is gross price-distance R,
    excluding fee/funding/slippage amounts; existing maximum-loss accounting
    continues to reserve those costs. This ratio is not a net outcome guarantee.
    Exact rational arithmetic decides the boundary, independent of Decimal context.
    """
    try:
        terms = TradePlanExecutionTerms.model_validate(
            terms.model_dump(include=set(TradePlanExecutionTerms.model_fields))
        )
    except ValidationError as exc:
        raise PlannedRewardRiskError("Invalid planned reward/risk terms.") from exc
    if terms.instrument_rules.contract_type is not ContractType.LINEAR:
        raise PlannedRewardRiskError("Planned reward/risk supports linear instruments only.")
    exits = terms.risk_and_exits
    unit = terms.entry_zone.price_unit
    if unit != terms.instrument_rules.quote_currency or any(
        amount.unit != unit for amount in (exits.stop, *(target.price for target in exits.targets))
    ):
        raise PlannedRewardRiskError(
            "Entry, stop and target price units must match the quote currency."
        )
    long = terms.side is EntrySide.BUY
    entry = terms.entry_zone.upper if long else terms.entry_zone.lower
    values = [
        terms.entry_zone.lower,
        terms.entry_zone.upper,
        exits.stop.value,
        exits.runner.remaining_quantity_fraction,
    ]
    values.extend(
        value
        for target in exits.targets
        for value in (target.price.value, target.quantity_fraction)
    )
    if any(
        len(value.as_tuple().digits) > 80 or abs(int(value.as_tuple().exponent)) > 80
        for value in values
    ):
        raise PlannedRewardRiskError(
            "Planned reward/risk decimal precision exceeds its bounded budget."
        )
    sign = 1 if long else -1
    nearest_entry = terms.entry_zone.lower if long else terms.entry_zone.upper
    if sign * (Fraction(nearest_entry) - Fraction(exits.stop.value)) <= 0:
        raise PlannedRewardRiskError(
            "The stop must be beyond the entire entry zone in the loss direction."
        )
    risk = sign * (Fraction(entry) - Fraction(exits.stop.value))
    if risk <= 0:
        raise PlannedRewardRiskError(
            "The stop must be beyond the entire entry zone in the loss direction."
        )
    reward = Fraction(0)
    allocated = Fraction(exits.runner.remaining_quantity_fraction)
    for target in exits.targets:
        distance = sign * (Fraction(target.price.value) - Fraction(entry))
        if distance <= 0:
            raise PlannedRewardRiskError(
                "Every target must be beyond the entry zone in the profit direction."
            )
        fraction = Fraction(target.quantity_fraction)
        allocated += fraction
        reward += distance * fraction
    if allocated != 1:
        raise PlannedRewardRiskError(
            "Targets plus any reserved runner must allocate exactly the whole position."
        )
    if exits.runner.enabled and exits.runner.remaining_quantity_fraction <= 0:
        raise PlannedRewardRiskError("An enabled runner must reserve a positive allocation.")
    with localcontext() as context:
        context.prec = 40
        ratio = (
            Decimal(reward.numerator)
            / Decimal(reward.denominator)
            / (Decimal(risk.numerator) / Decimal(risk.denominator))
        )
        result = PlannedRewardRisk(
            entry=entry,
            reward_distance=Decimal(reward.numerator) / Decimal(reward.denominator),
            risk_distance=Decimal(risk.numerator) / Decimal(risk.denominator),
            ratio=ratio,
            meets_minimum=reward >= risk * MINIMUM_REWARD_RISK,
        )
    return result


def planned_reward_risk(terms: TradePlanExecutionTerms) -> PlannedRewardRisk:
    """Enforce the current entry policy without changing old records or target prices."""
    result = measure_planned_reward_risk(terms)
    if not result.meets_minimum:
        raise PlannedRewardRiskError(
            "Planned allocation-weighted gross reward/risk must be at least 1:1; "
            "keep the original targets and reject this entry.",
            reason="planned_reward_risk_below_minimum",
        )
    return result


def execution_reward_risk(terms: TradePlanExecutionTerms) -> PlannedRewardRisk:
    """Only a hash-bound manual demo connectivity policy may omit the strategy 1R floor.

    Full semantic validation still enforces demo venue, no strategy/Candidate lineage,
    market-only entry and one full-position target. Geometry/allocation remain mandatory.
    Legacy manual plans without this explicit calculation policy retain the 1R floor.
    """
    markers = [item for item in terms.calculation_inputs if item.name == "manual_connectivity_rr"]
    if (
        terms.schema_version == "ManualDemoTradePlanV1"
        and terms.execution_policy_version == "manual-blofin-demo/v1"
        and len(markers) == 1
        and markers[0].formula_id == MANUAL_CONNECTIVITY_RR_POLICY
        and markers[0].formula_version == "1"
        and markers[0].unit == "POLICY"
        and markers[0].input_value == markers[0].result_value == 1
    ):
        return measure_planned_reward_risk(terms)
    return planned_reward_risk(terms)

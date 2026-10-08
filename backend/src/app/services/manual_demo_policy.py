"""Manual connectivity limits use only fresh, pinned BloFin demo evidence.

The provider proves the account flat (including pending orders and protection).
Unresolved demo history remains held separately. Internal paper accounting is
never an authority for this policy, but its records are retained unchanged.
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from app.core.errors import TradingPolicyError
from app.schemas.trade_plan import TradePlanRevisionSemantic
from app.services.planned_reward_risk import PlannedRewardRiskError, execution_reward_risk

if TYPE_CHECKING:
    from app.providers.exchange.governed_blofin import DemoVenueSnapshot

MAXIMUM_TEST_NOTIONAL_FRACTION = Decimal("0.05")
MAXIMUM_TEST_LOSS_FRACTION = Decimal("0.01")


def refuse(reason: str, message: str, *, category: str = "manual_demo_limits") -> None:
    raise TradingPolicyError(message, details={"reason": reason, "category": category})


def validate_manual_demo(
    plan: TradePlanRevisionSemantic,
    snapshot: "DemoVenueSnapshot",
    *,
    now: datetime,
    reserved_notional: Decimal = Decimal("0"),
    reserved_loss: Decimal = Decimal("0"),
) -> None:
    """Same policy in preview, confirmation, locked claim and final preflight."""
    if plan.schema_version != "ManualDemoTradePlanV1":
        refuse("manual_demo_plan_required", "A canonical manual demo plan is required.")
    try:
        execution_reward_risk(plan)
    except PlannedRewardRiskError as exc:
        refuse(exc.reason, f"Manual demo geometry: {exc}", category="manual_demo_geometry")
    if not 0 <= (now - snapshot.account_observed_at).total_seconds() < 10:
        refuse(
            "manual_demo_account_state_stale",
            "Demo account evidence is stale or future dated. Refresh the demo account and preview.",
        )
    if not 0 <= (now - snapshot.observed_at).total_seconds() < 10:
        refuse("manual_demo_quote_stale", "Demo quote is stale. Refresh the preview.")
    rules = plan.instrument_rules
    if snapshot.instrument != plan.execution_instrument or snapshot.book.side is not plan.side:
        refuse("manual_demo_evidence_mismatch", "Demo account instrument/side evidence mismatch.")
    if (snapshot.tick, snapshot.lot, snapshot.minimum, snapshot.multiplier) != (
        rules.tick_size,
        rules.lot_size,
        rules.minimum_quantity,
        rules.contract_multiplier,
    ):
        refuse(
            "manual_demo_instrument_changed",
            "Exchange instrument constraints changed. Refresh the preview.",
            category="exchange_constraints",
        )
    worst = snapshot.book.worst_price(
        plan.quantity.value, lot=snapshot.lot, minimum=snapshot.minimum, maximum=snapshot.maximum
    )
    if any(
        not plan.entry_zone.lower <= p <= plan.entry_zone.upper for p in (snapshot.price, worst)
    ):
        refuse("manual_demo_entry_changed", "Executable entry moved outside the confirmed range.")
    equity, available = snapshot.equity, snapshot.available
    if any(not v.is_finite() or v <= 0 for v in (equity, available)):
        refuse(
            "manual_demo_account_state_unknown",
            "Demo USDT equity or available funds are unknown. Verify the selected demo account.",
        )
    notional = plan.quantity.value * rules.contract_multiplier * plan.entry_zone.upper
    basis = min(equity, available)
    if notional + plan.risk_and_exits.fee_allowance.value + reserved_notional > available:
        refuse(
            "manual_demo_available_funds",
            "Demo available funds cannot cover this test and reservations.",
        )
    if notional + reserved_notional > basis * MAXIMUM_TEST_NOTIONAL_FRACTION:
        refuse(
            "manual_demo_notional_limit",
            "Manual demo limit: test plus demo reservations exceeds 5% of available demo equity.",
        )
    if plan.risk_and_exits.maximum_loss.value + reserved_loss > basis * MAXIMUM_TEST_LOSS_FRACTION:
        refuse(
            "manual_demo_per_trade_risk_limit",
            "Manual demo limit: planned loss plus demo reservations exceeds "
            "1% of available demo equity.",
        )

"""Build manual demo semantics from actual preflight reads and explicit prices."""

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from app.core.errors import TradingPolicyError
from app.providers.exchange.governed_blofin import DemoVenueSnapshot
from app.schemas.manual_demo import ManualDemoPreviewRequest
from app.schemas.trade_plan import TradePlanRevisionSemantic
from app.services.planned_reward_risk import MANUAL_CONNECTIVITY_RR_POLICY, execution_reward_risk

MANUAL_DEMO_POLICY = "manual-blofin-demo/v1"
MANUAL_DEMO_ORIGIN = "manual_demo_test"


def build_manual_plan(
    request: ManualDemoPreviewRequest,
    snapshot: DemoVenueSnapshot,
    *,
    organization_id: UUID,
    user_id: UUID,
    account_id: UUID,
    now: datetime,
) -> TradePlanRevisionSemantic:
    """No strategy, setup or Candidate identity is created or claimed."""
    if not 0 <= (now - snapshot.observed_at).total_seconds() < 10:
        raise TradingPolicyError("Demo preview quote is stale or future dated.")
    quantity = request.quantity
    if snapshot.book.side is not request.side:
        raise TradingPolicyError("Demo quote side does not match the requested entry.")
    snapshot.book.worst_price(
        quantity, lot=snapshot.lot, minimum=snapshot.minimum, maximum=snapshot.maximum
    )
    if (
        len(quantity.as_tuple().digits) > 28
        or abs(int(quantity.as_tuple().exponent)) > 28
        or quantity < snapshot.minimum
        or quantity > snapshot.maximum
        or quantity % snapshot.lot != 0
        or any(price % snapshot.tick != 0 for price in (request.stop, request.target))
    ):
        raise TradingPolicyError("Exact venue quantity/price increments and limits are required.")
    base = quantity * snapshot.multiplier
    lower, upper = snapshot.price * Decimal("0.999"), snapshot.price * Decimal("1.001")
    worst = upper if request.side.value == "BUY" else lower
    notional = base * upper
    if base * lower < Decimal("5"):
        raise TradingPolicyError("Demo entry notional is below 5 USDT.")
    gross_loss = base * abs(worst - request.stop)
    fee = notional * Decimal("0.001")
    slippage = notional * Decimal("0.001")

    def amount(value: Decimal | str) -> dict[str, Decimal | str]:
        return {"value": value, "unit": "USDT"}

    derivation = {"formula_id": "explicit-owner-manual-demo", "formula_version": "1"}
    plan = TradePlanRevisionSemantic.model_validate(
        {
            "schema_version": "ManualDemoTradePlanV1",
            "plan_id": uuid4(),
            "revision_id": uuid4(),
            "organization_id": organization_id,
            "user_id": user_id,
            "account_id": account_id,
            "exchange_account_id": None,
            "strategy_version_id": None,
            "setup_definition_id": None,
            "candidate_id": None,
            "permission_attestation_id": uuid4(),
            "permission_attestation_version": "verified-demo-read-trade/v1",
            "evidence_ids": [uuid4()],
            "evidence_venue": "BLOFIN_DEMO",
            "evidence_market": "PERPETUAL",
            "evidence_instrument": snapshot.instrument,
            "evidence_observed_at": snapshot.observed_at,
            "evidence_freshness_seconds": 10,
            "evidence_is_live": True,
            "evidence_fallback_used": False,
            "evidence_sequence_complete": True,
            "evidence_final": True,
            "execution_venue": "BLOFIN_DEMO",
            "execution_market": "PERPETUAL",
            "execution_instrument": snapshot.instrument,
            "timeframe": "manual",
            "instrument_mapping_version": "blofin-linear-usdt/v1",
            "side": request.side,
            "quantity": {"value": quantity, "unit": "CONTRACTS"},
            "quantity_unit": "CONTRACTS",
            "order_type": "MARKET",
            "time_in_force": "IOC",
            "limit_price": None,
            "market_marker": True,
            "entry_zone": {"lower": lower, "upper": upper, "price_unit": "USDT"},
            "entry_zone_derivation": derivation,
            "slippage_policy": {
                "policy_id": "blofin-demo-conservative",
                "policy_version": "1",
                "maximum_bps": "10",
            },
            "margin_mode": "CROSS",
            "position_mode": "NET",
            "instrument_rules": {
                "contract_multiplier": snapshot.multiplier,
                "contract_type": "LINEAR",
                "base_currency": "BTC",
                "quote_currency": "USDT",
                "settlement_currency": "USDT",
                "tick_size": snapshot.tick,
                "lot_size": snapshot.lot,
                "minimum_quantity": snapshot.minimum,
                "minimum_notional": "5",
                "rules_version": "blofin-observed-linear/v1",
            },
            "basis_policy": {
                "policy_id": "manual-demo-same-venue-quote",
                "policy_version": "1",
                "evidence_price": amount(snapshot.price),
                "execution_price": amount(snapshot.price),
                "formula": "same venue preview quote; no strategy/cross-venue evidence claimed",
                "timestamp": snapshot.observed_at,
                "tolerance_bps": "10",
                "freshness_seconds": 10,
            },
            "risk_and_exits": {
                "risk_budget": amount(gross_loss),
                "maximum_loss": amount(gross_loss + fee + slippage),
                "fee_allowance": amount(fee),
                "slippage_allowance": amount(slippage),
                "funding_allowance": amount("0"),
                "stop": amount(request.stop),
                "targets": [
                    {
                        "order": 1,
                        "price": amount(request.target),
                        "quantity_fraction": "1",
                        "derivation": derivation,
                    }
                ],
                "runner": {
                    "enabled": False,
                    "remaining_quantity_fraction": "0",
                    "rule_id": "manual-demo-no-runner",
                    "rule_version": "1",
                    "expression": "one full-position target",
                },
                "leverage": "1",
                "margin_assumption_id": "verified-demo-existing-1x",
                "margin_assumption_version": "1",
            },
            "valid_from": now,
            "valid_until": now + timedelta(seconds=60),
            "calculation_inputs": [
                {
                    "name": "manual_connectivity_rr",
                    "input_value": "1",
                    "result_value": "1",
                    "unit": "POLICY",
                    "formula_id": MANUAL_CONNECTIVITY_RR_POLICY,
                    "formula_version": "1",
                    "precision": 0,
                    "rounding_mode": "EXACT",
                    "conservative_remainder": "0",
                }
            ]
            + [
                {
                    "name": name,
                    "input_value": value,
                    "result_value": value,
                    "unit": "USDT",
                    "formula_id": "observed-demo-preflight",
                    "formula_version": "1",
                    "precision": 12,
                    "rounding_mode": "EXACT",
                    "conservative_remainder": "0",
                }
                for name, value in (
                    ("venue_equity", snapshot.equity),
                    ("venue_available", snapshot.available),
                )
            ],
            "execution_policy_version": MANUAL_DEMO_POLICY,
        }
    )
    execution_reward_risk(plan)
    return plan

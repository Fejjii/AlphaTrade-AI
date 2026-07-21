"""Fail-closed fresh risk evaluation for paper order placement (AT-012).

Does not trust client-supplied or stale stored risk results. Re-evaluates the
deterministic RiskEngine with authoritative DailyRiskState synced from paper
portfolio facts, plus kill switch and request↔proposal binding.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.core.errors import TradingPolicyError
from app.db.models import TradeProposal as TradeProposalModel
from app.schemas.approval import ApprovalRequest
from app.schemas.common import RiskAction, TradeDirection
from app.schemas.execution import PaperOrderRequest
from app.schemas.risk import RiskCheckRequest, RiskCheckResult
from app.services.execution_eligibility import paper_execution_eligibility
from app.services.mappers.proposal_mapper import proposal_to_schema
from app.services.risk.daily_risk_accounting import DailyRiskAccounting
from app.services.risk.kill_switch import KillSwitchService
from app.services.risk.rules import RiskEvaluationContext, default_is_weekend
from app.services.risk_service import RiskService


@dataclass(frozen=True)
class BoundPaperPlacement:
    """Server-authoritative parameters accepted for paper fill."""

    symbol: str
    side: str
    size: Decimal
    price: Decimal | None
    entry_price: Decimal
    stop_loss: Decimal
    risk_result: RiskCheckResult
    account_equity: Decimal
    open_exposure_notional: Decimal
    realized_pnl_today: Decimal
    trade_count_today: int


class PaperExecutionRiskGate:
    """Evaluate whether a paper order may be placed right now."""

    def __init__(
        self,
        *,
        risk_service: RiskService,
        daily_risk: DailyRiskAccounting,
        kill_switch: KillSwitchService,
    ) -> None:
        self._risk = risk_service
        self._daily_risk = daily_risk
        self._kill_switch = kill_switch

    def evaluate(
        self,
        *,
        proposal: TradeProposalModel,
        approval: ApprovalRequest,
        request: PaperOrderRequest,
    ) -> BoundPaperPlacement:
        proposal_schema = proposal_to_schema(proposal)

        if proposal_schema.risk_result is None:
            raise self._reject(
                "missing_risk_result",
                "Paper execution requires a prior risk evaluation on the proposal.",
            )

        eligible, eligibility_reason = paper_execution_eligibility(proposal_schema, approval)
        if not eligible:
            raise self._reject(
                "eligibility_blocked",
                eligibility_reason or "Paper execution is not eligible.",
            )

        stop_loss = proposal.stop_loss
        if stop_loss is None:
            raise self._reject(
                "missing_stop_loss",
                "Stop loss is required before paper execution.",
            )

        entry_price = proposal.entry_price
        if abs(entry_price - stop_loss) <= 0:
            raise self._reject(
                "invalid_stop_distance",
                "Stop loss distance must be greater than zero.",
            )

        proposal_symbol = str(proposal.symbol)
        if str(request.symbol) != proposal_symbol:
            raise self._reject(
                "symbol_mismatch",
                "Order symbol must match the approved proposal symbol.",
                details={
                    "requested_symbol": str(request.symbol),
                    "proposal_symbol": proposal_symbol,
                },
            )

        expected_side = "buy" if proposal.direction is TradeDirection.LONG else "sell"
        if request.side.value != expected_side:
            raise self._reject(
                "side_mismatch",
                "Order side must match the approved proposal direction.",
                details={
                    "requested_side": request.side.value,
                    "expected_side": expected_side,
                },
            )

        if request.size != proposal.position_size:
            raise self._reject(
                "size_mismatch",
                "Order size must match the approved proposal size.",
                details={
                    "requested_size": str(request.size),
                    "proposal_size": str(proposal.position_size),
                },
            )

        bound_price = request.price
        if bound_price is not None and bound_price != entry_price:
            raise self._reject(
                "price_mismatch",
                "Order price must match the approved proposal entry price.",
                details={
                    "requested_price": str(bound_price),
                    "proposal_entry_price": str(entry_price),
                },
            )

        # Market orders fill at the evaluated proposal entry when price omitted.
        fill_price = bound_price if bound_price is not None else entry_price

        # Authoritative sync from orders/positions — never trust client risk counters.
        snapshot = self._daily_risk.sync_from_portfolio(
            organization_id=proposal.organization_id,
            user_id=proposal.user_id,
        )
        account_equity = snapshot.account_equity
        user_settings = self._daily_risk.risk_settings.get(
            organization_id=proposal.organization_id,
            user_id=proposal.user_id,
        )

        kill_eval = self._kill_switch.evaluate(organization_id=proposal.organization_id)
        if kill_eval.reason_code == "kill_switch_unavailable":
            raise self._reject(
                "kill_switch_unavailable",
                "Kill switch state is unavailable; paper execution refused.",
            )
        kill_active = kill_eval.blocked

        overtrading = False
        if user_settings.overtrading_guard_enabled:
            max_trades = (
                snapshot.max_trades_per_day
                if snapshot.max_trades_per_day is not None
                else user_settings.max_trades_per_day
            )
            overtrading = snapshot.trade_count >= max_trades

        protect_green = False
        if (
            user_settings.green_day_protection_enabled
            and user_settings.daily_target is not None
            and snapshot.realized_pnl >= user_settings.daily_target
        ):
            protect_green = True

        context = RiskEvaluationContext(
            daily_locked=snapshot.daily_locked,
            realized_pnl_today=snapshot.realized_pnl,
            daily_loss_limit=snapshot.daily_loss_limit,
            trades_today=snapshot.trade_count,
            protect_green_day=protect_green,
            kill_switch_active=kill_active,
            overtrading=overtrading,
            is_weekend=default_is_weekend(),
            open_exposure_notional=snapshot.open_exposure_notional,
        )

        risk_request = RiskCheckRequest(
            symbol=proposal_symbol,
            direction=proposal.direction,
            strategy_id=proposal.strategy_id,
            entry_price=entry_price,
            stop_loss=stop_loss,
            position_size=proposal.position_size,
            leverage=proposal.leverage,
            account_equity=account_equity,
            risk_percent=user_settings.max_risk_per_trade_percent,
        )
        fresh = self._risk.check(risk_request, context=context)

        if fresh.action is RiskAction.BLOCK:
            rule_ids = [t.rule_id.value for t in fresh.triggered_rules]
            raise self._reject(
                "fresh_risk_blocked",
                "Paper execution blocked by risk engine.",
                details={
                    "risk_action": fresh.action.value,
                    "rules": ",".join(rule_ids),
                },
            )

        stored = proposal_schema.risk_result
        if stored.action is RiskAction.BLOCK:
            raise self._reject(
                "stale_risk_blocked",
                "Paper execution blocked by prior risk evaluation.",
                details={"risk_action": stored.action.value},
            )

        return BoundPaperPlacement(
            symbol=proposal_symbol,
            side=expected_side,
            size=proposal.position_size,
            price=fill_price,
            entry_price=entry_price,
            stop_loss=stop_loss,
            risk_result=fresh,
            account_equity=account_equity,
            open_exposure_notional=snapshot.open_exposure_notional,
            realized_pnl_today=snapshot.realized_pnl,
            trade_count_today=snapshot.trade_count,
        )

    @staticmethod
    def _reject(
        reason_code: str,
        message: str,
        *,
        details: dict[str, str] | None = None,
    ) -> TradingPolicyError:
        payload = {"reason": reason_code}
        if details:
            payload.update(details)
        return TradingPolicyError(message, details=payload)

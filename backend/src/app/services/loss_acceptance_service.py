"""Loss acceptance gate (Slice 33)."""

from __future__ import annotations

from decimal import Decimal

from app.schemas.common import LossAcceptanceStatus, PreTradeRecommendation
from app.schemas.position_sizing import LossAcceptanceRequest, LossAcceptanceResult


class LossAcceptanceService:
    """Deterministic loss acceptance workflow."""

    def evaluate(
        self,
        *,
        planned_loss_amount: Decimal,
        request: LossAcceptanceRequest,
    ) -> LossAcceptanceResult:
        if request.planned_loss_amount != planned_loss_amount:
            return LossAcceptanceResult(
                planned_loss_amount=planned_loss_amount,
                accepted=False,
                status=LossAcceptanceStatus.REJECTED.value,
                recommendation="Planned loss mismatch — recalculate position size.",
                can_execute_paper=False,
            )

        if request.accepted:
            return LossAcceptanceResult(
                planned_loss_amount=planned_loss_amount,
                accepted=True,
                status=LossAcceptanceStatus.ACCEPTED.value,
                recommendation="Loss accepted — paper execution may proceed if other gates pass.",
                can_execute_paper=True,
            )

        return LossAcceptanceResult(
            planned_loss_amount=planned_loss_amount,
            accepted=False,
            status=LossAcceptanceStatus.REJECTED.value,
            recommendation="Reduce size or skip trade — planned loss not acceptable.",
            can_execute_paper=False,
        )

    @staticmethod
    def recommendation_after_rejection(
        sizing_recommendation: PreTradeRecommendation,
    ) -> PreTradeRecommendation:
        if sizing_recommendation in {
            PreTradeRecommendation.NORMAL_SIZE,
            PreTradeRecommendation.HIGH_CONVICTION,
        }:
            return PreTradeRecommendation.SMALL_PROBE
        return PreTradeRecommendation.NO_TRADE

    @staticmethod
    def requires_acceptance(planned_loss: Decimal, account_balance: Decimal) -> bool:
        if account_balance <= 0:
            return True
        ratio = planned_loss / account_balance
        return ratio >= Decimal("0.005")

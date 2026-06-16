"""Position sizing engine v2 (Slice 33)."""

from __future__ import annotations

from decimal import Decimal

from app.schemas.common import PreTradeRecommendation
from app.schemas.position_sizing import PositionSizingRequest, PositionSizingResult


class PositionSizingService:
    """Deterministic position sizing — no LLM authority."""

    def calculate(self, request: PositionSizingRequest) -> PositionSizingResult:
        entry = request.entry_price
        invalidation = request.invalidation_level
        stop_distance = abs(entry - invalidation)
        if stop_distance <= Decimal("0"):
            raise ValueError("Stop loss distance must be positive.")

        max_loss = request.account_balance * (request.max_risk_percent / Decimal("100"))
        raw_size = max_loss / stop_distance

        rr: float | None = None
        breakeven_wr: float | None = None
        if request.take_profit_price is not None:
            reward = abs(request.take_profit_price - entry)
            if reward > 0:
                rr = float(reward / stop_distance)
                breakeven_wr = 1.0 / (1.0 + rr)

        confidence = request.confidence_score
        recommendation = self._recommendation_for_confidence(confidence)
        adjusted_size = self._confidence_adjusted_size(raw_size, confidence, recommendation)

        leverage_rec = min(request.leverage_limit, Decimal("10"))
        if confidence >= 80:
            leverage_rec = min(request.leverage_limit, Decimal("5"))
        elif confidence < 60:
            leverage_rec = min(request.leverage_limit, Decimal("3"))

        worst_case = (
            f"If price hits invalidation at {invalidation}, loss ≈ "
            f"{max_loss.quantize(Decimal('0.01'))} ({request.max_risk_percent}% of account)."
        )

        return PositionSizingResult(
            entry_price=entry,
            invalidation_level=invalidation,
            stop_loss_distance=stop_distance,
            account_balance=request.account_balance,
            max_risk_percent=request.max_risk_percent,
            maximum_acceptable_loss=max_loss,
            notional_position_size=raw_size,
            leverage_limit=request.leverage_limit,
            leverage_recommendation=leverage_rec,
            risk_reward_ratio=rr,
            required_breakeven_win_rate=breakeven_wr,
            confidence_score=confidence,
            confidence_adjusted_size=adjusted_size,
            worst_case_scenario=worst_case,
            final_recommendation=recommendation,
            planned_loss_amount=max_loss,
        )

    @staticmethod
    def _recommendation_for_confidence(confidence: float) -> PreTradeRecommendation:
        if confidence < 40:
            return PreTradeRecommendation.NO_TRADE
        if confidence < 60:
            return PreTradeRecommendation.WATCH
        if confidence < 80:
            return PreTradeRecommendation.NORMAL_SIZE
        return PreTradeRecommendation.HIGH_CONVICTION

    @staticmethod
    def _confidence_adjusted_size(
        raw_size: Decimal,
        confidence: float,
        recommendation: PreTradeRecommendation,
    ) -> Decimal:
        if recommendation is PreTradeRecommendation.NO_TRADE:
            return Decimal("0")
        if recommendation is PreTradeRecommendation.WATCH:
            return (raw_size * Decimal("0.10")).quantize(Decimal("0.00000001"))
        if recommendation is PreTradeRecommendation.NORMAL_SIZE:
            factor = Decimal("0.75") if confidence < 70 else Decimal("1")
            return (raw_size * factor).quantize(Decimal("0.00000001"))
        # high conviction — cap at 1R unless strongly validated (placeholder: 90%+)
        factor = Decimal("1") if confidence >= 90 else Decimal("0.85")
        return (raw_size * factor).quantize(Decimal("0.00000001"))

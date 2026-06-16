"""Stop loss refusal and discipline analysis (Slice 36)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.schemas.common import LossAcceptanceStatus, TradeDirection
from app.schemas.human_vs_system import StopLossAnalysis


@dataclass(frozen=True)
class StopLossAnalysisInput:
    planned_stop: Decimal | None
    actual_stop: Decimal | None
    planned_loss: Decimal | None
    actual_loss: Decimal | None
    entry_price: Decimal | None
    exit_price: Decimal | None
    direction: TradeDirection | None
    loss_acceptance_status: LossAcceptanceStatus | None
    stop_was_placed: bool | None
    stop_moved_away: bool | None
    held_for_breakeven: bool | None
    exit_after_invalidation: bool | None


class StopLossRefusalAnalyzer:
    """Detect stop-loss discipline issues without shaming the trader."""

    def analyze(self, data: StopLossAnalysisInput) -> StopLossAnalysis:
        limitations: list[str] = []
        violation = False
        avoidable: Decimal | None = None
        lesson_parts: list[str] = []
        restriction: str | None = None

        if data.planned_loss is None and data.planned_stop is None:
            limitations.append("No planned stop or loss amount recorded.")
        if data.actual_loss is None and data.exit_price is None:
            limitations.append("Actual loss or exit price not recorded.")

        if (
            data.planned_loss is not None
            and data.actual_loss is not None
            and data.actual_loss > data.planned_loss
        ):
            violation = True
            excess = (data.actual_loss - data.planned_loss).quantize(Decimal("0.01"))
            avoidable = excess
            lesson_parts.append(
                f"Actual loss exceeded planned loss by approximately {excess} "
                "(estimate — not guaranteed avoidable)."
            )
            restriction = (
                "Consider requiring loss acceptance confirmation before paper execution "
                "when planned loss exceeds your daily threshold."
            )

        if data.stop_was_placed is False:
            violation = True
            lesson_parts.append("Stop was not placed at entry — review pre-trade checklist.")
        if data.stop_moved_away:
            violation = True
            lesson_parts.append(
                "Stop was moved away from invalidation — note the reason in your journal."
            )
        if data.held_for_breakeven:
            lesson_parts.append(
                "Trade was held hoping for breakeven — compare to your invalidation rule."
            )
        if data.loss_acceptance_status == LossAcceptanceStatus.REJECTED:
            violation = True
            lesson_parts.append(
                "Loss acceptance was rejected but trade continued — review your process."
            )
        if data.exit_after_invalidation:
            lesson_parts.append("Exit occurred after thesis invalidation — note the delay.")

        lesson = (
            " ".join(lesson_parts)
            if lesson_parts
            else ("Stop discipline appears aligned with plan based on available data.")
        )

        return StopLossAnalysis(
            stop_violation_flag=violation if violation or lesson_parts else False,
            planned_loss=data.planned_loss,
            actual_loss=data.actual_loss,
            avoidable_loss_estimate=avoidable,
            lesson=lesson,
            future_restriction_suggestion=restriction,
            limitations=limitations,
        )

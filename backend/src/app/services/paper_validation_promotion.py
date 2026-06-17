"""Conservative paper validation promotion (Slice 39 — paper only, no live)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.schemas.common import PaperValidationRecommendation, PaperValidationStatus
from app.schemas.paper_validation import PaperValidationMetrics

MIN_PAPER_TRADES = 10
MIN_PROFIT_FACTOR = 1.1
MAX_DRAWDOWN_PCT = 25.0
MIN_WIN_RATE_FOR_CONTINUE = 0.40


@dataclass(frozen=True)
class PaperPromotionDecision:
    recommendation: PaperValidationRecommendation
    status: PaperValidationStatus | None
    blockers: list[str]
    paper_validated: bool


def evaluate_paper_promotion(
    *,
    metrics: PaperValidationMetrics,
    paper_eligible: bool,
    has_critical_lesson_blockers: bool,
    severe_overtrading: bool,
    min_runtime_days_met: bool,
) -> PaperPromotionDecision:
    blockers: list[str] = []

    if metrics.paper_trades_count == 0:
        return PaperPromotionDecision(
            recommendation=PaperValidationRecommendation.INSUFFICIENT_DATA,
            status=None,
            blockers=["No closed paper trades yet."],
            paper_validated=False,
        )

    if not paper_eligible:
        blockers.append("Strategy is not paper eligible.")
        return PaperPromotionDecision(
            recommendation=PaperValidationRecommendation.RESTRICT,
            status=PaperValidationStatus.FAILED,
            blockers=blockers,
            paper_validated=False,
        )

    if has_critical_lesson_blockers:
        blockers.append("Critical unresolved lesson blockers remain.")
        return PaperPromotionDecision(
            recommendation=PaperValidationRecommendation.IMPROVE,
            status=PaperValidationStatus.IN_PROGRESS,
            blockers=blockers,
            paper_validated=False,
        )

    if severe_overtrading:
        blockers.append("Recent severe overtrading behavior detected.")
        return PaperPromotionDecision(
            recommendation=PaperValidationRecommendation.RESTRICT,
            status=PaperValidationStatus.IN_PROGRESS,
            blockers=blockers,
            paper_validated=False,
        )

    if metrics.paper_trades_count < MIN_PAPER_TRADES:
        blockers.append(
            f"Need at least {MIN_PAPER_TRADES} closed paper trades "
            f"(have {metrics.paper_trades_count})."
        )
        return PaperPromotionDecision(
            recommendation=PaperValidationRecommendation.INSUFFICIENT_DATA,
            status=PaperValidationStatus.IN_PROGRESS,
            blockers=blockers,
            paper_validated=False,
        )

    if metrics.expectancy <= 0:
        blockers.append("Expectancy is not positive.")
        return PaperPromotionDecision(
            recommendation=PaperValidationRecommendation.IMPROVE,
            status=PaperValidationStatus.FAILED,
            blockers=blockers,
            paper_validated=False,
        )

    if metrics.profit_factor < MIN_PROFIT_FACTOR:
        blockers.append(
            f"Profit factor {metrics.profit_factor:.2f} below threshold {MIN_PROFIT_FACTOR}."
        )
        return PaperPromotionDecision(
            recommendation=PaperValidationRecommendation.IMPROVE,
            status=PaperValidationStatus.IN_PROGRESS,
            blockers=blockers,
            paper_validated=False,
        )

    if metrics.max_drawdown_pct > MAX_DRAWDOWN_PCT:
        blockers.append(
            f"Max drawdown {metrics.max_drawdown_pct:.1f}% exceeds {MAX_DRAWDOWN_PCT}%."
        )
        return PaperPromotionDecision(
            recommendation=PaperValidationRecommendation.RESTRICT,
            status=PaperValidationStatus.FAILED,
            blockers=blockers,
            paper_validated=False,
        )

    stop_respect_rate = (
        metrics.stop_respected_count / metrics.paper_trades_count
        if metrics.paper_trades_count
        else 0.0
    )
    if stop_respect_rate < 0.8 and metrics.paper_trades_count >= MIN_PAPER_TRADES:
        blockers.append("Stop rules not consistently respected in paper simulation.")

    if not min_runtime_days_met:
        blockers.append("Paper validation has not run across enough time or samples.")

    if blockers:
        return PaperPromotionDecision(
            recommendation=PaperValidationRecommendation.IMPROVE,
            status=PaperValidationStatus.IN_PROGRESS,
            blockers=blockers,
            paper_validated=False,
        )

    if metrics.win_rate >= MIN_WIN_RATE_FOR_CONTINUE and metrics.profit_factor >= MIN_PROFIT_FACTOR:
        return PaperPromotionDecision(
            recommendation=PaperValidationRecommendation.PAPER_VALIDATED,
            status=PaperValidationStatus.PASSED,
            blockers=[],
            paper_validated=True,
        )

    if metrics.expectancy > 0:
        return PaperPromotionDecision(
            recommendation=PaperValidationRecommendation.CONTINUE,
            status=PaperValidationStatus.IN_PROGRESS,
            blockers=[],
            paper_validated=False,
        )

    return PaperPromotionDecision(
        recommendation=PaperValidationRecommendation.RETIRE,
        status=PaperValidationStatus.FAILED,
        blockers=["Paper metrics do not support continuation."],
        paper_validated=False,
    )


def compute_max_drawdown(equity_points: list[Decimal]) -> float:
    if not equity_points:
        return 0.0
    peak = equity_points[0]
    max_dd = Decimal("0")
    for eq in equity_points:
        if eq > peak:
            peak = eq
        if peak > 0:
            dd = (peak - eq) / peak * Decimal("100")
            max_dd = max(max_dd, dd)
    return float(max_dd)

"""Conservative strategy promotion after backtest v1."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.schemas.backtest import BacktestMetrics
from app.schemas.common import BacktestRecommendation, BacktestStatus, StrategyValidationStatus

MIN_SAMPLE_SIZE = 20
PREFERRED_SAMPLE_SIZE = 30
MIN_PROFIT_FACTOR = 1.1
MAX_DRAWDOWN_PCT = 25.0
MAX_SINGLE_LOSS_PCT_OF_CAPITAL = 10.0


@dataclass(frozen=True)
class PromotionDecision:
    recommendation: BacktestRecommendation
    backtest_status: BacktestStatus
    validation_status: StrategyValidationStatus | None
    paper_eligible: bool
    limitations: list[str]


def evaluate_promotion(
    *,
    metrics: BacktestMetrics,
    machine_readable: bool,
    data_quality: str,
    meets_success_criteria: bool,
) -> PromotionDecision:
    limitations: list[str] = []

    if not machine_readable:
        return PromotionDecision(
            recommendation=BacktestRecommendation.NEEDS_STRUCTURED_RULES,
            backtest_status=BacktestStatus.FAILED,
            validation_status=None,
            paper_eligible=False,
            limitations=["Rules could not be evaluated mechanically."],
        )

    if data_quality != "ok":
        return PromotionDecision(
            recommendation=BacktestRecommendation.UNRELIABLE_DATA,
            backtest_status=BacktestStatus.FAILED,
            validation_status=None,
            paper_eligible=False,
            limitations=["Historical data incomplete or stale — result unreliable."],
        )

    if metrics.trade_count < MIN_SAMPLE_SIZE:
        limitations.append(
            f"Sample size {metrics.trade_count} below minimum {MIN_SAMPLE_SIZE} — "
            "statistical confidence is low."
        )
        return PromotionDecision(
            recommendation=BacktestRecommendation.NEEDS_MORE_SAMPLE,
            backtest_status=BacktestStatus.COMPLETED,
            validation_status=StrategyValidationStatus.IN_REVIEW,
            paper_eligible=False,
            limitations=limitations,
        )

    if metrics.expectancy <= 0:
        limitations.append("Negative or zero expectancy — not paper eligible.")
        return PromotionDecision(
            recommendation=BacktestRecommendation.RESTRICTED,
            backtest_status=BacktestStatus.COMPLETED,
            validation_status=StrategyValidationStatus.RESTRICTED,
            paper_eligible=False,
            limitations=limitations,
        )

    if metrics.profit_factor < MIN_PROFIT_FACTOR:
        limitations.append(
            f"Profit factor {metrics.profit_factor:.2f} below threshold {MIN_PROFIT_FACTOR}."
        )
        return PromotionDecision(
            recommendation=BacktestRecommendation.NEEDS_REVIEW,
            backtest_status=BacktestStatus.COMPLETED,
            validation_status=StrategyValidationStatus.IN_REVIEW,
            paper_eligible=False,
            limitations=limitations,
        )

    if metrics.max_drawdown_pct > MAX_DRAWDOWN_PCT:
        limitations.append(
            f"Max drawdown {metrics.max_drawdown_pct:.1f}% exceeds {MAX_DRAWDOWN_PCT}% threshold."
        )
        return PromotionDecision(
            recommendation=BacktestRecommendation.RESTRICTED,
            backtest_status=BacktestStatus.COMPLETED,
            validation_status=StrategyValidationStatus.RESTRICTED,
            paper_eligible=False,
            limitations=limitations,
        )

    if metrics.largest_loss < 0 and abs(metrics.largest_loss) > Decimal("1000"):
        limitations.append("Large single-trade loss detected — review sizing rules.")

    if metrics.trade_count < PREFERRED_SAMPLE_SIZE:
        limitations.append(
            f"Sample size {metrics.trade_count} below preferred {PREFERRED_SAMPLE_SIZE}."
        )
        return PromotionDecision(
            recommendation=BacktestRecommendation.NEEDS_REVIEW,
            backtest_status=BacktestStatus.COMPLETED,
            validation_status=StrategyValidationStatus.IN_REVIEW,
            paper_eligible=False,
            limitations=limitations,
        )

    if meets_success_criteria and metrics.profit_factor >= MIN_PROFIT_FACTOR:
        return PromotionDecision(
            recommendation=BacktestRecommendation.PAPER_ELIGIBLE,
            backtest_status=BacktestStatus.COMPLETED,
            validation_status=StrategyValidationStatus.IN_REVIEW,
            paper_eligible=True,
            limitations=limitations
            or ["Paper eligible — requires paper validation before any live consideration."],
        )

    return PromotionDecision(
        recommendation=BacktestRecommendation.BACKTESTED,
        backtest_status=BacktestStatus.COMPLETED,
        validation_status=StrategyValidationStatus.IN_REVIEW,
        paper_eligible=False,
        limitations=limitations or ["Backtest completed — manual review recommended."],
    )

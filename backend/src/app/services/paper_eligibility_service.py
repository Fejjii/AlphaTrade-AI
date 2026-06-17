"""Deterministic paper eligibility gates (Slice 38 — paper only, no live promotion)."""

from __future__ import annotations

import uuid
from collections import Counter

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import NotFoundError
from app.repositories.backtest import BacktestRunRepository
from app.repositories.strategy_library import UserStrategyRepository, UserStrategyVersionRepository
from app.schemas.backtest import BacktestResult
from app.schemas.common import (
    BacktestRunStatus,
    BacktestStatus,
    LessonCandidateStatus,
    LessonSeverity,
    PaperEligibilityStatus,
    PaperValidationRecommendation,
    PaperValidationStatus,
)
from app.schemas.lesson import LessonCandidate
from app.schemas.paper_eligibility import BacktestMetricsSummary, PaperEligibilityReport
from app.services.lesson_candidate_service import LessonCandidateService
from app.services.strategy_promotion import (
    MAX_DRAWDOWN_PCT,
    MIN_PROFIT_FACTOR,
    MIN_SAMPLE_SIZE,
    PREFERRED_SAMPLE_SIZE,
)
from app.services.strategy_testability_service import StrategyTestabilityService

TESTABILITY_THRESHOLD = 70
CRITICAL_SEVERITIES = {LessonSeverity.HIGH, LessonSeverity.CRITICAL}


class PaperEligibilityService:
    """Combine testability, backtest, lessons, and paper validation into one gate."""

    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._strategies = UserStrategyRepository(session)
        self._versions = UserStrategyVersionRepository(session)
        self._backtests = BacktestRunRepository(session)
        self._testability = StrategyTestabilityService(session)
        self._lesson_service = LessonCandidateService(session)

    def evaluate(
        self,
        strategy_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> PaperEligibilityReport:
        strategy = self._strategies.get_scoped(
            strategy_id, organization_id=organization_id, user_id=user_id
        )
        if strategy is None:
            raise NotFoundError("Strategy not found.")

        version = self._versions.latest(strategy_id)
        testability = self._testability.score(
            strategy_id, organization_id=organization_id, user_id=user_id
        )
        accepted, _ = self._lesson_service.list_accepted(
            organization_id=organization_id, user_id=user_id, limit=100
        )
        strategy_accepted = [a for a in accepted if a.related_strategy_id == strategy_id]

        pending_rows = self._lesson_service.list_for_strategy(
            strategy_id,
            organization_id=organization_id,
            user_id=user_id,
            status=LessonCandidateStatus.PENDING_REVIEW,
            limit=200,
        )
        unresolved = pending_rows
        critical_unresolved = [
            lesson for lesson in unresolved if lesson.severity in CRITICAL_SEVERITIES
        ]

        blockers: list[str] = []
        reasons: list[str] = []
        limitations = [
            "Paper only — real trading and exchange execution remain disabled.",
        ]

        if not testability.has_structured_rules or testability.score < TESTABILITY_THRESHOLD:
            blockers.append(
                f"Testability score {testability.score} below threshold {TESTABILITY_THRESHOLD} "
                "or structured rules missing."
            )
            if testability.not_backtestable_reason:
                blockers.append(testability.not_backtestable_reason)
            return self._report(
                strategy_id=strategy_id,
                status=PaperEligibilityStatus.NEEDS_STRUCTURE,
                paper_eligible=False,
                testability_score=testability.score,
                blockers=blockers,
                reasons=reasons,
                accepted=strategy_accepted,
                unresolved=unresolved,
                recommendation="improve",
                limitations=limitations,
            )

        missing_required = [m.label for m in testability.missing_fields if m.severity == "required"]
        if any("Stop loss" in label for label in missing_required):
            blockers.append("Stop loss rule missing from structured rules.")
        if any("Invalidation" in label for label in missing_required):
            blockers.append("Invalidation conditions missing from strategy card.")
        if blockers:
            return self._report(
                strategy_id=strategy_id,
                status=PaperEligibilityStatus.NEEDS_STRUCTURE,
                paper_eligible=False,
                testability_score=testability.score,
                blockers=blockers,
                reasons=reasons,
                accepted=strategy_accepted,
                unresolved=unresolved,
                recommendation="improve",
                limitations=limitations,
            )

        if critical_unresolved:
            blockers.append(
                f"{len(critical_unresolved)} critical unresolved lesson candidate(s) "
                "for this strategy."
            )
            return self._report(
                strategy_id=strategy_id,
                status=PaperEligibilityStatus.NEEDS_LESSON_REVIEW,
                paper_eligible=False,
                testability_score=testability.score,
                blockers=blockers,
                reasons=reasons,
                accepted=strategy_accepted,
                unresolved=unresolved,
                recommendation="improve",
                limitations=limitations,
            )

        repeated_pending = self._repeated_mistake_blockers(unresolved, strategy_accepted)
        if repeated_pending:
            blockers.extend(repeated_pending)
            return self._report(
                strategy_id=strategy_id,
                status=PaperEligibilityStatus.NEEDS_LESSON_REVIEW,
                paper_eligible=False,
                testability_score=testability.score,
                blockers=blockers,
                reasons=reasons,
                accepted=strategy_accepted,
                unresolved=unresolved,
                recommendation="improve",
                limitations=limitations,
            )

        if version is None or version.backtest_status not in {
            BacktestStatus.COMPLETED,
            BacktestStatus.FAILED,
        }:
            blockers.append("Backtest has not completed for the current strategy version.")
            return self._report(
                strategy_id=strategy_id,
                status=PaperEligibilityStatus.NEEDS_BACKTEST,
                paper_eligible=False,
                testability_score=testability.score,
                blockers=blockers,
                reasons=reasons,
                accepted=strategy_accepted,
                unresolved=unresolved,
                recommendation="improve",
                limitations=limitations,
            )

        latest_backtest = self._latest_backtest_metrics(
            strategy_id, organization_id=organization_id
        )
        if latest_backtest is None:
            blockers.append("No completed backtest result found.")
            return self._report(
                strategy_id=strategy_id,
                status=PaperEligibilityStatus.NEEDS_BACKTEST,
                paper_eligible=False,
                testability_score=testability.score,
                blockers=blockers,
                reasons=reasons,
                accepted=strategy_accepted,
                unresolved=unresolved,
                recommendation="improve",
                limitations=limitations,
            )

        if latest_backtest.trade_count < MIN_SAMPLE_SIZE:
            blockers.append(
                f"Backtest sample size {latest_backtest.trade_count} "
                f"below minimum {MIN_SAMPLE_SIZE}."
            )
            return self._report(
                strategy_id=strategy_id,
                status=PaperEligibilityStatus.NEEDS_MORE_SAMPLE,
                paper_eligible=False,
                testability_score=testability.score,
                blockers=blockers,
                reasons=reasons,
                latest=latest_backtest,
                accepted=strategy_accepted,
                unresolved=unresolved,
                recommendation="improve",
                limitations=limitations,
            )

        promotion_blockers = self._backtest_gate_blockers(latest_backtest)
        if promotion_blockers:
            restricted = any(
                "expectancy" in b.lower() or "drawdown" in b.lower() for b in promotion_blockers
            )
            status = (
                PaperEligibilityStatus.RESTRICTED
                if restricted
                else PaperEligibilityStatus.NEEDS_MORE_SAMPLE
            )
            rec = "restrict" if restricted else "improve"
            return self._report(
                strategy_id=strategy_id,
                status=status,
                paper_eligible=False,
                testability_score=testability.score,
                blockers=promotion_blockers,
                reasons=reasons,
                latest=latest_backtest,
                accepted=strategy_accepted,
                unresolved=unresolved,
                recommendation=rec,
                limitations=limitations,
            )

        if version.paper_validation_status == PaperValidationStatus.IN_PROGRESS:
            reasons.append("Paper validation run in progress — simulated trades only.")
            return self._report(
                strategy_id=strategy_id,
                status=PaperEligibilityStatus.PAPER_VALIDATION_RUNNING,
                paper_eligible=True,
                testability_score=testability.score,
                blockers=[],
                reasons=reasons,
                latest=latest_backtest,
                accepted=strategy_accepted,
                unresolved=unresolved,
                recommendation="continue",
                limitations=limitations,
            )

        if version.paper_validation_status == PaperValidationStatus.PASSED:
            reasons.append("Paper validation passed — still paper only, not live trading.")
            return self._report(
                strategy_id=strategy_id,
                status=PaperEligibilityStatus.PAPER_VALIDATED,
                paper_eligible=True,
                testability_score=testability.score,
                blockers=[],
                reasons=reasons,
                latest=latest_backtest,
                accepted=strategy_accepted,
                unresolved=unresolved,
                recommendation="continue",
                limitations=limitations,
            )

        reasons.extend(
            [
                f"Testability score {testability.score} meets threshold.",
                f"Backtest sample {latest_backtest.trade_count} "
                f"(preferred {PREFERRED_SAMPLE_SIZE}).",
                f"Profit factor {latest_backtest.profit_factor:.2f} (min {MIN_PROFIT_FACTOR}).",
                f"Max drawdown {latest_backtest.max_drawdown_pct:.1f}% (max {MAX_DRAWDOWN_PCT}%).",
            ]
        )
        if unresolved:
            reasons.append(
                f"{len(unresolved)} pending lesson observation(s) — "
                "review before promoting further."
            )

        strategy.paper_eligible = True
        return self._report(
            strategy_id=strategy_id,
            status=PaperEligibilityStatus.PAPER_ELIGIBLE,
            paper_eligible=True,
            testability_score=testability.score,
            blockers=[],
            reasons=reasons,
            latest=latest_backtest,
            accepted=strategy_accepted,
            unresolved=unresolved,
            recommendation="continue",
            limitations=limitations,
        )

    def refresh_strategy_flag(
        self,
        strategy_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Sync strategy.paper_eligible from gate evaluation."""
        report = self.evaluate(strategy_id, organization_id=organization_id, user_id=user_id)
        strategy = self._strategies.get_scoped(
            strategy_id, organization_id=organization_id, user_id=user_id
        )
        if strategy is not None:
            strategy.paper_eligible = report.paper_eligible
        return report.paper_eligible

    def _latest_backtest_metrics(
        self,
        strategy_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
    ) -> BacktestMetricsSummary | None:
        rows, _ = self._backtests.list_for_strategy(
            strategy_id, organization_id=organization_id, limit=1, offset=0
        )
        for row in rows:
            if row.status != BacktestRunStatus.COMPLETED or not row.result:
                continue
            result = BacktestResult.model_validate(row.result)
            return BacktestMetricsSummary(
                trade_count=result.metrics.trade_count,
                win_rate=float(result.metrics.win_rate),
                profit_factor=float(result.metrics.profit_factor),
                expectancy=result.metrics.expectancy,
                max_drawdown_pct=float(result.metrics.max_drawdown_pct),
                recommendation=result.recommendation.value if result.recommendation else None,
            )
        return None

    @staticmethod
    def _backtest_gate_blockers(metrics: BacktestMetricsSummary) -> list[str]:
        blockers: list[str] = []
        if metrics.expectancy <= 0:
            blockers.append("Negative or zero expectancy — not paper eligible.")
        if metrics.profit_factor < MIN_PROFIT_FACTOR:
            blockers.append(
                f"Profit factor {metrics.profit_factor:.2f} below threshold {MIN_PROFIT_FACTOR}."
            )
        if metrics.max_drawdown_pct > MAX_DRAWDOWN_PCT:
            blockers.append(
                f"Max drawdown {metrics.max_drawdown_pct:.1f}% exceeds {MAX_DRAWDOWN_PCT}%."
            )
        if metrics.trade_count < PREFERRED_SAMPLE_SIZE:
            blockers.append(
                f"Sample size {metrics.trade_count} below preferred {PREFERRED_SAMPLE_SIZE}."
            )
        return blockers

    @staticmethod
    def _repeated_mistake_blockers(
        unresolved: list[LessonCandidate],
        accepted: list,
    ) -> list[str]:
        if not unresolved:
            return []
        accepted_types = Counter(a.mistake_type for a in accepted)
        blockers: list[str] = []
        for lesson in unresolved:
            if accepted_types.get(lesson.mistake_type, 0) >= 1:
                blockers.append(
                    f"Repeated mistake '{lesson.mistake_type}' has pending review — "
                    "accept or reject related lessons first."
                )
        return blockers

    def _report(
        self,
        *,
        strategy_id: uuid.UUID,
        status: PaperEligibilityStatus,
        paper_eligible: bool,
        testability_score: int,
        blockers: list[str],
        reasons: list[str],
        accepted: list,
        unresolved: list[LessonCandidate],
        recommendation: str,
        limitations: list[str],
        latest: BacktestMetricsSummary | None = None,
    ) -> PaperEligibilityReport:
        paper_rec: PaperValidationRecommendation | None = None
        try:
            paper_rec = PaperValidationRecommendation(recommendation)
        except ValueError:
            paper_rec = None

        return PaperEligibilityReport(
            strategy_id=strategy_id,
            status=status,
            paper_eligible=paper_eligible,
            testability_score=testability_score,
            blockers=blockers,
            eligibility_reasons=reasons,
            latest_backtest=latest,
            accepted_lessons=accepted,
            unresolved_lesson_candidates=unresolved,
            paper_validation_recommendation=paper_rec,
            recommendation=recommendation,
            real_trading_enabled=self._settings.enable_real_trading,
            limitations=limitations,
        )

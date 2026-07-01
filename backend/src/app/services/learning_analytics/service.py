"""Learning analytics read service (Slice 84 — record derived, no automation).

Live-computed aggregations over the manual paper validation workflow. This
service only reads existing records and returns derived summaries. It never
mutates data and never touches order, proposal, approval, execution, exchange,
engine, scanner, worker, or Telegram code paths.
"""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from app.db.models import (
    PaperValidationAlert,
    PaperValidationCandidate,
    PaperValidationDraft,
    PaperValidationRunPlan,
    PaperValidationRunSession,
    PaperValidationSessionObservation,
    PaperValidationSessionResult,
)
from app.schemas.analytics import AnalyticsDateRange
from app.schemas.common import (
    PaperValidationDisciplineAssessment,
    PaperValidationEntryAssessment,
    PaperValidationOutcome,
    PaperValidationRunSessionStatus,
)
from app.schemas.learning_analytics import (
    BehaviorInsight,
    BehaviorInsightsResponse,
    ConfidenceBucketStat,
    ConfidenceOutcomeResponse,
    DisciplineAnalyticsResponse,
    LearningAnalyticsFunnel,
    LearningAnalyticsSummaryResponse,
    LessonTheme,
    LessonThemesResponse,
    ObservationMetrics,
    OutcomeDistributionItem,
    RateMetrics,
    SetupDimension,
    SetupPerformanceGroup,
    SetupPerformanceResponse,
    SetupRankingItem,
    SetupRankingResponse,
)
from app.services.analytics.helpers import date_range_bounds
from app.services.learning_analytics.scoring import (
    CONFIDENCE_BUCKETS,
    confidence_bucket,
    correlation_sign,
    discipline_grade,
    discipline_points,
    extract_lesson_themes,
    insight_confidence,
    quality_score,
    safe_rate,
)

_UNKNOWN = "unknown"


@dataclass(frozen=True)
class _Record:
    """Denormalized session + outcome row used for aggregation."""

    session: PaperValidationRunSession
    result: PaperValidationSessionResult
    confidence: float | None


class LearningAnalyticsService:
    """Compute read-only learning summaries for a tenant."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # -- summary ---------------------------------------------------------

    def summary(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
        start_date: date | None,
        end_date: date | None,
        min_sample: int,
    ) -> LearningAnalyticsSummaryResponse:
        start_dt, end_dt = date_range_bounds(start_date, end_date)
        records = self._load_records(
            organization_id=organization_id,
            user_id=user_id,
            start_dt=start_dt,
            end_dt=end_dt,
        )
        results = [record.result for record in records]
        results_count = len(results)

        session_conditions = self._session_scope_conditions(
            organization_id=organization_id, user_id=user_id, start_dt=start_dt, end_dt=end_dt
        )
        total_sessions = self._count(PaperValidationRunSession, *session_conditions)
        completed_sessions = self._count(
            PaperValidationRunSession,
            *session_conditions,
            PaperValidationRunSession.session_status
            == PaperValidationRunSessionStatus.COMPLETED.value,
        )
        cancelled_sessions = self._count(
            PaperValidationRunSession,
            *session_conditions,
            PaperValidationRunSession.session_status
            == PaperValidationRunSessionStatus.CANCELLED.value,
        )

        observations = self._observation_metrics(
            organization_id=organization_id,
            session_ids=[record.session.id for record in records],
        )
        lessons_count = sum(1 for r in results if (r.lessons or "").strip())

        return LearningAnalyticsSummaryResponse(
            organization_id=organization_id,
            user_id=user_id,
            date_range=AnalyticsDateRange(start=start_date, end=end_date),
            min_sample=min_sample,
            funnel=self._funnel(
                organization_id=organization_id,
                user_id=user_id,
                start_dt=start_dt,
                end_dt=end_dt,
                results_count=results_count,
            ),
            total_sessions=total_sessions,
            completed_sessions=completed_sessions,
            cancelled_sessions=cancelled_sessions,
            results_count=results_count,
            outcome_distribution=self._outcome_distribution(results),
            rates=self._rate_metrics(results),
            observations=observations,
            average_minutes_to_outcome=self._average_minutes_to_outcome(records),
            lessons_count=lessons_count,
        )

    # -- setup performance ----------------------------------------------

    def setup_performance(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
        start_date: date | None,
        end_date: date | None,
        dimension: SetupDimension,
        min_sample: int,
    ) -> SetupPerformanceResponse:
        start_dt, end_dt = date_range_bounds(start_date, end_date)
        records = self._load_records(
            organization_id=organization_id,
            user_id=user_id,
            start_dt=start_dt,
            end_dt=end_dt,
        )
        grouped: dict[str, list[PaperValidationSessionResult]] = defaultdict(list)
        for record in records:
            grouped[self._dimension_key(dimension, record)].append(record.result)

        groups = [
            self._build_group(value, results, min_sample) for value, results in grouped.items()
        ]
        groups.sort(key=lambda g: (g.insufficient_data, -g.sample_size, g.dimension_value))

        return SetupPerformanceResponse(
            organization_id=organization_id,
            user_id=user_id,
            date_range=AnalyticsDateRange(start=start_date, end=end_date),
            min_sample=min_sample,
            dimension=dimension,
            groups=groups,
        )

    # -- discipline ------------------------------------------------------

    def discipline(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
        start_date: date | None,
        end_date: date | None,
        min_sample: int,
    ) -> DisciplineAnalyticsResponse:
        start_dt, end_dt = date_range_bounds(start_date, end_date)
        records = self._load_records(
            organization_id=organization_id,
            user_id=user_id,
            start_dt=start_dt,
            end_dt=end_dt,
        )
        results = [record.result for record in records]
        sample_size = len(results)
        discipline_breakdown = Counter(r.discipline_assessment for r in results)
        entry_breakdown = Counter(r.entry_assessment for r in results)

        response = DisciplineAnalyticsResponse(
            organization_id=organization_id,
            user_id=user_id,
            date_range=AnalyticsDateRange(start=start_date, end=end_date),
            min_sample=min_sample,
            sample_size=sample_size,
            insufficient_data=sample_size < min_sample,
            discipline_breakdown=dict(discipline_breakdown),
            entry_breakdown=dict(entry_breakdown),
        )
        if sample_size < min_sample:
            return response

        score = round(
            100.0 * sum(discipline_points(r.discipline_assessment) for r in results) / sample_size
        )
        score = max(0, min(100, score))
        response.discipline_score = score
        response.discipline_grade = discipline_grade(score)
        response.issue_frequency = {
            assessment: rate
            for assessment in (
                PaperValidationDisciplineAssessment.SHOULD_HAVE_WAITED.value,
                PaperValidationDisciplineAssessment.SHOULD_HAVE_ENTERED.value,
                PaperValidationDisciplineAssessment.SHOULD_HAVE_AVOIDED.value,
            )
            if (rate := safe_rate(discipline_breakdown.get(assessment, 0), sample_size))
        }
        self._fill_discipline_narrative(response, discipline_breakdown, sample_size)
        return response

    # -- confidence vs outcome ------------------------------------------

    def confidence_outcome(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
        start_date: date | None,
        end_date: date | None,
        min_sample: int,
    ) -> ConfidenceOutcomeResponse:
        start_dt, end_dt = date_range_bounds(start_date, end_date)
        records = self._load_records(
            organization_id=organization_id,
            user_id=user_id,
            start_dt=start_dt,
            end_dt=end_dt,
        )
        buckets: list[ConfidenceBucketStat] = []
        qualifying: list[tuple[int, float]] = []
        for index, (name, lower, upper) in enumerate(CONFIDENCE_BUCKETS):
            bucket_results = [
                record.result for record in records if confidence_bucket(record.confidence) == name
            ]
            size = len(bucket_results)
            insufficient = size < min_sample
            success_rate = safe_rate(
                sum(1 for r in bucket_results if r.outcome == PaperValidationOutcome.SUCCESS.value),
                size,
            )
            buckets.append(
                ConfidenceBucketStat(
                    bucket=name,
                    lower=lower,
                    upper=min(upper, 1.0),
                    sample_size=size,
                    insufficient_data=insufficient,
                    success_rate=success_rate,
                )
            )
            if not insufficient and success_rate is not None:
                qualifying.append((index, success_rate))

        return ConfidenceOutcomeResponse(
            organization_id=organization_id,
            user_id=user_id,
            date_range=AnalyticsDateRange(start=start_date, end=end_date),
            min_sample=min_sample,
            buckets=buckets,
            correlation=correlation_sign(qualifying),
        )

    # -- behavior insights ----------------------------------------------

    def behavior_insights(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
        start_date: date | None,
        end_date: date | None,
        min_sample: int,
    ) -> BehaviorInsightsResponse:
        start_dt, end_dt = date_range_bounds(start_date, end_date)
        records = self._load_records(
            organization_id=organization_id,
            user_id=user_id,
            start_dt=start_dt,
            end_dt=end_dt,
        )
        insights = self._derive_insights(records, min_sample)
        return BehaviorInsightsResponse(
            organization_id=organization_id,
            user_id=user_id,
            date_range=AnalyticsDateRange(start=start_date, end=end_date),
            min_sample=min_sample,
            insights=insights,
        )

    # -- lessons ---------------------------------------------------------

    def lessons(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
        start_date: date | None,
        end_date: date | None,
        min_sample: int,
    ) -> LessonThemesResponse:
        start_dt, end_dt = date_range_bounds(start_date, end_date)
        records = self._load_records(
            organization_id=organization_id,
            user_id=user_id,
            start_dt=start_dt,
            end_dt=end_dt,
        )
        texts = [
            record.result.lessons.strip()
            for record in records
            if (record.result.lessons or "").strip()
        ]
        themes = [
            LessonTheme(theme=word, count=count, example_excerpt=example)
            for word, count, example in extract_lesson_themes(texts)
        ]
        return LessonThemesResponse(
            organization_id=organization_id,
            user_id=user_id,
            date_range=AnalyticsDateRange(start=start_date, end=end_date),
            min_sample=min_sample,
            lessons_count=len(texts),
            themes=themes,
        )

    # -- setup ranking ---------------------------------------------------

    def setup_ranking(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
        start_date: date | None,
        end_date: date | None,
        dimension: SetupDimension,
        min_sample: int,
    ) -> SetupRankingResponse:
        performance = self.setup_performance(
            organization_id=organization_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            dimension=dimension,
            min_sample=min_sample,
        )
        qualifying = [
            group
            for group in performance.groups
            if not group.insufficient_data and group.quality_score is not None
        ]
        qualifying.sort(key=lambda g: g.quality_score or 0.0, reverse=True)
        ranked = [
            SetupRankingItem(
                setup_key=group.dimension_value,
                rank=index + 1,
                quality_score=group.quality_score or 0.0,
                sample_size=group.sample_size,
            )
            for index, group in enumerate(qualifying)
        ]
        return SetupRankingResponse(
            organization_id=organization_id,
            user_id=user_id,
            date_range=AnalyticsDateRange(start=start_date, end=end_date),
            min_sample=min_sample,
            dimension=dimension,
            note=(
                "Read-only ranking for human review only. This does not enable "
                "automation, ordering, proposals, approvals, or execution."
            ),
            ranked=ranked,
        )

    # -- internals -------------------------------------------------------

    def _load_records(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
        start_dt: datetime | None,
        end_dt: datetime | None,
    ) -> list[_Record]:
        stmt = (
            select(
                PaperValidationRunSession,
                PaperValidationSessionResult,
                PaperValidationRunPlan.confidence,
            )
            .join(
                PaperValidationSessionResult,
                PaperValidationSessionResult.run_session_id == PaperValidationRunSession.id,
            )
            .join(
                PaperValidationRunPlan,
                PaperValidationRunPlan.id == PaperValidationRunSession.run_plan_id,
            )
            .where(PaperValidationRunSession.organization_id == organization_id)
        )
        if user_id is not None:
            stmt = stmt.where(PaperValidationRunSession.started_by == user_id)
        if start_dt is not None:
            stmt = stmt.where(PaperValidationSessionResult.recorded_at >= start_dt)
        if end_dt is not None:
            stmt = stmt.where(PaperValidationSessionResult.recorded_at <= end_dt)

        rows = self._session.execute(stmt).all()
        return [_Record(session=row[0], result=row[1], confidence=row[2]) for row in rows]

    def _session_scope_conditions(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
        start_dt: datetime | None,
        end_dt: datetime | None,
    ) -> list[ColumnElement[bool]]:
        conditions: list[ColumnElement[bool]] = [
            PaperValidationRunSession.organization_id == organization_id
        ]
        if user_id is not None:
            conditions.append(PaperValidationRunSession.started_by == user_id)
        if start_dt is not None:
            conditions.append(PaperValidationRunSession.created_at >= start_dt)
        if end_dt is not None:
            conditions.append(PaperValidationRunSession.created_at <= end_dt)
        return conditions

    def _count(self, model: type, *conditions: ColumnElement[bool]) -> int:
        stmt = select(func.count()).select_from(model)
        for condition in conditions:
            stmt = stmt.where(condition)
        return int(self._session.scalar(stmt) or 0)

    def _funnel(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
        start_dt: datetime | None,
        end_dt: datetime | None,
        results_count: int,
    ) -> LearningAnalyticsFunnel:
        def stage_count(model: type, user_column, *extra: ColumnElement[bool]) -> int:
            conditions: list[ColumnElement[bool]] = [model.organization_id == organization_id]
            if start_dt is not None:
                conditions.append(model.created_at >= start_dt)
            if end_dt is not None:
                conditions.append(model.created_at <= end_dt)
            if user_id is not None and user_column is not None:
                conditions.append(user_column == user_id)
            conditions.extend(extra)
            return self._count(model, *conditions)

        return LearningAnalyticsFunnel(
            alerts=stage_count(PaperValidationAlert, PaperValidationAlert.user_id),
            drafts=stage_count(PaperValidationDraft, PaperValidationDraft.created_by),
            candidates=stage_count(PaperValidationCandidate, PaperValidationCandidate.created_by),
            run_plans=stage_count(PaperValidationRunPlan, PaperValidationRunPlan.created_by),
            run_sessions=stage_count(
                PaperValidationRunSession, PaperValidationRunSession.started_by
            ),
            completed_sessions=stage_count(
                PaperValidationRunSession,
                PaperValidationRunSession.started_by,
                PaperValidationRunSession.session_status
                == PaperValidationRunSessionStatus.COMPLETED.value,
            ),
            cancelled_sessions=stage_count(
                PaperValidationRunSession,
                PaperValidationRunSession.started_by,
                PaperValidationRunSession.session_status
                == PaperValidationRunSessionStatus.CANCELLED.value,
            ),
            results=results_count,
        )

    def _observation_metrics(
        self,
        *,
        organization_id: uuid.UUID,
        session_ids: list[uuid.UUID],
    ) -> ObservationMetrics:
        if not session_ids:
            return ObservationMetrics()
        rows = (
            self._session.execute(
                select(PaperValidationSessionObservation.observation_kind).where(
                    PaperValidationSessionObservation.organization_id == organization_id,
                    PaperValidationSessionObservation.run_session_id.in_(session_ids),
                )
            )
            .scalars()
            .all()
        )
        by_kind = Counter(rows)
        total = len(rows)
        return ObservationMetrics(
            total_observations=total,
            average_per_session=round(total / len(session_ids), 2),
            by_kind=dict(by_kind),
        )

    @staticmethod
    def _average_minutes_to_outcome(records: list[_Record]) -> float | None:
        durations: list[float] = []
        for record in records:
            started = record.session.started_at
            recorded = record.result.recorded_at
            if started is None or recorded is None:
                continue
            start_naive = started.replace(tzinfo=None)
            end_naive = recorded.replace(tzinfo=None)
            minutes = (end_naive - start_naive).total_seconds() / 60.0
            if minutes >= 0:
                durations.append(minutes)
        if not durations:
            return None
        return round(sum(durations) / len(durations), 2)

    @staticmethod
    def _outcome_distribution(
        results: list[PaperValidationSessionResult],
    ) -> list[OutcomeDistributionItem]:
        total = len(results)
        counts = Counter(r.outcome for r in results)
        return [
            OutcomeDistributionItem(
                outcome=outcome,
                count=counts.get(outcome.value, 0),
                rate=safe_rate(counts.get(outcome.value, 0), total),
            )
            for outcome in PaperValidationOutcome
        ]

    @staticmethod
    def _rate_metrics(results: list[PaperValidationSessionResult]) -> RateMetrics:
        total = len(results)
        if total == 0:
            return RateMetrics()
        counts = Counter(r.outcome for r in results)
        behaved_values = [
            r.behaved_as_expected for r in results if r.behaved_as_expected is not None
        ]
        return RateMetrics(
            success_rate=safe_rate(counts.get(PaperValidationOutcome.SUCCESS.value, 0), total),
            failure_rate=safe_rate(counts.get(PaperValidationOutcome.FAILURE.value, 0), total),
            invalidated_rate=safe_rate(
                counts.get(PaperValidationOutcome.INVALIDATED.value, 0), total
            ),
            missed_entry_rate=safe_rate(
                counts.get(PaperValidationOutcome.MISSED_ENTRY.value, 0), total
            ),
            no_trade_rate=safe_rate(counts.get(PaperValidationOutcome.NO_TRADE.value, 0), total),
            inconclusive_rate=safe_rate(
                counts.get(PaperValidationOutcome.INCONCLUSIVE.value, 0), total
            ),
            behaved_as_expected_rate=safe_rate(
                sum(1 for value in behaved_values if value), len(behaved_values)
            ),
            invalidation_hit_rate=safe_rate(sum(1 for r in results if r.invalidation_hit), total),
        )

    @staticmethod
    def _dimension_key(dimension: SetupDimension, record: _Record) -> str:
        session = record.session
        if dimension is SetupDimension.CONDITION:
            return session.condition or _UNKNOWN
        if dimension is SetupDimension.TIMEFRAME:
            return session.timeframe or _UNKNOWN
        if dimension is SetupDimension.SYMBOL:
            return session.symbol or _UNKNOWN
        if dimension is SetupDimension.DIRECTION:
            return session.direction or _UNKNOWN
        return confidence_bucket(record.confidence) or _UNKNOWN

    def _build_group(
        self,
        value: str,
        results: list[PaperValidationSessionResult],
        min_sample: int,
    ) -> SetupPerformanceGroup:
        size = len(results)
        insufficient = size < min_sample
        counts = Counter(r.outcome for r in results)
        success_rate = safe_rate(counts.get(PaperValidationOutcome.SUCCESS.value, 0), size)
        failure_rate = safe_rate(counts.get(PaperValidationOutcome.FAILURE.value, 0), size)
        invalidation_rate = safe_rate(sum(1 for r in results if r.invalidation_hit), size)
        behaved_values = [
            r.behaved_as_expected for r in results if r.behaved_as_expected is not None
        ]
        behaved_rate = safe_rate(sum(1 for value_ in behaved_values if value_), len(behaved_values))
        avoided_rate = safe_rate(
            sum(
                1
                for r in results
                if r.discipline_assessment
                == PaperValidationDisciplineAssessment.SHOULD_HAVE_AVOIDED.value
            ),
            size,
        )
        quality = None
        if not insufficient:
            quality = quality_score(
                success_rate or 0.0,
                behaved_rate or 0.0,
                invalidation_rate or 0.0,
                avoided_rate or 0.0,
            )
        return SetupPerformanceGroup(
            dimension_value=value,
            sample_size=size,
            insufficient_data=insufficient,
            quality_score=quality,
            success_rate=success_rate,
            failure_rate=failure_rate,
            invalidation_hit_rate=invalidation_rate,
            behaved_as_expected_rate=behaved_rate,
            outcome_distribution=self._outcome_distribution(results),
        )

    @staticmethod
    def _fill_discipline_narrative(
        response: DisciplineAnalyticsResponse,
        breakdown: Counter[str],
        sample_size: int,
    ) -> None:
        disciplined = breakdown.get(PaperValidationDisciplineAssessment.DISCIPLINED.value, 0)
        if safe_rate(disciplined, sample_size) and (disciplined / sample_size) >= 0.6:
            response.positive_behaviors.append("Most sessions were graded as disciplined.")
        mapping = {
            PaperValidationDisciplineAssessment.SHOULD_HAVE_WAITED.value: (
                "You often entered when you should have waited.",
                "Wait for full setup confirmation before entering.",
            ),
            PaperValidationDisciplineAssessment.SHOULD_HAVE_ENTERED.value: (
                "You often skipped setups you should have entered.",
                "Trust validated setups and act on your plan.",
            ),
            PaperValidationDisciplineAssessment.SHOULD_HAVE_AVOIDED.value: (
                "You often took setups you should have avoided.",
                "Filter out low-quality conditions before committing.",
            ),
        }
        for assessment, (negative, suggestion) in mapping.items():
            rate = safe_rate(breakdown.get(assessment, 0), sample_size)
            if rate and rate >= 0.3:
                response.negative_behaviors.append(negative)
                response.improvement_suggestions.append(suggestion)

    def _derive_insights(self, records: list[_Record], min_sample: int) -> list[BehaviorInsight]:
        insights: list[BehaviorInsight] = []
        results = [record.result for record in records]

        self._insight_strong_setup_misses(records, min_sample, insights)
        self._insight_should_have_waited_low_confidence(records, min_sample, insights)
        self._insight_price_moves_without_entry(results, min_sample, insights)
        self._insight_per_condition(records, min_sample, insights)
        self._insight_confidence_correlation(records, min_sample, insights)
        self._insight_needs_more_validation(records, min_sample, insights)
        return insights

    def _insight_strong_setup_misses(
        self, records: list[_Record], min_sample: int, insights: list[BehaviorInsight]
    ) -> None:
        strong = [
            record.result
            for record in records
            if confidence_bucket(record.confidence) in ("high", "very_high")
        ]
        miss_kinds = {
            PaperValidationEntryAssessment.MISSED_ENTRY.value,
            PaperValidationEntryAssessment.PRICE_MOVED_WITHOUT_ENTRY.value,
        }
        misses = sum(1 for r in strong if r.entry_assessment in miss_kinds)
        rate = safe_rate(misses, len(strong))
        if len(strong) >= min_sample and rate and rate >= 0.3:
            insights.append(
                BehaviorInsight(
                    code="misses_entries_on_strong_setups",
                    message="You miss entries often on strong (high-confidence) setups.",
                    severity="warning",
                    sample_size=len(strong),
                    confidence=insight_confidence(len(strong), min_sample),
                )
            )

    def _insight_should_have_waited_low_confidence(
        self, records: list[_Record], min_sample: int, insights: list[BehaviorInsight]
    ) -> None:
        low = [record.result for record in records if confidence_bucket(record.confidence) == "low"]
        waited = sum(
            1
            for r in low
            if r.discipline_assessment
            == PaperValidationDisciplineAssessment.SHOULD_HAVE_WAITED.value
        )
        rate = safe_rate(waited, len(low))
        if len(low) >= min_sample and rate and rate >= 0.3:
            insights.append(
                BehaviorInsight(
                    code="should_have_waited_on_low_quality",
                    message="You should have waited more often on low-quality setups.",
                    severity="warning",
                    sample_size=len(low),
                    confidence=insight_confidence(len(low), min_sample),
                )
            )

    def _insight_price_moves_without_entry(
        self,
        results: list[PaperValidationSessionResult],
        min_sample: int,
        insights: list[BehaviorInsight],
    ) -> None:
        moved = sum(
            1
            for r in results
            if r.entry_assessment == PaperValidationEntryAssessment.PRICE_MOVED_WITHOUT_ENTRY.value
        )
        rate = safe_rate(moved, len(results))
        if len(results) >= min_sample and rate and rate >= 0.3:
            insights.append(
                BehaviorInsight(
                    code="price_moves_without_entry",
                    message="Price frequently moves without entry after your trigger.",
                    severity="info",
                    sample_size=len(results),
                    confidence=insight_confidence(len(results), min_sample),
                )
            )

    def _insight_per_condition(
        self, records: list[_Record], min_sample: int, insights: list[BehaviorInsight]
    ) -> None:
        by_condition: dict[str, list[PaperValidationSessionResult]] = defaultdict(list)
        for record in records:
            by_condition[record.session.condition or _UNKNOWN].append(record.result)

        for condition, group in by_condition.items():
            if len(group) < min_sample or condition == _UNKNOWN:
                continue
            failure_rate = safe_rate(
                sum(1 for r in group if r.outcome == PaperValidationOutcome.FAILURE.value),
                len(group),
            )
            avoided = any(
                r.discipline_assessment
                == PaperValidationDisciplineAssessment.SHOULD_HAVE_AVOIDED.value
                for r in group
            )
            if failure_rate and failure_rate >= 0.5 and avoided:
                insights.append(
                    BehaviorInsight(
                        code="avoid_condition",
                        message=(
                            f"Consider avoiding the '{condition}' condition — high failure rate."
                        ),
                        severity="warning",
                        sample_size=len(group),
                        confidence=insight_confidence(len(group), min_sample),
                    )
                )
            invalidation_rate = safe_rate(sum(1 for r in group if r.invalidation_hit), len(group))
            if invalidation_rate and invalidation_rate >= 0.5:
                insights.append(
                    BehaviorInsight(
                        code="invalidation_prone_setup",
                        message=(f"Invalidation is frequently hit on the '{condition}' condition."),
                        severity="warning",
                        sample_size=len(group),
                        confidence=insight_confidence(len(group), min_sample),
                    )
                )

    def _insight_confidence_correlation(
        self, records: list[_Record], min_sample: int, insights: list[BehaviorInsight]
    ) -> None:
        qualifying: list[tuple[int, float]] = []
        total_qualifying = 0
        for index, (name, _lower, _upper) in enumerate(CONFIDENCE_BUCKETS):
            bucket_results = [
                record.result for record in records if confidence_bucket(record.confidence) == name
            ]
            if len(bucket_results) < min_sample:
                continue
            success_rate = safe_rate(
                sum(1 for r in bucket_results if r.outcome == PaperValidationOutcome.SUCCESS.value),
                len(bucket_results),
            )
            if success_rate is not None:
                qualifying.append((index, success_rate))
                total_qualifying += len(bucket_results)

        sign = correlation_sign(qualifying)
        messages = {
            "positive": "Higher confidence correlates with better outcomes.",
            "negative": "Higher confidence does NOT correlate with better outcomes.",
            "none": "Confidence shows no clear correlation with outcomes.",
        }
        if sign in messages:
            insights.append(
                BehaviorInsight(
                    code="confidence_correlation",
                    message=messages[sign],
                    severity="info",
                    sample_size=total_qualifying,
                    confidence=insight_confidence(total_qualifying, min_sample),
                )
            )

    def _insight_needs_more_validation(
        self, records: list[_Record], min_sample: int, insights: list[BehaviorInsight]
    ) -> None:
        by_condition: dict[str, list[PaperValidationSessionResult]] = defaultdict(list)
        for record in records:
            by_condition[record.session.condition or _UNKNOWN].append(record.result)

        for condition, group in by_condition.items():
            if condition == _UNKNOWN or not (0 < len(group) < min_sample):
                continue
            success_rate = safe_rate(
                sum(1 for r in group if r.outcome == PaperValidationOutcome.SUCCESS.value),
                len(group),
            )
            if success_rate and success_rate >= 0.5:
                insights.append(
                    BehaviorInsight(
                        code="needs_more_validation",
                        message=(
                            f"The '{condition}' condition looks promising but needs "
                            "more validation sessions."
                        ),
                        severity="info",
                        sample_size=len(group),
                        confidence="low",
                    )
                )

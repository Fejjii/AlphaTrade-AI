"""Strategy quality read service (Slice 89 — record derived, no automation).

Live-computed detector performance analytics over the manual paper validation
workflow. This service only reads existing records and returns derived,
read-only study guidance. It never mutates data, never changes strategy rules,
never enables or disables detectors, and never touches order, proposal,
approval, execution, exchange, engine, scanner, worker, or Telegram code paths.
"""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.db.models import (
    PaperValidationRunPlan,
    PaperValidationRunSession,
    PaperValidationSessionResult,
)
from app.schemas.analytics import AnalyticsDateRange
from app.schemas.common import (
    PaperValidationDisciplineAssessment,
    PaperValidationOutcome,
)
from app.schemas.learning_analytics import ConfidenceBucketStat, OutcomeDistributionItem
from app.schemas.strategy_quality import (
    CalibrationLabel,
    ConfidenceCalibration,
    DetectorExplainResponse,
    DetectorFactor,
    DetectorQualityReport,
    DetectorRankItem,
    DetectorTimeframeStat,
    DetectorTrustTier,
    DetectorVerdict,
    DetectorWarning,
    StrategyQualityDetectorsResponse,
    StrategyQualitySummaryResponse,
    TrustTierCount,
    VerdictCount,
)
from app.schemas.validation_priority import FactorDirection
from app.services.analytics.helpers import date_range_bounds
from app.services.learning_analytics.scoring import (
    CONFIDENCE_BUCKETS,
    confidence_bucket,
    correlation_sign,
    safe_rate,
)
from app.services.market_watcher_setup_detectors import SETUP_DETECTOR_VERSIONS
from app.services.strategy_quality.scoring import (
    RawDetectorFactor,
    RawWarning,
    calibration_label,
    mean_confidence,
    normalize_confidence,
    score_detector,
)

_UNKNOWN = "unknown"

_NOTE = (
    "Read-only strategy quality review for human study only. Verdicts and trust "
    "tiers are guidance for which detectors to trust or improve; they do not "
    "change strategy rules, enable or disable detectors, recommend live trades, "
    "or enable automation, ordering, proposals, approvals, or execution."
)


@dataclass(frozen=True)
class _Record:
    """Denormalized session + outcome row used for detector aggregation."""

    session: PaperValidationRunSession
    result: PaperValidationSessionResult
    confidence: float | None


class StrategyQualityService:
    """Compute read-only detector performance analytics for a tenant."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # -- public ----------------------------------------------------------

    def detectors(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
        start_date: date | None,
        end_date: date | None,
        min_sample: int,
        condition: str | None,
        timeframe: str | None,
    ) -> StrategyQualityDetectorsResponse:
        records = self._load_records(
            organization_id=organization_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            timeframe=timeframe,
        )
        by_condition = self._group_by_condition(records)
        conditions = self._detector_universe(by_condition)
        if condition is not None:
            conditions = [condition] if condition in conditions else []

        reports = [
            self._build_report(name, by_condition.get(name, []), min_sample) for name in conditions
        ]
        reports.sort(
            key=lambda r: (
                r.insufficient_data,
                -(r.quality_score or 0.0),
                -r.sample_size,
                r.condition,
            )
        )
        return StrategyQualityDetectorsResponse(
            organization_id=organization_id,
            user_id=user_id,
            date_range=AnalyticsDateRange(start=start_date, end=end_date),
            min_sample=min_sample,
            note=_NOTE,
            condition_filter=condition,
            timeframe_filter=timeframe,
            detectors=reports,
        )

    def summary(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
        start_date: date | None,
        end_date: date | None,
        min_sample: int,
    ) -> StrategyQualitySummaryResponse:
        records = self._load_records(
            organization_id=organization_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            timeframe=None,
        )
        by_condition = self._group_by_condition(records)
        conditions = self._detector_universe(by_condition)
        reports = [
            self._build_report(name, by_condition.get(name, []), min_sample) for name in conditions
        ]

        trust_counts = Counter(r.trust_tier for r in reports)
        verdict_counts = Counter(r.verdict for r in reports)
        ranked_reports = sorted(
            (r for r in reports if not r.insufficient_data and r.quality_score is not None),
            key=lambda r: (-(r.quality_score or 0.0), -r.sample_size, r.condition),
        )
        ranked = [
            DetectorRankItem(
                condition=r.condition,
                rank=index + 1,
                quality_score=r.quality_score or 0.0,
                sample_size=r.sample_size,
                trust_tier=r.trust_tier,
                verdict=r.verdict,
            )
            for index, r in enumerate(ranked_reports)
        ]

        return StrategyQualitySummaryResponse(
            organization_id=organization_id,
            user_id=user_id,
            date_range=AnalyticsDateRange(start=start_date, end=end_date),
            min_sample=min_sample,
            note=_NOTE,
            total_detectors=len(reports),
            detectors_with_data=sum(1 for r in reports if r.sample_size > 0),
            total_results=sum(r.sample_size for r in reports),
            by_trust_tier=[
                TrustTierCount(trust_tier=tier, count=trust_counts.get(tier, 0))
                for tier in DetectorTrustTier
            ],
            by_verdict=[
                VerdictCount(verdict=verdict, count=verdict_counts.get(verdict, 0))
                for verdict in DetectorVerdict
            ],
            ranked=ranked,
            warnings=self._summary_warnings(reports),
        )

    def explain(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
        start_date: date | None,
        end_date: date | None,
        min_sample: int,
        condition: str,
    ) -> DetectorExplainResponse:
        records = self._load_records(
            organization_id=organization_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            timeframe=None,
        )
        by_condition = self._group_by_condition(records)
        detector_records = by_condition.get(condition, [])
        if not detector_records and condition not in SETUP_DETECTOR_VERSIONS:
            raise NotFoundError("Detector not found.")

        report = self._build_report(condition, detector_records, min_sample)
        return DetectorExplainResponse(
            organization_id=organization_id,
            user_id=user_id,
            date_range=AnalyticsDateRange(start=start_date, end=end_date),
            min_sample=min_sample,
            note=_NOTE,
            report=report,
            timeframes=self._timeframe_stats(condition, detector_records, min_sample),
        )

    # -- internals -------------------------------------------------------

    def _load_records(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
        start_date: date | None,
        end_date: date | None,
        timeframe: str | None,
    ) -> list[_Record]:
        start_dt, end_dt = date_range_bounds(start_date, end_date)
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
        if timeframe is not None:
            stmt = stmt.where(PaperValidationRunSession.timeframe == timeframe)
        if start_dt is not None:
            stmt = stmt.where(PaperValidationSessionResult.recorded_at >= start_dt)
        if end_dt is not None:
            stmt = stmt.where(PaperValidationSessionResult.recorded_at <= end_dt)

        rows = self._session.execute(stmt).all()
        return [_Record(session=row[0], result=row[1], confidence=row[2]) for row in rows]

    @staticmethod
    def _group_by_condition(records: list[_Record]) -> dict[str, list[_Record]]:
        grouped: dict[str, list[_Record]] = defaultdict(list)
        for record in records:
            grouped[record.session.condition or _UNKNOWN].append(record)
        return grouped

    @staticmethod
    def _detector_universe(by_condition: dict[str, list[_Record]]) -> list[str]:
        return sorted(set(SETUP_DETECTOR_VERSIONS) | set(by_condition))

    def _build_report(
        self,
        condition: str,
        records: list[_Record],
        min_sample: int,
    ) -> DetectorQualityReport:
        results = [record.result for record in records]
        size = len(results)
        counts = Counter(r.outcome for r in results)
        discipline_breakdown = Counter(r.discipline_assessment for r in results)
        entry_breakdown = Counter(r.entry_assessment for r in results)

        success_rate = safe_rate(counts.get(PaperValidationOutcome.SUCCESS.value, 0), size)
        invalidation_rate = safe_rate(sum(1 for r in results if r.invalidation_hit), size)
        behaved_values = [
            r.behaved_as_expected for r in results if r.behaved_as_expected is not None
        ]
        behaved_rate = safe_rate(sum(1 for v in behaved_values if v), len(behaved_values))
        avoided_rate = safe_rate(
            discipline_breakdown.get(
                PaperValidationDisciplineAssessment.SHOULD_HAVE_AVOIDED.value, 0
            ),
            size,
        )
        waited_rate = safe_rate(
            discipline_breakdown.get(
                PaperValidationDisciplineAssessment.SHOULD_HAVE_WAITED.value, 0
            ),
            size,
        )
        missed_entry_rate = safe_rate(
            counts.get(PaperValidationOutcome.MISSED_ENTRY.value, 0), size
        )

        calibration = self._confidence_calibration(records, success_rate, min_sample)
        score = score_detector(
            condition=condition,
            sample_size=size,
            success_rate=success_rate,
            behaved_rate=behaved_rate,
            invalidation_hit_rate=invalidation_rate,
            avoided_rate=avoided_rate,
            missed_entry_rate=missed_entry_rate,
            mean_conf=calibration.mean_confidence,
            calibration=calibration.calibration_label.value,
            min_sample=min_sample,
        )

        return DetectorQualityReport(
            condition=condition,
            detector_version=SETUP_DETECTOR_VERSIONS.get(condition),
            sample_size=size,
            insufficient_data=size < min_sample,
            trust_tier=DetectorTrustTier(score.trust_tier),
            verdict=DetectorVerdict(score.verdict),
            quality_score=score.shrunk_quality,
            raw_quality_score=score.raw_quality,
            success_rate=success_rate,
            failure_rate=safe_rate(counts.get(PaperValidationOutcome.FAILURE.value, 0), size),
            invalidated_rate=safe_rate(
                counts.get(PaperValidationOutcome.INVALIDATED.value, 0), size
            ),
            missed_entry_rate=missed_entry_rate,
            no_trade_rate=safe_rate(counts.get(PaperValidationOutcome.NO_TRADE.value, 0), size),
            inconclusive_rate=safe_rate(
                counts.get(PaperValidationOutcome.INCONCLUSIVE.value, 0), size
            ),
            invalidation_hit_rate=invalidation_rate,
            behaved_as_expected_rate=behaved_rate,
            should_have_avoided_rate=avoided_rate,
            should_have_waited_rate=waited_rate,
            outcome_distribution=self._outcome_distribution(results),
            discipline_breakdown=dict(discipline_breakdown),
            entry_breakdown=dict(entry_breakdown),
            confidence_calibration=calibration,
            warnings=[self._to_warning(w) for w in score.warnings],
            factors=[self._to_factor(f) for f in score.factors],
            rationale=list(score.rationale),
        )

    def _confidence_calibration(
        self,
        records: list[_Record],
        success_rate: float | None,
        min_sample: int,
    ) -> ConfidenceCalibration:
        buckets: list[ConfidenceBucketStat] = []
        qualifying: list[tuple[int, float]] = []
        for index, (name, lower, upper) in enumerate(CONFIDENCE_BUCKETS):
            bucket_results = [
                record.result
                for record in records
                if confidence_bucket(normalize_confidence(record.confidence)) == name
            ]
            bsize = len(bucket_results)
            insufficient = bsize < min_sample
            bucket_success = safe_rate(
                sum(1 for r in bucket_results if r.outcome == PaperValidationOutcome.SUCCESS.value),
                bsize,
            )
            buckets.append(
                ConfidenceBucketStat(
                    bucket=name,
                    lower=lower,
                    upper=min(upper, 1.0),
                    sample_size=bsize,
                    insufficient_data=insufficient,
                    success_rate=bucket_success,
                )
            )
            if not insufficient and bucket_success is not None:
                qualifying.append((index, bucket_success))

        mean_conf = mean_confidence([record.confidence for record in records])
        label = calibration_label(mean_conf, success_rate, len(records), min_sample)
        return ConfidenceCalibration(
            mean_confidence=mean_conf,
            mean_success_rate=success_rate,
            correlation=correlation_sign(qualifying),
            calibration_label=CalibrationLabel(label),
            buckets=buckets,
        )

    def _timeframe_stats(
        self,
        condition: str,
        records: list[_Record],
        min_sample: int,
    ) -> list[DetectorTimeframeStat]:
        by_timeframe: dict[str, list[_Record]] = defaultdict(list)
        for record in records:
            by_timeframe[record.session.timeframe or _UNKNOWN].append(record)

        stats = [
            DetectorTimeframeStat(
                condition=condition,
                timeframe=timeframe,
                sample_size=len(recs),
                insufficient_data=len(recs) < min_sample,
                invalidation_rate=safe_rate(
                    sum(1 for r in recs if r.result.invalidation_hit), len(recs)
                ),
                success_rate=safe_rate(
                    sum(
                        1 for r in recs if r.result.outcome == PaperValidationOutcome.SUCCESS.value
                    ),
                    len(recs),
                ),
            )
            for timeframe, recs in by_timeframe.items()
        ]
        stats.sort(key=lambda s: (-s.sample_size, s.timeframe))
        return stats

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
    def _summary_warnings(reports: list[DetectorQualityReport]) -> list[DetectorWarning]:
        if all(r.sample_size == 0 for r in reports):
            return [
                DetectorWarning(
                    code="no_validation_data",
                    message=(
                        "No validated results yet; detector quality will populate as you "
                        "record paper validation outcomes."
                    ),
                    severity="info",
                )
            ]
        empty = sorted(
            r.condition
            for r in reports
            if r.sample_size == 0 and r.condition in SETUP_DETECTOR_VERSIONS
        )
        if not empty:
            return []
        return [
            DetectorWarning(
                code="detectors_without_data",
                message=f"No validated results yet for: {', '.join(empty)}.",
                severity="info",
            )
        ]

    @staticmethod
    def _to_factor(factor: RawDetectorFactor) -> DetectorFactor:
        return DetectorFactor(
            code=factor.code,
            label=factor.label,
            direction=FactorDirection(factor.direction),
            contribution=factor.contribution,
            detail=factor.detail,
        )

    @staticmethod
    def _to_warning(warning: RawWarning) -> DetectorWarning:
        return DetectorWarning(
            code=warning.code,
            message=warning.message,
            severity=warning.severity,
        )

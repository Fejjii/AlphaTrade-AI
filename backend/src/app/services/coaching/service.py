"""Coaching read/save service (Slice 87 — record derived, no automation).

Live-computed coaching prompts from paper validation outcomes and learning
analytics. Read paths are side-effect free. Save persists into the existing
lesson candidate workflow only — never orders, proposals, approvals, execution,
exchange, engine, scanner, worker, or Telegram paths.
"""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import ColumnElement, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationAppError
from app.db.models import (
    LessonCandidate as LessonCandidateModel,
)
from app.db.models import (
    PaperValidationRunPlan,
    PaperValidationRunSession,
    PaperValidationSessionResult,
)
from app.schemas.analytics import AnalyticsDateRange
from app.schemas.coaching import (
    CategoryCount,
    CoachingCategory,
    CoachingExplainResponse,
    CoachingFactor,
    CoachingPrompt,
    CoachingPromptsResponse,
    CoachingSaveRequest,
    CoachingSource,
    CoachingSummaryResponse,
    SeverityCount,
)
from app.schemas.common import (
    LessonCandidateStatus,
    LessonSeverity,
    LessonSourceType,
    PaperValidationDisciplineAssessment,
    PaperValidationEntryAssessment,
    PaperValidationOutcome,
)
from app.schemas.lesson import LessonCandidate, LessonCandidateCreate
from app.schemas.validation_priority import FactorDirection, ReliabilityTier
from app.services.analytics.helpers import date_range_bounds
from app.services.coaching.rules import (
    _OVERCONFIDENCE_BUCKETS,
    CATEGORY_INVALIDATION_HIT,
    CATEGORY_LOW_QUALITY_SETUP,
    CATEGORY_MISSED_ENTRY,
    CATEGORY_OVERCONFIDENCE,
    CATEGORY_SHOULD_HAVE_AVOIDED,
    CATEGORY_SHOULD_HAVE_WAITED,
    CATEGORY_WEAK_CONFIDENCE_CORRELATION,
    CoachingBuildResult,
    RawPattern,
    build_coaching_prompt,
    coaching_signature,
    reliability_weight,
)
from app.services.learning_analytics.scoring import (
    CONFIDENCE_BUCKETS,
    confidence_bucket,
    correlation_sign,
    quality_score,
    safe_rate,
)
from app.services.learning_analytics.service import LearningAnalyticsService
from app.services.lesson_candidate_service import LessonCandidateService

_UNKNOWN = "unknown"
_GLOBAL_KEY = "all"
_DEFAULT_LIMIT = 20

_NOTE = (
    "Read-only coaching guidance for human discipline review only. Prompts say "
    "'review this behavior'; they do not enable automation, ordering, proposals, "
    "approvals, or execution."
)

_MISS_ENTRY_KINDS = frozenset(
    {
        PaperValidationEntryAssessment.MISSED_ENTRY.value,
        PaperValidationEntryAssessment.PRICE_MOVED_WITHOUT_ENTRY.value,
    }
)


class _Record:
    __slots__ = ("confidence", "result", "session")

    def __init__(
        self,
        session: PaperValidationRunSession,
        result: PaperValidationSessionResult,
        confidence: float | None,
    ) -> None:
        self.session = session
        self.result = result
        self.confidence = confidence


class CoachingService:
    """Compute coaching prompts and optionally journal them as lesson candidates."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._learning = LearningAnalyticsService(session)
        self._lessons = LessonCandidateService(session)

    def prompts(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
        start_date: date | None,
        end_date: date | None,
        min_sample: int,
        category: CoachingCategory | None,
        severity: LessonSeverity | None,
        limit: int,
        saved_lookup_user_id: uuid.UUID | None = None,
    ) -> CoachingPromptsResponse:
        records = self._load_records(
            organization_id=organization_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
        )
        built = self._build_prompts(records, min_sample=min_sample)
        if category is not None:
            built = [prompt for prompt in built if prompt.category == category]
        if severity is not None:
            built = [prompt for prompt in built if prompt.severity == severity]
        built.sort(
            key=lambda prompt: (-prompt.concern_score, prompt.category.value, prompt.signature)
        )
        saved_map = self._saved_signature_map(
            organization_id=organization_id,
            user_id=saved_lookup_user_id or user_id,
        )
        items = [
            self._attach_saved(prompt, saved_map.get(prompt.signature)) for prompt in built[:limit]
        ]
        return CoachingPromptsResponse(
            organization_id=organization_id,
            user_id=user_id,
            date_range=AnalyticsDateRange(start=start_date, end=end_date),
            min_sample=min_sample,
            note=_NOTE,
            total=len(built),
            items=items,
        )

    def summary(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
        start_date: date | None,
        end_date: date | None,
        min_sample: int,
        saved_lookup_user_id: uuid.UUID | None = None,
    ) -> CoachingSummaryResponse:
        records = self._load_records(
            organization_id=organization_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
        )
        built = self._build_prompts(records, min_sample=min_sample)
        category_counts = Counter(prompt.category for prompt in built)
        severity_counts = Counter(prompt.severity for prompt in built)
        pending_lessons = self._count_pending_coaching_lessons(
            organization_id=organization_id,
            user_id=saved_lookup_user_id or user_id,
        )
        top = built[0] if built else None
        saved_map = self._saved_signature_map(
            organization_id=organization_id,
            user_id=saved_lookup_user_id or user_id,
        )
        if top is not None:
            top = self._attach_saved(top, saved_map.get(top.signature))
        return CoachingSummaryResponse(
            organization_id=organization_id,
            user_id=user_id,
            date_range=AnalyticsDateRange(start=start_date, end=end_date),
            min_sample=min_sample,
            note=_NOTE,
            total_open=len(built),
            pending_coaching_lessons=pending_lessons,
            by_category=[
                CategoryCount(category=cat, count=category_counts.get(cat, 0))
                for cat in CoachingCategory
            ],
            by_severity=[
                SeverityCount(severity=sev, count=severity_counts.get(sev, 0))
                for sev in LessonSeverity
            ],
            top_prompt=top,
        )

    def explain(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
        start_date: date | None,
        end_date: date | None,
        min_sample: int,
        category: CoachingCategory,
        matched_key: str,
        saved_lookup_user_id: uuid.UUID | None = None,
    ) -> CoachingExplainResponse:
        records = self._load_records(
            organization_id=organization_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
        )
        built = self._build_prompts(records, min_sample=min_sample)
        matches = [
            prompt
            for prompt in built
            if prompt.category == category and prompt.source.matched_key == matched_key
        ]
        if not matches:
            raise NotFoundError("Coaching prompt not found for the requested pattern.")
        prompt = matches[0]
        saved_map = self._saved_signature_map(
            organization_id=organization_id,
            user_id=saved_lookup_user_id or user_id,
        )
        prompt = self._attach_saved(prompt, saved_map.get(prompt.signature))
        return CoachingExplainResponse(
            organization_id=organization_id,
            user_id=user_id,
            date_range=AnalyticsDateRange(start=start_date, end=end_date),
            min_sample=min_sample,
            note=_NOTE,
            prompt=prompt,
        )

    def save_prompt(
        self,
        body: CoachingSaveRequest,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> LessonCandidate:
        records = self._load_records(
            organization_id=organization_id,
            user_id=user_id,
            start_date=body.start_date,
            end_date=body.end_date,
        )
        built = self._build_prompts(records, min_sample=body.min_sample)
        signature = coaching_signature(
            category=body.category.value,
            matched_dimension=body.matched_dimension,
            matched_key=body.matched_key,
        )
        match = next((prompt for prompt in built if prompt.signature == signature), None)
        if match is None or match.insufficient_data:
            raise ValidationAppError(
                "Coaching pattern no longer qualifies; prompt was not saved.",
            )

        existing = self._find_saved_by_signature(
            organization_id=organization_id,
            user_id=user_id,
            signature=signature,
        )
        if existing is not None:
            return self._lessons._to_schema(existing)

        metadata = {
            "signature": signature,
            "category": body.category.value,
            "matched_dimension": body.matched_dimension,
            "matched_key": body.matched_key,
            "sample_size": match.source.sample_size,
            "reliability": match.reliability.value,
            "rate": match.source.rate,
            "source_session_ids": [str(sid) for sid in match.source.source_session_ids],
            "analytics_codes": match.source.analytics_codes,
            "date_range": {"start": body.start_date, "end": body.end_date},
            "min_sample": body.min_sample,
            "generated_at": datetime.now(tz=UTC).isoformat(),
        }
        if body.reviewer_note:
            metadata["reviewer_note"] = body.reviewer_note

        payload = LessonCandidateCreate(
            source_type=LessonSourceType.COACHING,
            source_id=None,
            lesson_text=match.prompt_text,
            mistake_type=body.category.value,
            severity=match.severity,
            confidence=Decimal(
                str(round(reliability_weight(match.source.sample_size, body.min_sample), 4))
            ),
            proposed_rule_update=None,
            analysis_metadata=metadata,
        )
        return self._lessons.create(payload, organization_id=organization_id, user_id=user_id)

    # -- internals -------------------------------------------------------

    def _load_records(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
        start_date: date | None,
        end_date: date | None,
    ) -> list[_Record]:
        start_dt, end_dt = date_range_bounds(start_date, end_date)
        conditions: list[ColumnElement[bool]] = [
            PaperValidationRunSession.organization_id == organization_id
        ]
        if user_id is not None:
            conditions.append(PaperValidationRunSession.started_by == user_id)
        if start_dt is not None:
            conditions.append(PaperValidationSessionResult.recorded_at >= start_dt)
        if end_dt is not None:
            conditions.append(PaperValidationSessionResult.recorded_at <= end_dt)

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
            .where(*conditions)
        )
        rows = self._session.execute(stmt).all()
        return [
            _Record(session_row, result_row, confidence)
            for session_row, result_row, confidence in rows
        ]

    def _build_prompts(self, records: list[_Record], *, min_sample: int) -> list[CoachingPrompt]:
        patterns = self._detect_patterns(records, min_sample=min_sample)
        prompts: list[CoachingPrompt] = []
        for pattern in patterns:
            built = build_coaching_prompt(pattern, min_sample=min_sample)
            if built is None:
                continue
            prompts.append(self._to_prompt(pattern, built))
        prompts.sort(
            key=lambda prompt: (-prompt.concern_score, prompt.category.value, prompt.signature)
        )
        return prompts

    def _detect_patterns(self, records: list[_Record], *, min_sample: int) -> list[RawPattern]:
        patterns: list[RawPattern] = []
        by_condition: dict[str, list[_Record]] = defaultdict(list)
        for record in records:
            by_condition[record.session.condition or _UNKNOWN].append(record)

        for condition, group in by_condition.items():
            if condition == _UNKNOWN:
                continue
            session_ids = tuple(str(record.session.id) for record in group)
            results = [record.result for record in group]
            size = len(results)

            missed = sum(
                1
                for record in group
                if record.result.outcome == PaperValidationOutcome.MISSED_ENTRY.value
                or record.result.entry_assessment in _MISS_ENTRY_KINDS
            )
            missed_rate = safe_rate(missed, size)
            if missed_rate is not None and size >= min_sample and missed_rate >= 0.3:
                patterns.append(
                    RawPattern(
                        category=CATEGORY_MISSED_ENTRY,
                        matched_dimension="condition",
                        matched_key=condition,
                        sample_size=size,
                        rate=missed_rate,
                        source_session_ids=session_ids,
                        analytics_codes=(
                            "misses_entries_on_strong_setups",
                            "price_moves_without_entry",
                        ),
                    )
                )

            waited = sum(
                1
                for r in results
                if r.discipline_assessment
                == PaperValidationDisciplineAssessment.SHOULD_HAVE_WAITED.value
            )
            waited_rate = safe_rate(waited, size)
            if size >= min_sample and waited_rate is not None and waited_rate >= 0.3:
                patterns.append(
                    RawPattern(
                        category=CATEGORY_SHOULD_HAVE_WAITED,
                        matched_dimension="condition",
                        matched_key=condition,
                        sample_size=size,
                        rate=waited_rate,
                        source_session_ids=session_ids,
                        analytics_codes=("should_have_waited_on_low_quality",),
                    )
                )

            avoided = sum(
                1
                for r in results
                if r.discipline_assessment
                == PaperValidationDisciplineAssessment.SHOULD_HAVE_AVOIDED.value
            )
            avoided_rate = safe_rate(avoided, size)
            failure_rate = safe_rate(
                sum(1 for r in results if r.outcome == PaperValidationOutcome.FAILURE.value),
                size,
            )
            if (
                size >= min_sample
                and avoided_rate is not None
                and avoided_rate >= 0.3
                and failure_rate is not None
                and failure_rate >= 0.3
            ):
                patterns.append(
                    RawPattern(
                        category=CATEGORY_SHOULD_HAVE_AVOIDED,
                        matched_dimension="condition",
                        matched_key=condition,
                        sample_size=size,
                        rate=avoided_rate,
                        source_session_ids=session_ids,
                        analytics_codes=("avoid_condition",),
                    )
                )

            invalidation = sum(
                1
                for r in results
                if r.invalidation_hit or r.outcome == PaperValidationOutcome.INVALIDATED.value
            )
            invalidation_rate = safe_rate(invalidation, size)
            if size >= min_sample and invalidation_rate is not None and invalidation_rate >= 0.3:
                patterns.append(
                    RawPattern(
                        category=CATEGORY_INVALIDATION_HIT,
                        matched_dimension="condition",
                        matched_key=condition,
                        sample_size=size,
                        rate=invalidation_rate,
                        source_session_ids=session_ids,
                        analytics_codes=("invalidation_prone_setup",),
                    )
                )

            success_rate = safe_rate(
                sum(1 for r in results if r.outcome == PaperValidationOutcome.SUCCESS.value),
                size,
            )
            behaved_values = [
                r.behaved_as_expected for r in results if r.behaved_as_expected is not None
            ]
            behaved_rate = safe_rate(sum(1 for v in behaved_values if v), len(behaved_values))
            invalidation_rate = safe_rate(sum(1 for r in results if r.invalidation_hit), size)
            avoided_rate_for_quality = safe_rate(avoided, size)
            q_score = quality_score(
                success_rate or 0.0,
                behaved_rate or 0.0,
                invalidation_rate or 0.0,
                avoided_rate_for_quality or 0.0,
            )
            if size >= min_sample and q_score < 50.0:
                low_quality_rate = round((100.0 - q_score) / 100.0, 4)
                patterns.append(
                    RawPattern(
                        category=CATEGORY_LOW_QUALITY_SETUP,
                        matched_dimension="condition",
                        matched_key=condition,
                        sample_size=size,
                        rate=low_quality_rate,
                        source_session_ids=session_ids,
                        analytics_codes=("low_quality_setup",),
                        quality_score=q_score,
                    )
                )

        for bucket_name in _OVERCONFIDENCE_BUCKETS:
            bucket_records = [
                record for record in records if confidence_bucket(record.confidence) == bucket_name
            ]
            if len(bucket_records) < min_sample:
                continue
            bucket_results = [record.result for record in bucket_records]
            session_ids = tuple(str(record.session.id) for record in bucket_records)
            success_rate = safe_rate(
                sum(1 for r in bucket_results if r.outcome == PaperValidationOutcome.SUCCESS.value),
                len(bucket_results),
            )
            miss_rate = safe_rate(
                sum(
                    1
                    for r in bucket_results
                    if r.outcome == PaperValidationOutcome.MISSED_ENTRY.value
                    or r.entry_assessment in _MISS_ENTRY_KINDS
                ),
                len(bucket_results),
            )
            concern_rate = miss_rate if success_rate is not None and success_rate < 0.5 else None
            if success_rate is not None and success_rate < 0.5:
                patterns.append(
                    RawPattern(
                        category=CATEGORY_OVERCONFIDENCE,
                        matched_dimension="confidence_bucket",
                        matched_key=bucket_name,
                        sample_size=len(bucket_records),
                        rate=1.0 - success_rate,
                        source_session_ids=session_ids,
                        analytics_codes=("overconfidence",),
                        success_rate=success_rate,
                    )
                )
            elif concern_rate is not None and concern_rate >= 0.3:
                patterns.append(
                    RawPattern(
                        category=CATEGORY_OVERCONFIDENCE,
                        matched_dimension="confidence_bucket",
                        matched_key=bucket_name,
                        sample_size=len(bucket_records),
                        rate=concern_rate,
                        source_session_ids=session_ids,
                        analytics_codes=("overconfidence",),
                        success_rate=success_rate,
                    )
                )

        qualifying: list[tuple[int, float]] = []
        total_qualifying = 0
        for index, (name, _lower, _upper) in enumerate(CONFIDENCE_BUCKETS):
            bucket_records = [
                record for record in records if confidence_bucket(record.confidence) == name
            ]
            if len(bucket_records) < min_sample:
                continue
            bucket_results = [record.result for record in bucket_records]
            success_rate = safe_rate(
                sum(1 for r in bucket_results if r.outcome == PaperValidationOutcome.SUCCESS.value),
                len(bucket_results),
            )
            if success_rate is not None:
                qualifying.append((index, success_rate))
                total_qualifying += len(bucket_records)

        correlation = correlation_sign(qualifying)
        if total_qualifying >= min_sample and correlation in ("none", "negative"):
            patterns.append(
                RawPattern(
                    category=CATEGORY_WEAK_CONFIDENCE_CORRELATION,
                    matched_dimension="global",
                    matched_key=_GLOBAL_KEY,
                    sample_size=total_qualifying,
                    rate=0.5 if correlation == "none" else 0.6,
                    source_session_ids=tuple(str(record.session.id) for record in records[:20]),
                    analytics_codes=("confidence_correlation",),
                    correlation=correlation,
                )
            )

        return patterns

    @staticmethod
    def _to_prompt(pattern: RawPattern, built: CoachingBuildResult) -> CoachingPrompt:
        return CoachingPrompt(
            signature=built.signature,
            category=CoachingCategory(built.category),
            title=built.title,
            prompt_text=built.prompt_text,
            severity=LessonSeverity(built.severity),
            reliability=ReliabilityTier(built.reliability),
            concern_score=built.concern_score,
            insufficient_data=built.insufficient_data,
            source=CoachingSource(
                matched_dimension=pattern.matched_dimension,
                matched_key=pattern.matched_key,
                sample_size=pattern.sample_size,
                source_session_ids=[uuid.UUID(sid) for sid in pattern.source_session_ids],
                analytics_codes=list(pattern.analytics_codes),
                rate=pattern.rate,
            ),
            factors=[
                CoachingFactor(
                    code=factor.code,
                    label=factor.label,
                    direction=FactorDirection(factor.direction),
                    contribution=factor.contribution,
                    detail=factor.detail,
                )
                for factor in built.factors
            ],
            rationale=list(built.rationale),
        )

    def _saved_signature_map(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
    ) -> dict[str, uuid.UUID]:
        if user_id is None:
            return {}
        rows = self._session.scalars(
            select(LessonCandidateModel).where(
                LessonCandidateModel.organization_id == organization_id,
                LessonCandidateModel.user_id == user_id,
                LessonCandidateModel.source_type == LessonSourceType.COACHING.value,
                LessonCandidateModel.status == LessonCandidateStatus.PENDING_REVIEW.value,
            )
        ).all()
        mapping: dict[str, uuid.UUID] = {}
        for row in rows:
            metadata = row.analysis_metadata or {}
            signature = metadata.get("signature")
            if isinstance(signature, str):
                mapping[signature] = row.id
        return mapping

    def _find_saved_by_signature(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        signature: str,
    ) -> LessonCandidateModel | None:
        rows = self._session.scalars(
            select(LessonCandidateModel).where(
                LessonCandidateModel.organization_id == organization_id,
                LessonCandidateModel.user_id == user_id,
                LessonCandidateModel.source_type == LessonSourceType.COACHING.value,
                LessonCandidateModel.status == LessonCandidateStatus.PENDING_REVIEW.value,
            )
        ).all()
        for row in rows:
            metadata = row.analysis_metadata or {}
            if metadata.get("signature") == signature:
                return row
        return None

    def _count_pending_coaching_lessons(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
    ) -> int:
        if user_id is None:
            return 0
        stmt = select(LessonCandidateModel).where(
            LessonCandidateModel.organization_id == organization_id,
            LessonCandidateModel.user_id == user_id,
            LessonCandidateModel.source_type == LessonSourceType.COACHING.value,
            LessonCandidateModel.status == LessonCandidateStatus.PENDING_REVIEW.value,
        )
        return len(list(self._session.scalars(stmt).all()))

    @staticmethod
    def _attach_saved(prompt: CoachingPrompt, lesson_id: uuid.UUID | None) -> CoachingPrompt:
        if lesson_id is None:
            return prompt
        return prompt.model_copy(update={"already_saved_lesson_id": lesson_id})

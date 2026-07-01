"""Validation prioritization read service (Slice 85 — record derived, no automation).

Live-computed ranking of pending paper validation run plans and candidates. This
service only reads existing records and returns derived study guidance. It never
mutates data and never touches order, proposal, approval, execution, exchange,
engine, scanner, worker, or Telegram code paths, and never starts a validation
session.
"""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from datetime import date, datetime

from sqlalchemy import ColumnElement, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.db.models import (
    PaperValidationCandidate,
    PaperValidationRunPlan,
    PaperValidationRunSession,
    PaperValidationSessionResult,
)
from app.schemas.analytics import AnalyticsDateRange
from app.schemas.common import (
    PaperValidationCandidateStatus,
    PaperValidationDisciplineAssessment,
    PaperValidationOutcome,
    PaperValidationRunPlanStatus,
)
from app.schemas.validation_priority import (
    ActionLabelCount,
    FactorDirection,
    PriorityFactor,
    PriorityItemType,
    ReliabilityCount,
    ReliabilityTier,
    ValidationActionLabel,
    ValidationPriorityExplainResponse,
    ValidationPriorityItem,
    ValidationPriorityQueueResponse,
    ValidationPrioritySummaryResponse,
)
from app.services.analytics.helpers import date_range_bounds
from app.services.learning_analytics.scoring import (
    confidence_bucket,
    quality_score,
    safe_rate,
)
from app.services.learning_analytics.service import LearningAnalyticsService
from app.services.validation_priority.scoring import (
    HistoryStats,
    ItemContext,
    RawFactor,
    compute_priority,
)

_GLOBAL_KEY = "all"
_UNKNOWN = "unknown"
_DEFAULT_LIMIT = 20

_NOTE = (
    "Read-only validation prioritization for human study only. Action labels are "
    "guidance for what to validate next; they do not enable automation, ordering, "
    "proposals, approvals, or execution."
)

_PENDING_CANDIDATE_STATUSES = (
    PaperValidationCandidateStatus.QUEUED.value,
    PaperValidationCandidateStatus.REVIEWING.value,
)


class ValidationPriorityService:
    """Compute read-only validation priorities for a tenant."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._learning = LearningAnalyticsService(session)

    # -- public ----------------------------------------------------------

    def queue(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
        start_date: date | None,
        end_date: date | None,
        min_sample: int,
        item_type: PriorityItemType | None,
        limit: int,
    ) -> ValidationPriorityQueueResponse:
        items = self._score_all(
            organization_id=organization_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            min_sample=min_sample,
            item_type=item_type,
        )
        return ValidationPriorityQueueResponse(
            organization_id=organization_id,
            user_id=user_id,
            date_range=AnalyticsDateRange(start=start_date, end=end_date),
            min_sample=min_sample,
            note=_NOTE,
            item_type_filter=item_type,
            limit=limit,
            total_pending=len(items),
            items=items[:limit],
        )

    def summary(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
        start_date: date | None,
        end_date: date | None,
        min_sample: int,
    ) -> ValidationPrioritySummaryResponse:
        items = self._score_all(
            organization_id=organization_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            min_sample=min_sample,
            item_type=None,
        )
        action_counts = Counter(item.action_label for item in items)
        reliability_counts = Counter(item.reliability for item in items)
        run_plans = sum(1 for item in items if item.item_type is PriorityItemType.RUN_PLAN)
        candidates = sum(1 for item in items if item.item_type is PriorityItemType.CANDIDATE)

        return ValidationPrioritySummaryResponse(
            organization_id=organization_id,
            user_id=user_id,
            date_range=AnalyticsDateRange(start=start_date, end=end_date),
            min_sample=min_sample,
            note=_NOTE,
            total_pending=len(items),
            run_plans_pending=run_plans,
            candidates_pending=candidates,
            by_action=[
                ActionLabelCount(action_label=label, count=action_counts.get(label, 0))
                for label in ValidationActionLabel
            ],
            by_reliability=[
                ReliabilityCount(reliability=tier, count=reliability_counts.get(tier, 0))
                for tier in ReliabilityTier
            ],
        )

    def explain(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
        start_date: date | None,
        end_date: date | None,
        min_sample: int,
        item_type: PriorityItemType,
        item_id: uuid.UUID,
    ) -> ValidationPriorityExplainResponse:
        history_index, global_stats, correlation = self._history_context(
            organization_id=organization_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
        )
        row = self._load_single_pending(
            organization_id=organization_id,
            user_id=user_id,
            item_type=item_type,
            item_id=item_id,
        )
        if row is None:
            raise NotFoundError("Pending item not found.")
        item = self._score_row(
            item_type=item_type,
            row=row,
            history_index=history_index,
            global_stats=global_stats,
            correlation=correlation,
            min_sample=min_sample,
        )
        return ValidationPriorityExplainResponse(
            organization_id=organization_id,
            user_id=user_id,
            date_range=AnalyticsDateRange(start=start_date, end=end_date),
            min_sample=min_sample,
            note=_NOTE,
            item=item,
        )

    # -- internals -------------------------------------------------------

    def _score_all(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
        start_date: date | None,
        end_date: date | None,
        min_sample: int,
        item_type: PriorityItemType | None,
    ) -> list[ValidationPriorityItem]:
        history_index, global_stats, correlation = self._history_context(
            organization_id=organization_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
        )
        items: list[ValidationPriorityItem] = []
        for row_type, row in self._pending_rows(
            organization_id=organization_id, user_id=user_id, item_type=item_type
        ):
            items.append(
                self._score_row(
                    item_type=row_type,
                    row=row,
                    history_index=history_index,
                    global_stats=global_stats,
                    correlation=correlation,
                    min_sample=min_sample,
                )
            )
        items.sort(key=lambda item: (-item.priority_score, item.item_type.value, str(item.item_id)))
        return items

    def _pending_rows(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
        item_type: PriorityItemType | None,
    ) -> list[tuple[PriorityItemType, PaperValidationRunPlan | PaperValidationCandidate]]:
        rows: list[tuple[PriorityItemType, PaperValidationRunPlan | PaperValidationCandidate]] = []
        if item_type in (None, PriorityItemType.RUN_PLAN):
            stmt = select(PaperValidationRunPlan).where(
                PaperValidationRunPlan.organization_id == organization_id,
                PaperValidationRunPlan.plan_status == PaperValidationRunPlanStatus.PLANNED.value,
            )
            if user_id is not None:
                stmt = stmt.where(PaperValidationRunPlan.created_by == user_id)
            rows.extend(
                (PriorityItemType.RUN_PLAN, plan)
                for plan in self._session.execute(stmt).scalars().all()
            )
        if item_type in (None, PriorityItemType.CANDIDATE):
            stmt = select(PaperValidationCandidate).where(
                PaperValidationCandidate.organization_id == organization_id,
                PaperValidationCandidate.candidate_status.in_(_PENDING_CANDIDATE_STATUSES),
            )
            if user_id is not None:
                stmt = stmt.where(PaperValidationCandidate.created_by == user_id)
            rows.extend(
                (PriorityItemType.CANDIDATE, candidate)
                for candidate in self._session.execute(stmt).scalars().all()
            )
        return rows

    def _load_single_pending(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
        item_type: PriorityItemType,
        item_id: uuid.UUID,
    ) -> PaperValidationRunPlan | PaperValidationCandidate | None:
        if item_type is PriorityItemType.RUN_PLAN:
            stmt = select(PaperValidationRunPlan).where(
                PaperValidationRunPlan.organization_id == organization_id,
                PaperValidationRunPlan.id == item_id,
                PaperValidationRunPlan.plan_status == PaperValidationRunPlanStatus.PLANNED.value,
            )
            if user_id is not None:
                stmt = stmt.where(PaperValidationRunPlan.created_by == user_id)
        else:
            stmt = select(PaperValidationCandidate).where(
                PaperValidationCandidate.organization_id == organization_id,
                PaperValidationCandidate.id == item_id,
                PaperValidationCandidate.candidate_status.in_(_PENDING_CANDIDATE_STATUSES),
            )
            if user_id is not None:
                stmt = stmt.where(PaperValidationCandidate.created_by == user_id)
        return self._session.execute(stmt).scalars().first()

    def _score_row(
        self,
        *,
        item_type: PriorityItemType,
        row: PaperValidationRunPlan | PaperValidationCandidate,
        history_index: dict[str, dict[str, HistoryStats]],
        global_stats: HistoryStats,
        correlation: str,
        min_sample: int,
    ) -> ValidationPriorityItem:
        matched_dimension, matched_key, history = self._match_history(
            row=row, history_index=history_index, global_stats=global_stats
        )
        bucket = confidence_bucket(row.confidence)
        context = ItemContext(
            confidence=row.confidence,
            confidence_bucket=bucket,
            readiness=self._readiness(row.checklist_snapshot),
        )
        breakdown = compute_priority(
            history,
            context,
            min_sample=min_sample,
            confidence_correlation=correlation,
        )
        current_status = (
            row.plan_status if item_type is PriorityItemType.RUN_PLAN else row.candidate_status
        )
        return ValidationPriorityItem(
            item_type=item_type,
            item_id=row.id,
            symbol=row.symbol,
            condition=row.condition,
            timeframe=row.timeframe,
            direction=row.direction,
            confidence=row.confidence,
            confidence_bucket=bucket,
            current_status=current_status,
            priority_score=breakdown.score,
            action_label=ValidationActionLabel(breakdown.action_label),
            reliability=ReliabilityTier(breakdown.reliability),
            matched_dimension=matched_dimension,
            matched_key=matched_key,
            matched_sample_size=history.sample_size,
            historical_success_rate=history.success_rate,
            historical_invalidation_rate=history.invalidation_hit_rate,
            factors=[self._to_factor(factor) for factor in breakdown.factors],
            rationale=list(breakdown.rationale),
        )

    @staticmethod
    def _match_history(
        *,
        row: PaperValidationRunPlan | PaperValidationCandidate,
        history_index: dict[str, dict[str, HistoryStats]],
        global_stats: HistoryStats,
    ) -> tuple[str, str, HistoryStats]:
        condition = row.condition
        if condition and condition in history_index["condition"]:
            return "condition", condition, history_index["condition"][condition]
        symbol = row.symbol
        if symbol and symbol in history_index["symbol"]:
            return "symbol", symbol, history_index["symbol"][symbol]
        return "global", _GLOBAL_KEY, global_stats

    @staticmethod
    def _readiness(checklist_snapshot: dict | None) -> float:
        if not checklist_snapshot:
            return 0.0
        values = [bool(v) for v in checklist_snapshot.values() if isinstance(v, bool)]
        if not values:
            return 0.0
        return sum(values) / len(values)

    @staticmethod
    def _to_factor(factor: RawFactor) -> PriorityFactor:
        return PriorityFactor(
            code=factor.code,
            label=factor.label,
            direction=FactorDirection(factor.direction),
            contribution=factor.contribution,
            detail=factor.detail,
        )

    def _history_context(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
        start_date: date | None,
        end_date: date | None,
    ) -> tuple[dict[str, dict[str, HistoryStats]], HistoryStats, str]:
        start_dt, end_dt = date_range_bounds(start_date, end_date)
        records = self._load_result_rows(
            organization_id=organization_id,
            user_id=user_id,
            start_dt=start_dt,
            end_dt=end_dt,
        )
        by_condition: dict[str, list[PaperValidationSessionResult]] = defaultdict(list)
        by_symbol: dict[str, list[PaperValidationSessionResult]] = defaultdict(list)
        all_results: list[PaperValidationSessionResult] = []
        for session, result in records:
            all_results.append(result)
            by_condition[session.condition or _UNKNOWN].append(result)
            by_symbol[session.symbol or _UNKNOWN].append(result)

        history_index = {
            "condition": {key: self._history_stats(rows) for key, rows in by_condition.items()},
            "symbol": {key: self._history_stats(rows) for key, rows in by_symbol.items()},
        }
        global_stats = self._history_stats(all_results)
        correlation = self._learning.confidence_outcome(
            organization_id=organization_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            min_sample=1,
        ).correlation
        return history_index, global_stats, correlation

    def _load_result_rows(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
        start_dt: datetime | None,
        end_dt: datetime | None,
    ) -> list[tuple[PaperValidationRunSession, PaperValidationSessionResult]]:
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
            select(PaperValidationRunSession, PaperValidationSessionResult)
            .join(
                PaperValidationSessionResult,
                PaperValidationSessionResult.run_session_id == PaperValidationRunSession.id,
            )
            .where(*conditions)
        )
        return [(row[0], row[1]) for row in self._session.execute(stmt).all()]

    @staticmethod
    def _history_stats(results: list[PaperValidationSessionResult]) -> HistoryStats:
        size = len(results)
        if size == 0:
            return HistoryStats()
        counts = Counter(r.outcome for r in results)
        success_rate = safe_rate(counts.get(PaperValidationOutcome.SUCCESS.value, 0), size)
        invalidation_rate = safe_rate(sum(1 for r in results if r.invalidation_hit), size)
        behaved_values = [
            r.behaved_as_expected for r in results if r.behaved_as_expected is not None
        ]
        behaved_rate = safe_rate(sum(1 for v in behaved_values if v), len(behaved_values))
        avoided_rate = safe_rate(
            sum(
                1
                for r in results
                if r.discipline_assessment
                == PaperValidationDisciplineAssessment.SHOULD_HAVE_AVOIDED.value
            ),
            size,
        )
        quality = quality_score(
            success_rate or 0.0,
            behaved_rate or 0.0,
            invalidation_rate or 0.0,
            avoided_rate or 0.0,
        )
        return HistoryStats(
            sample_size=size,
            quality_score=quality,
            success_rate=success_rate,
            invalidation_hit_rate=invalidation_rate,
            should_have_avoided_rate=avoided_rate,
        )

"""Facade for analytics API, agent tool, and summary exports."""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import date

from sqlalchemy.orm import Session

from app.schemas.analytics import (
    AnalyticsDateRange,
    AnalyticsSummaryRequest,
    AnalyticsSummaryToolOutput,
    SetupAnalyticsResponse,
)
from app.schemas.common import SetupType
from app.services.analytics.discipline_score import DisciplineScoreService
from app.services.analytics.risk_behavior import RiskBehaviorAnalyticsService
from app.services.analytics.setup_statistics import SetupStatisticsService
from app.services.analytics.trade_review import TradeReviewAnalyticsService


class TradingAnalyticsFacade:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._setups = SetupStatisticsService(session)
        self._review = TradeReviewAnalyticsService(session)
        self._discipline = DisciplineScoreService(session)
        self._risk = RiskBehaviorAnalyticsService(session)

    def setup_analytics(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        start_date: date | None = None,
        end_date: date | None = None,
        setup_type: SetupType | None = None,
    ) -> SetupAnalyticsResponse:
        setups = self._setups.compute(
            organization_id=organization_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            setup_type_filter=setup_type,
        )
        return SetupAnalyticsResponse(
            organization_id=organization_id,
            user_id=user_id,
            setup_type_filter=setup_type,
            date_range=AnalyticsDateRange(start=start_date, end=end_date),
            setups=setups,
        )

    def trade_review(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        start_date: date | None = None,
        end_date: date | None = None,
    ):
        return self._review.compute(
            organization_id=organization_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
        )

    def discipline(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        start_date: date | None = None,
        end_date: date | None = None,
    ):
        return self._discipline.compute(
            organization_id=organization_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
        )

    def risk_behavior(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        start_date: date | None = None,
        end_date: date | None = None,
    ):
        return self._risk.compute(
            organization_id=organization_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
        )

    def summary_tool(self, request: AnalyticsSummaryRequest) -> AnalyticsSummaryToolOutput:
        if request.organization_id is None or request.user_id is None:
            raise ValueError("organization_id and user_id are required")

        setups = self._setups.compute(
            organization_id=request.organization_id,
            user_id=request.user_id,
            start_date=request.start_date,
            end_date=request.end_date,
            setup_type_filter=SetupType(request.setup_type.value) if request.setup_type else None,
        )
        discipline = self._discipline.compute(
            organization_id=request.organization_id,
            user_id=request.user_id,
            start_date=request.start_date,
            end_date=request.end_date,
        )
        review = self._review.compute(
            organization_id=request.organization_id,
            user_id=request.user_id,
            start_date=request.start_date,
            end_date=request.end_date,
        )

        from app.services.analytics.helpers import load_journals

        journals = load_journals(
            self._session,
            organization_id=request.organization_id,
            user_id=request.user_id,
            start_dt=None,
            end_dt=None,
            setup_type=SetupType(request.setup_type.value) if request.setup_type else None,
        )
        mistake_counter: Counter[str] = Counter()
        emotion_counter: Counter[str] = Counter()
        improvements: list[str] = list(discipline.improvement_suggestions)
        for entry in journals:
            mistake_counter.update(entry.mistakes or [])
            emotion_counter.update(entry.emotions or [])
            if entry.improvement_rule and entry.improvement_rule not in improvements:
                improvements.append(entry.improvement_rule)

        return AnalyticsSummaryToolOutput(
            setup_statistics=setups,
            discipline_summary=discipline,
            repeated_mistakes=[m for m, _ in mistake_counter.most_common(8)],
            repeated_emotions=[e for e, _ in emotion_counter.most_common(8)],
            improvement_suggestions=improvements[:10],
            trade_review=review,
        )

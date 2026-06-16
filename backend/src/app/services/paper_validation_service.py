"""Paper validation service with metrics (Slice 35 — paper only)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.db.models import PaperValidationRun as PaperValidationRunModel
from app.db.models import Position as PositionModel
from app.db.models import TradeProposal
from app.repositories.paper_validation import PaperValidationRunRepository
from app.repositories.strategy_library import UserStrategyRepository, UserStrategyVersionRepository
from app.schemas.common import (
    PaperValidationRecommendation,
    PaperValidationStatus,
    StrategyValidationStatus,
)
from app.schemas.paper_validation import (
    PaperValidationMetrics,
    PaperValidationRun,
    PaperValidationSummary,
)


class PaperValidationService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._runs = PaperValidationRunRepository(session)
        self._strategies = UserStrategyRepository(session)
        self._versions = UserStrategyVersionRepository(session)

    def start(
        self,
        strategy_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> PaperValidationRun:
        strategy = self._strategies.get_scoped(
            strategy_id, organization_id=organization_id, user_id=user_id
        )
        if strategy is None:
            raise NotFoundError("Strategy not found.")

        version = self._versions.latest(strategy_id)
        eligible = strategy.paper_eligible or (
            version is not None
            and version.validation_status
            in {StrategyValidationStatus.VALIDATED, StrategyValidationStatus.IN_REVIEW}
        )
        if version is not None:
            version.paper_validation_status = PaperValidationStatus.IN_PROGRESS

        metrics = self._aggregate_metrics(strategy_id, organization_id=organization_id)
        recommendation = self._recommend(metrics, eligible=eligible)

        run = PaperValidationRunModel(
            strategy_id=strategy_id,
            organization_id=organization_id,
            user_id=user_id,
            status=PaperValidationStatus.IN_PROGRESS,
            paper_eligible=eligible,
            notes="Paper validation tracking — simulated paper trades only, no exchange orders.",
            metrics=metrics.model_dump(mode="json"),
            recommendation=recommendation.value,
        )
        self._runs.add(run)
        return self._to_schema(run)

    def get_run(
        self,
        strategy_id: uuid.UUID,
        run_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> PaperValidationRun:
        strategy = self._strategies.get_scoped(
            strategy_id, organization_id=organization_id, user_id=user_id
        )
        if strategy is None:
            raise NotFoundError("Strategy not found.")
        row = self._runs.get_scoped(run_id, organization_id=organization_id)
        if row is None or row.strategy_id != strategy_id:
            raise NotFoundError("Paper validation run not found.")
        return self._to_schema(row)

    def refresh_metrics(
        self,
        run_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
    ) -> PaperValidationRun:
        row = self._runs.get_scoped(run_id, organization_id=organization_id)
        if row is None:
            raise NotFoundError("Paper validation run not found.")
        metrics = self._aggregate_metrics(row.strategy_id, organization_id=organization_id)
        recommendation = self._recommend(metrics, eligible=row.paper_eligible)
        row.metrics = metrics.model_dump(mode="json")
        row.recommendation = recommendation.value
        if metrics.paper_trades_count >= 10:
            row.status = (
                PaperValidationStatus.PASSED
                if metrics.expectancy > 0 and metrics.profit_factor >= 1.0
                else PaperValidationStatus.FAILED
            )
            row.ended_at = datetime.now(UTC)
        return self._to_schema(row)

    def list_for_strategy(
        self,
        strategy_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> PaperValidationSummary:
        strategy = self._strategies.get_scoped(
            strategy_id, organization_id=organization_id, user_id=user_id
        )
        if strategy is None:
            raise NotFoundError("Strategy not found.")

        version = self._versions.latest(strategy_id)
        rows, total = self._runs.list_for_strategy(
            strategy_id, organization_id=organization_id, limit=limit, offset=offset
        )
        latest_status = version.paper_validation_status if version else None
        return PaperValidationSummary(
            strategy_id=strategy_id,
            paper_eligible=strategy.paper_eligible,
            latest_status=latest_status,
            runs=[self._to_schema(row) for row in rows],
            total=total,
        )

    def _aggregate_metrics(
        self,
        strategy_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
    ) -> PaperValidationMetrics:
        positions = list(
            self._session.scalars(
                select(PositionModel)
                .join(TradeProposal, PositionModel.linked_proposal_id == TradeProposal.id)
                .where(
                    TradeProposal.user_strategy_id == strategy_id,
                    PositionModel.organization_id == organization_id,
                )
            ).all()
        )
        if not positions:
            return PaperValidationMetrics(
                paper_trades_count=0,
                win_rate=0.0,
                net_pnl=Decimal("0"),
                profit_factor=0.0,
                expectancy=Decimal("0"),
                max_drawdown_pct=0.0,
            )

        pnls = [p.realized_pnl or Decimal("0") for p in positions if p.status.value == "closed"]
        if not pnls:
            pnls = [Decimal("0") for _ in positions]

        wins = [p for p in pnls if p > 0]
        losses = [abs(p) for p in pnls if p <= 0]
        gross_profit = sum(wins, Decimal("0"))
        gross_loss = sum(losses, Decimal("0"))
        pf = float(gross_profit / gross_loss) if gross_loss > 0 else float(gross_profit)
        net = sum(pnls, Decimal("0"))
        count = len(pnls)

        return PaperValidationMetrics(
            paper_trades_count=count,
            win_rate=len(wins) / count if count else 0.0,
            net_pnl=net,
            profit_factor=pf,
            expectancy=net / Decimal(str(count)) if count else Decimal("0"),
            max_drawdown_pct=0.0,
            plan_adherence_avg=None,
            early_exit_count=0,
            stop_respected_count=0,
        )

    @staticmethod
    def _recommend(
        metrics: PaperValidationMetrics,
        *,
        eligible: bool,
    ) -> PaperValidationRecommendation:
        if metrics.paper_trades_count == 0:
            return PaperValidationRecommendation.INSUFFICIENT_DATA
        if not eligible:
            return PaperValidationRecommendation.RESTRICT
        if metrics.expectancy <= 0 or metrics.profit_factor < 1.0:
            return PaperValidationRecommendation.IMPROVE
        if metrics.win_rate >= 0.45 and metrics.profit_factor >= 1.1:
            return PaperValidationRecommendation.CONTINUE
        return PaperValidationRecommendation.IMPROVE

    @staticmethod
    def _to_schema(row: PaperValidationRunModel) -> PaperValidationRun:
        metrics = None
        if row.metrics:
            metrics = PaperValidationMetrics.model_validate(row.metrics)
        recommendation = None
        if row.recommendation:
            recommendation = PaperValidationRecommendation(row.recommendation)
        return PaperValidationRun(
            id=row.id,
            strategy_id=row.strategy_id,
            organization_id=row.organization_id,
            user_id=row.user_id,
            status=row.status,
            paper_eligible=row.paper_eligible,
            notes=row.notes,
            ended_at=row.ended_at,
            metrics=metrics,
            recommendation=recommendation,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

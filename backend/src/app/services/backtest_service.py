"""Backtest service (Slice 35 — deterministic engine v1, paper only)."""

from __future__ import annotations

import uuid
from contextlib import suppress

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import NotFoundError
from app.db.models import BacktestRun as BacktestRunModel
from app.providers.factory import resolve_market_data_provider
from app.repositories.backtest import BacktestRunRepository
from app.repositories.backtest_trades import BacktestTradeRepository
from app.repositories.strategy_library import UserStrategyRepository, UserStrategyVersionRepository
from app.schemas.backtest import (
    BacktestAssumptions,
    BacktestResult,
    BacktestRun,
    BacktestRunCreate,
    BacktestTradeRecord,
    PaginatedBacktestTrades,
)
from app.schemas.common import (
    BacktestRecommendation,
    BacktestRunStatus,
    PaperValidationStatus,
    TradeDirection,
)
from app.schemas.strategy_library import StrategyCard
from app.schemas.structured_rules import StructuredRules
from app.services.backtest_engine_service import BacktestEngineService
from app.services.historical_candle_service import HistoricalCandleService
from app.services.strategy_promotion import evaluate_promotion


class BacktestService:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._runs = BacktestRunRepository(session)
        self._trades = BacktestTradeRepository(session)
        self._strategies = UserStrategyRepository(session)
        self._versions = UserStrategyVersionRepository(session)
        provider = resolve_market_data_provider(self._settings)
        self._engine = BacktestEngineService(
            session,
            HistoricalCandleService(session, provider, self._settings),
        )

    def create(
        self,
        strategy_id: uuid.UUID,
        payload: BacktestRunCreate,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> BacktestRun:
        strategy = self._strategies.get_scoped(
            strategy_id, organization_id=organization_id, user_id=user_id
        )
        if strategy is None:
            raise NotFoundError("Strategy not found.")

        version = (
            self._versions.get_by_id(payload.strategy_version_id)
            if payload.strategy_version_id
            else self._versions.latest(strategy_id)
        )
        assumptions = payload.assumptions or BacktestAssumptions()

        run = BacktestRunModel(
            strategy_id=strategy_id,
            strategy_version_id=version.id if version else None,
            organization_id=organization_id,
            user_id=user_id,
            status=BacktestRunStatus.RUNNING,
            assumptions=assumptions.model_dump(mode="json"),
        )
        self._runs.add(run)
        self._session.flush()

        try:
            card = StrategyCard.model_validate(version.card) if version else None
            if card is None:
                run.status = BacktestRunStatus.FAILED
                run.error_message = "Strategy version or card not found."
                return self._to_schema(run)

            structured: StructuredRules | None = None
            if version and version.structured_rules:
                with suppress(Exception):
                    structured = StructuredRules.model_validate(version.structured_rules)

            result = self._engine.run(
                run=run,
                card=card,
                setup_type=strategy.setup_type,
                structured_rules=structured,
            )
            run.result = result.model_dump(mode="json")
            run.status = BacktestRunStatus.COMPLETED
            needs_rules = BacktestRecommendation.NEEDS_STRUCTURED_RULES
            if version is not None and result.recommendation != needs_rules:
                promotion = evaluate_promotion(
                    metrics=result.metrics,
                    machine_readable=(
                        result.recommendation != BacktestRecommendation.NEEDS_STRUCTURED_RULES
                    ),
                    data_quality=result.data_quality,
                    meets_success_criteria=result.meets_success_criteria,
                )
                version.backtest_status = promotion.backtest_status
                if promotion.validation_status is not None:
                    version.validation_status = promotion.validation_status
                strategy.paper_eligible = promotion.paper_eligible
                if promotion.paper_eligible:
                    version.paper_validation_status = PaperValidationStatus.NOT_STARTED
        except Exception as exc:
            run.status = BacktestRunStatus.FAILED
            run.error_message = str(exc)

        return self._to_schema(run)

    def list_for_strategy(
        self,
        strategy_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[BacktestRun], int]:
        strategy = self._strategies.get_scoped(
            strategy_id, organization_id=organization_id, user_id=user_id
        )
        if strategy is None:
            raise NotFoundError("Strategy not found.")
        rows, total = self._runs.list_for_strategy(
            strategy_id, organization_id=organization_id, limit=limit, offset=offset
        )
        return [self._to_schema(row) for row in rows], total

    def get(
        self,
        run_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
    ) -> BacktestRun:
        row = self._runs.get_scoped(run_id, organization_id=organization_id)
        if row is None:
            raise NotFoundError("Backtest run not found.")
        return self._to_schema(row)

    def list_trades(
        self,
        run_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        limit: int = 200,
        offset: int = 0,
    ) -> PaginatedBacktestTrades:
        row = self._runs.get_scoped(run_id, organization_id=organization_id)
        if row is None:
            raise NotFoundError("Backtest run not found.")
        rows, total = self._trades.list_for_run(run_id, limit=limit, offset=offset)
        items = [
            BacktestTradeRecord(
                id=trade.id,
                entry_time=trade.entry_time,
                exit_time=trade.exit_time,
                direction=TradeDirection(trade.direction),
                entry_price=trade.entry_price,
                exit_price=trade.exit_price,
                stop_loss=trade.stop_loss,
                size=trade.size,
                fees=trade.fees,
                slippage_cost=trade.slippage_cost,
                gross_pnl=trade.gross_pnl,
                net_pnl=trade.net_pnl,
                tp_hit_status=trade.tp_hit_status,
                exit_reason=trade.exit_reason,
                rule_notes=trade.rule_notes,
            )
            for trade in rows
        ]
        return PaginatedBacktestTrades(items=items, total=total, limit=limit, offset=offset)

    @staticmethod
    def _to_schema(row: BacktestRunModel) -> BacktestRun:
        assumptions = BacktestAssumptions.model_validate(row.assumptions or {})
        result = None
        if row.result:
            result = BacktestResult.model_validate(row.result)
        return BacktestRun(
            id=row.id,
            strategy_id=row.strategy_id,
            strategy_version_id=row.strategy_version_id,
            organization_id=row.organization_id,
            user_id=row.user_id,
            status=row.status,
            assumptions=assumptions,
            result=result,
            error_message=row.error_message,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

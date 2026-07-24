"""Setup evidence tiers from backtest OOS + non-backtest journal confirmation (AT-034).

Read-only and advisory only — never feeds execution or risk decisions.
No new tables; no persistence.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import BacktestRun as BacktestRunModel
from app.db.models import UserStrategy, UserStrategyVersion
from app.repositories.journal_trades import JournalTradeRepository
from app.schemas.backtest import (
    SetupEvidenceItem,
    SetupEvidenceMeasured,
    SetupEvidenceResponse,
    SetupEvidenceThresholds,
    SetupEvidenceTier,
)
from app.schemas.common import BacktestRunStatus, JournalTradeSource
from app.services.journal_statistics_service import _compute_metrics


class SetupEvidenceService:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._trades = JournalTradeRepository(session)

    def evaluate(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        strategy_id: uuid.UUID | None = None,
        strategy_version_id: uuid.UUID | None = None,
        setup_id: uuid.UUID | None = None,
    ) -> SetupEvidenceResponse:
        thresholds = SetupEvidenceThresholds(
            tier1_oos_min_trades=self._settings.backtest_tier1_oos_min_trades,
            tier1_oos_min_profit_factor=self._settings.backtest_tier1_oos_min_profit_factor,
            tier1_min_confirm_trades=self._settings.backtest_tier1_min_confirm_trades,
            tier2_min_trades=self._settings.backtest_tier2_min_trades,
            tier2_oos_min_trades=self._settings.backtest_tier2_oos_min_trades,
            tier2_oos_min_profit_factor=self._settings.backtest_tier2_oos_min_profit_factor,
        )

        versions = self._scoped_versions(
            organization_id=organization_id,
            user_id=user_id,
            strategy_id=strategy_id,
            strategy_version_id=strategy_version_id,
        )
        items: list[SetupEvidenceItem] = []
        for strategy, version in versions:
            if setup_id is not None:
                # setup_id filters confirmation cohort only when provided.
                pass
            measured = self._measure_version(
                strategy_id=strategy.id,
                version_id=version.id,
                organization_id=organization_id,
                user_id=user_id,
                setup_id=setup_id,
            )
            tier = self._classify(measured, thresholds)
            items.append(
                SetupEvidenceItem(
                    strategy_id=strategy.id,
                    strategy_version_id=version.id,
                    strategy_name=strategy.name,
                    version=version.version,
                    tier=tier,
                    measured=measured,
                    thresholds=thresholds,
                )
            )

        items.sort(key=lambda i: (i.strategy_name.lower(), i.version, str(i.strategy_version_id)))
        return SetupEvidenceResponse(items=items, generated_at=datetime.now(UTC))

    def _scoped_versions(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        strategy_id: uuid.UUID | None,
        strategy_version_id: uuid.UUID | None,
    ) -> list[tuple[UserStrategy, UserStrategyVersion]]:
        stmt = (
            select(UserStrategy, UserStrategyVersion)
            .join(UserStrategyVersion, UserStrategyVersion.strategy_id == UserStrategy.id)
            .where(
                UserStrategy.organization_id == organization_id,
                UserStrategy.user_id == user_id,
            )
            .order_by(UserStrategy.name.asc(), UserStrategyVersion.version.asc())
        )
        if strategy_id is not None:
            stmt = stmt.where(UserStrategy.id == strategy_id)
        if strategy_version_id is not None:
            stmt = stmt.where(UserStrategyVersion.id == strategy_version_id)
        return [(strategy, version) for strategy, version in self._session.execute(stmt).all()]

    def _measure_version(
        self,
        *,
        strategy_id: uuid.UUID,
        version_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        setup_id: uuid.UUID | None,
    ) -> SetupEvidenceMeasured:
        run = self._latest_oos_run(
            strategy_id=strategy_id,
            version_id=version_id,
            organization_id=organization_id,
        )
        oos_trade_count = 0
        oos_pf: float | None = None
        oos_exp: Decimal | None = None
        total_bt = 0
        run_id: uuid.UUID | None = None
        if run is not None and run.result:
            run_id = run.id
            result = run.result
            metrics = result.get("metrics") or {}
            total_bt = int(metrics.get("trade_count") or 0)
            oos = result.get("oos_metrics")
            if isinstance(oos, dict):
                oos_trade_count = int(oos.get("trade_count") or 0)
                raw_pf = oos.get("profit_factor")
                oos_pf = float(raw_pf) if raw_pf is not None else None
                raw_exp = oos.get("expectancy")
                oos_exp = Decimal(str(raw_exp)) if raw_exp is not None else None

        confirm_sources = {
            JournalTradeSource.MANUAL,
            JournalTradeSource.IMPORTED,
            JournalTradeSource.PAPER_EXECUTION,
            JournalTradeSource.PAPER_VALIDATION,
            JournalTradeSource.SYSTEM,
        }
        rows, _truncated = self._trades.fetch_stats_rows(
            organization_id=organization_id,
            user_id=user_id,
            sources=confirm_sources,
            setup_id=setup_id,
            user_strategy_id=strategy_id,
            strategy_version_id=version_id,
            max_rows=self._settings.journal_stats_max_rows,
        )
        confirm_metrics = _compute_metrics(rows)
        return SetupEvidenceMeasured(
            oos_trade_count=oos_trade_count,
            oos_profit_factor=oos_pf,
            oos_expectancy=oos_exp,
            confirm_trade_count=confirm_metrics.trade_count,
            confirm_expectancy=confirm_metrics.expectancy,
            total_backtest_trades=total_bt,
            backtest_run_id=run_id,
        )

    def _latest_oos_run(
        self,
        *,
        strategy_id: uuid.UUID,
        version_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> BacktestRunModel | None:
        stmt = (
            select(BacktestRunModel)
            .where(
                BacktestRunModel.organization_id == organization_id,
                BacktestRunModel.strategy_id == strategy_id,
                BacktestRunModel.strategy_version_id == version_id,
                BacktestRunModel.status == BacktestRunStatus.COMPLETED,
            )
            .order_by(
                BacktestRunModel.finished_at.desc().nullslast(),
                BacktestRunModel.created_at.desc(),
            )
        )
        for run in self._session.scalars(stmt).all():
            result = run.result or {}
            if isinstance(result.get("oos_metrics"), dict):
                return run
        return None

    @staticmethod
    def _classify(
        measured: SetupEvidenceMeasured,
        thresholds: SetupEvidenceThresholds,
    ) -> SetupEvidenceTier:
        oos_exp_ok = measured.oos_expectancy is not None and measured.oos_expectancy > 0
        confirm_exp_ok = measured.confirm_expectancy is not None and measured.confirm_expectancy > 0
        oos_pf = measured.oos_profit_factor

        if (
            measured.oos_trade_count >= thresholds.tier1_oos_min_trades
            and oos_pf is not None
            and oos_pf >= thresholds.tier1_oos_min_profit_factor
            and oos_exp_ok
            and measured.confirm_trade_count >= thresholds.tier1_min_confirm_trades
            and confirm_exp_ok
        ):
            return SetupEvidenceTier.TIER1

        if (
            measured.total_backtest_trades >= thresholds.tier2_min_trades
            and measured.oos_trade_count >= thresholds.tier2_oos_min_trades
            and oos_pf is not None
            and oos_pf >= thresholds.tier2_oos_min_profit_factor
            and oos_exp_ok
        ):
            return SetupEvidenceTier.TIER2

        return SetupEvidenceTier.TIER3

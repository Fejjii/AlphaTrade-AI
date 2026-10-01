"""Replay lifecycle on existing BacktestRun/Dataset/Trade and audit authorities.

Creation queues a normal backtest job. Existing workers execute/verify it through
BacktestService; completed JSON includes the durable candidate/risk trace.
"""

import json
from dataclasses import asdict
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from app.services.backtest_service import BacktestService

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationAppError
from app.db.models import BacktestDataset, BacktestRun, BacktestTrade, UserStrategyVersion
from app.db.strategy_immutability import strategy_version_content_hash
from app.repositories.backtest import BacktestRunRepository
from app.repositories.strategy_library import UserStrategyRepository
from app.schemas.backtest import BacktestResult
from app.schemas.backtest import BacktestRun as BacktestRunSchema
from app.schemas.common import AuditEventType, BacktestRunStatus, BacktestSplitLabel
from app.schemas.nested_continuation import NestedContinuationSpec
from app.schemas.strategy_replay import (
    REPLAY_ENGINE,
    ReplayComparison,
    ReplayComparisonRequest,
    ReplayReport,
    StrategyReplayCreate,
)
from app.services.backtest_hashing import (
    canonical_json_bytes,
    canonical_json_hash,
    dataset_content_hash,
)
from app.services.risk.limits import RiskLimits
from app.services.strategy_replay_engine import StrategyReplayEngine, replay_input_hash


class StrategyReplayService:
    def __init__(self, session: Session, backtests: "BacktestService") -> None:
        self._session = session
        self._backtests = backtests
        self._runs = BacktestRunRepository(session)

    def create(
        self, request: StrategyReplayCreate, *, organization_id: UUID, user_id: UUID
    ) -> BacktestRunSchema:
        version = self._session.get(UserStrategyVersion, request.strategy_version_id)
        if version is None:
            raise NotFoundError("Strategy version not found.")
        strategy = UserStrategyRepository(self._session).get_scoped(
            version.strategy_id, organization_id=organization_id, user_id=user_id
        )
        if strategy is None:
            raise NotFoundError("Strategy version not found.")
        content_hash = strategy_version_content_hash(
            card=version.card,
            structured_rules=version.structured_rules,
            lesson_source_metadata=version.lesson_source_metadata,
            pattern_spec=version.pattern_spec,
        )
        if content_hash != version.content_hash:
            raise ValidationAppError("Strategy version content hash mismatch.")
        try:
            spec = NestedContinuationSpec.model_validate(version.pattern_spec)
        except ValueError as exc:
            raise ValidationAppError(
                "Replay 001 supports exact Nested Continuation versions only."
            ) from exc
        dataset = self._session.get(BacktestDataset, request.dataset_id)
        if dataset is None:
            raise NotFoundError("Backtest dataset not found.")
        assumptions = request.assumptions
        if (dataset.symbol, dataset.exchange, dataset.timeframe) != (
            spec.symbol,
            assumptions.exchange,
            spec.trigger_timeframe.value,
        ) or (assumptions.symbol, assumptions.timeframe) != (spec.symbol, spec.trigger_timeframe):
            raise ValidationAppError(
                "Dataset, assumptions and strategy instrument/timeframe must match."
            )
        if assumptions.exchange not in {"binance", "bybit"}:
            raise ValidationAppError("Replay requires a contracted perpetual venue.")
        rows = self._backtests._load_dataset_candles(dataset)
        if dataset_content_hash(rows) != dataset.dataset_hash or len(rows) != dataset.candle_count:
            raise ValidationAppError(
                "Dataset changed or is missing; create a new dataset snapshot."
            )
        if len(rows) > self._backtests._settings.backtest_max_bars:
            raise ValidationAppError("Dataset exceeds backtest_max_bars; replay cannot truncate.")
        limits = asdict(RiskLimits())
        limits["supported_symbols"] = sorted(limits["supported_symbols"])
        request_payload = request.model_dump(mode="json", exclude={"idempotency_key"})
        snapshot = {
            "engine_version": REPLAY_ENGINE,
            "pattern_spec": spec.model_dump(mode="json"),
            "strategy_content_hash": version.content_hash,
            "replay_request": {**request_payload, "idempotency_key": request.idempotency_key},
            "assumptions": assumptions.model_dump(mode="json"),
            "risk_limits": json.loads(canonical_json_bytes(limits)),
            "dataset_hash": dataset.dataset_hash,
            "input_hash": replay_input_hash(rows),
        }
        # Idempotency identifies one exact intent; conflicting content cannot be reused.
        config_hash = canonical_json_hash(snapshot)
        existing = self._runs.get_by_idempotency_key(
            organization_id=organization_id, idempotency_key=request.idempotency_key
        )
        if existing:
            if existing.config_hash != config_hash or existing.user_id != user_id:
                raise ConflictError("Replay idempotency key reused with different content.")
            return self._backtests._to_schema(existing)
        run = BacktestRun(
            strategy_id=strategy.id,
            strategy_version_id=version.id,
            organization_id=organization_id,
            user_id=user_id,
            status=BacktestRunStatus.QUEUED,
            assumptions=assumptions.model_dump(mode="json"),
            config_snapshot=snapshot,
            config_hash=config_hash,
            dataset_id=dataset.id,
            engine_version=REPLAY_ENGINE,
            idempotency_key=request.idempotency_key,
            total_bars=len(rows),
        )
        if (
            self._runs.count_active_for_org(organization_id)
            >= self._backtests._settings.backtest_max_active_runs_per_org
        ):
            raise ConflictError("Too many active backtest/replay runs.")
        try:
            self._backtests._persist_new_run(run)
        except ConflictError:
            winner = self._runs.get_by_idempotency_key(
                organization_id=organization_id, idempotency_key=request.idempotency_key
            )
            if winner is None or winner.config_hash != config_hash or winner.user_id != user_id:
                raise
            return self._backtests._to_schema(winner)
        self._backtests._audit_lifecycle(
            run,
            AuditEventType.BACKTEST_RUN_CREATED,
            {"research_replay": True, "config_hash": config_hash},
        )
        return self._backtests._to_schema(run)

    def replay(self, run: BacktestRun, *, persist: bool) -> BacktestResult:
        snapshot = run.config_snapshot or {}
        if (
            snapshot.get("engine_version") != REPLAY_ENGINE
            or canonical_json_hash(snapshot) != run.config_hash
        ):
            raise ValidationAppError("Replay frozen configuration mismatch.")
        request = StrategyReplayCreate.model_validate(snapshot["replay_request"])
        if (
            request.strategy_version_id != run.strategy_version_id
            or request.dataset_id != run.dataset_id
        ):
            raise ValidationAppError("Replay run identity differs from its frozen configuration.")
        version = self._session.get(UserStrategyVersion, run.strategy_version_id)
        if version is None or version.content_hash != snapshot["strategy_content_hash"]:
            raise ValidationAppError("Replay immutable strategy version mismatch.")
        dataset = self._session.get(BacktestDataset, run.dataset_id)
        if dataset is None:
            raise ValidationAppError("Replay dataset missing.")
        rows = self._backtests._load_dataset_candles(dataset)
        if (
            dataset_content_hash(rows) != snapshot["dataset_hash"]
            or replay_input_hash(rows) != snapshot["input_hash"]
        ):
            raise ValidationAppError("Replay dataset content changed.")
        result = StrategyReplayEngine(self._backtests._engine).run(
            rows=rows,
            snapshot=snapshot,
            should_cancel=(lambda: self._backtests._should_cancel(run.id)) if persist else None,
        )
        if persist:
            for trade in result.trades:
                data = trade.model_dump(
                    exclude={
                        "id",
                        "planned_targets",
                        "r_result",
                        "holding_bars",
                        "holding_seconds",
                        "setup_id",
                    }
                )
                data["direction"] = trade.direction.value
                data["split_label"] = trade.split_label.value
                self._session.add(BacktestTrade(backtest_run_id=run.id, **data))
            run.result = result.model_dump(mode="json")
            run.result_hash = result.result_hash
            run.processed_bars = result.processed_bars
            run.total_bars = result.total_bars
        return result

    def compare(
        self, request: ReplayComparisonRequest, *, organization_id: UUID
    ) -> ReplayComparison:
        found = [
            self._runs.get_scoped(identity, organization_id=organization_id)
            for identity in (request.baseline_run_id, request.proposed_run_id)
        ]
        if any(run is None for run in found):
            raise NotFoundError("Replay run not found.")
        runs = [run for run in found if run is not None]
        baseline, proposed = runs
        assert baseline.config_snapshot is not None and proposed.config_snapshot is not None
        assert baseline.strategy_version_id is not None and proposed.strategy_version_id is not None
        if any(
            run.status != BacktestRunStatus.COMPLETED or run.engine_version != REPLAY_ENGINE
            for run in runs
        ):
            raise ValidationAppError("Comparison requires two completed strategy replays.")
        for key in ("input_hash", "dataset_hash", "assumptions", "risk_limits", "engine_version"):
            if baseline.config_snapshot[key] != proposed.config_snapshot[key]:
                raise ValidationAppError(f"Comparison requires identical {key}.")
        for key in ("windows", "minimum_sample"):
            if (
                baseline.config_snapshot["replay_request"][key]
                != proposed.config_snapshot["replay_request"][key]
            ):
                raise ValidationAppError(f"Comparison requires identical {key}.")
        base_spec, prop_spec = (
            baseline.config_snapshot["pattern_spec"],
            proposed.config_snapshot["pattern_spec"],
        )
        for key in ("kind", "symbol", "trigger_timeframe", "direction"):
            if base_spec[key] != prop_spec[key]:
                raise ValidationAppError(f"Comparison requires identical strategy {key}.")
        results = [BacktestResult.model_validate(run.result) for run in runs]
        for run, result in zip(runs, results, strict=True):
            if canonical_json_hash(run.config_snapshot) != run.config_hash:
                raise ValidationAppError("Stored replay config hash mismatch.")
            if result.result_hash != run.result_hash:
                raise ValidationAppError("Stored replay result identity mismatch.")
            if (
                canonical_json_hash(result.model_dump(mode="json", exclude={"result_hash"}))
                != run.result_hash
            ):
                raise ValidationAppError("Stored replay result hash mismatch.")
        reports = [ReplayReport.model_validate(result.replay) for result in results]
        evaluation = [
            next(s for s in report.samples if s.split_label is BacktestSplitLabel.OUT_OF_SAMPLE)
            for report in reports
        ]
        comparison = ReplayComparison(
            comparison_hash=canonical_json_hash(
                {
                    "baseline": str(baseline.id),
                    "proposed": str(proposed.id),
                    "results": [run.result_hash for run in runs],
                }
            ),
            baseline_run_id=baseline.id,
            proposed_run_id=proposed.id,
            baseline_version_id=baseline.strategy_version_id,
            proposed_version_id=proposed.strategy_version_id,
            baseline_samples=reports[0].samples,
            proposed_samples=reports[1].samples,
            evaluation_net_pnl_delta=None
            if any(s.status == "missing_data" for s in evaluation)
            else evaluation[1].net_pnl - evaluation[0].net_pnl,
            limitations=[
                "Observed differences are descriptive; no performance improvement claim.",
                "No automatic parameter selection, promotion, or evaluation-window training.",
                *[
                    f"{name}: {sample.status} ({sample.trade_count} evaluation trades)."
                    for name, sample in zip(("baseline", "proposed"), evaluation, strict=True)
                ],
            ],
        )

        self._backtests._audit_lifecycle(
            baseline,
            AuditEventType.BACKTEST_RUN_VERIFIED,
            {
                "operation": "strategy_replay_comparison",
                "comparison_hash": comparison.comparison_hash,
                "baseline_run_id": str(baseline.id),
                "proposed_run_id": str(proposed.id),
                "baseline_result_hash": baseline.result_hash,
                "proposed_result_hash": proposed.result_hash,
                "improvement_claim": False,
            },
        )
        return comparison

"""Bulk journal from completed backtest runs (AT-034 WS2).

Record-only: creates canonical ``journal_trades`` with ``source=backtest`` and
``entry_method=auto``. Never touches execution, risk, or live trading.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import ConflictError, NotFoundError, ValidationAppError
from app.db.models import BacktestRun as BacktestRunModel
from app.db.models import BacktestTrade as BacktestTradeModel
from app.db.models import JournalTrade
from app.repositories.backtest import BacktestRunRepository
from app.repositories.backtest_trades import BacktestTradeRepository
from app.repositories.journal_trades import JournalTradeRepository
from app.schemas.audit import AuditRecordCreate
from app.schemas.backtest import (
    BacktestAssumptions,
    BacktestJournalRequest,
    BacktestJournalResult,
    BacktestJournalRowOutcome,
    BacktestJournalRowResult,
)
from app.schemas.common import (
    ActorType,
    AuditEventType,
    JournalEntryMethod,
    JournalTradeSource,
    JournalTradeStatus,
    TradeDirection,
    TradeResult,
)
from app.services.audit_service import AuditService

_REQUEST_TAG = "backtest-journal-api"
_ZERO = Decimal("0")


class BacktestJournalService:
    def __init__(
        self,
        session: Session,
        audit_service: AuditService,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._audit = audit_service
        self._settings = settings or get_settings()
        self._runs = BacktestRunRepository(session)
        self._trades = BacktestTradeRepository(session)
        self._journal = JournalTradeRepository(session)

    def journal_run(
        self,
        run_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        dry_run: bool = True,
    ) -> BacktestJournalResult:
        run = self._runs.get_scoped(run_id, organization_id=organization_id)
        if run is None:
            raise NotFoundError("Backtest run not found.")
        if run.status.value != "completed":
            raise ConflictError(
                "Only completed backtest runs can be journaled.",
                code="backtest_journal_invalid",
            )

        trade_count = self._trades.count_for_run(run_id)
        cap = self._settings.backtest_journal_bulk_max
        if trade_count > cap:
            raise ValidationAppError(
                f"Backtest has {trade_count} trades; bulk journal cap is {cap}.",
                details={"trade_count": trade_count, "cap": cap},
            )

        trades = self._trades.list_all_for_run(run_id, limit=cap)
        assumptions = BacktestAssumptions.model_validate(run.assumptions or {})
        refs = [f"backtest:{run_id}:{trade.id}" for trade in trades]
        existing = self._journal.existing_external_refs(
            organization_id=organization_id, external_refs=refs
        )

        results: list[BacktestJournalRowResult] = []
        created = duplicates = invalid = 0
        any_invalid = False
        pending: list[JournalTrade] = []

        for index, trade in enumerate(trades):
            external_ref = f"backtest:{run_id}:{trade.id}"
            errors = _validate_trade(trade)
            if errors:
                any_invalid = True
                invalid += 1
                results.append(
                    BacktestJournalRowResult(
                        index=index,
                        backtest_trade_id=trade.id,
                        outcome=BacktestJournalRowOutcome.INVALID,
                        external_ref=external_ref,
                        errors=errors,
                    )
                )
                continue

            if external_ref in existing:
                duplicates += 1
                results.append(
                    BacktestJournalRowResult(
                        index=index,
                        backtest_trade_id=trade.id,
                        outcome=BacktestJournalRowOutcome.DUPLICATE,
                        external_ref=external_ref,
                        journal_trade_id=existing[external_ref],
                    )
                )
                continue

            created += 1
            row = self._build_journal_trade(
                trade,
                run=run,
                assumptions=assumptions,
                organization_id=organization_id,
                user_id=user_id,
                external_ref=external_ref,
            )
            pending.append(row)
            results.append(
                BacktestJournalRowResult(
                    index=index,
                    backtest_trade_id=trade.id,
                    outcome=(
                        BacktestJournalRowOutcome.WOULD_CREATE
                        if dry_run
                        else BacktestJournalRowOutcome.CREATED
                    ),
                    external_ref=external_ref,
                    journal_trade_id=None if dry_run else row.id,
                )
            )

        persist = (not dry_run) and (not any_invalid)
        if persist:
            for row in pending:
                self._journal.add(row)
            self._session.flush()
            # Fill created ids into the report.
            ref_to_id = {row.external_ref: row.id for row in pending if row.external_ref}
            for item in results:
                if item.outcome == BacktestJournalRowOutcome.CREATED and item.external_ref:
                    item.journal_trade_id = ref_to_id.get(item.external_ref)
            self._audit.record(
                AuditRecordCreate(
                    request_id=_REQUEST_TAG,
                    trace_id=_REQUEST_TAG,
                    event_type=AuditEventType.BACKTEST_JOURNALED,
                    resource_type="backtest_run",
                    resource_id=str(run_id),
                    organization_id=organization_id,
                    user_id=user_id,
                    actor_type=ActorType.USER,
                    metadata={
                        "created_count": created,
                        "duplicate_count": duplicates,
                        "invalid_count": invalid,
                        "total_rows": len(trades),
                    },
                )
            )

        return BacktestJournalResult(
            run_id=run_id,
            dry_run=dry_run,
            committed=persist,
            total_rows=len(trades),
            created_count=created,
            duplicate_count=duplicates,
            invalid_count=invalid,
            results=results,
        )

    def journal_from_request(
        self,
        run_id: uuid.UUID,
        request: BacktestJournalRequest,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> BacktestJournalResult:
        return self.journal_run(
            run_id,
            organization_id=organization_id,
            user_id=user_id,
            dry_run=request.dry_run,
        )

    def _build_journal_trade(
        self,
        trade: BacktestTradeModel,
        *,
        run: BacktestRunModel,
        assumptions: BacktestAssumptions,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        external_ref: str,
    ) -> JournalTrade:
        net_pnl = trade.net_pnl
        result = _result_from_pnl(net_pnl)
        capture_float = float(trade.capture_pct) if trade.capture_pct is not None else None
        runner_enabled = "runner" in str(trade.exit_reason).lower()
        return JournalTrade(
            organization_id=organization_id,
            user_id=user_id,
            source=JournalTradeSource.BACKTEST,
            entry_method=JournalEntryMethod.AUTO,
            status=JournalTradeStatus.CLOSED,
            symbol=assumptions.symbol,
            exchange=assumptions.exchange,
            timeframe=assumptions.timeframe.value,
            user_strategy_id=run.strategy_id,
            strategy_version_id=run.strategy_version_id,
            direction=TradeDirection(trade.direction),
            entry_price=trade.entry_price,
            entry_time=trade.entry_time,
            exit_price=trade.exit_price,
            exit_time=trade.exit_time,
            exit_reason=trade.exit_reason,
            size=trade.size,
            fees=trade.fees,
            funding=trade.funding_cost or _ZERO,
            slippage=trade.slippage_cost,
            gross_pnl=trade.gross_pnl,
            net_pnl=net_pnl,
            result=result,
            planned_stop_price=trade.stop_loss,
            planned_targets=[],
            runner_enabled=runner_enabled,
            mfe_price=trade.mfe_price,
            mae_price=trade.mae_price,
            mfe_amount=trade.mfe_amount,
            mae_amount=trade.mae_amount,
            available_profit=trade.available_profit,
            realized_vs_available_pct=capture_float,
            excursion_source="backtest",
            linked_backtest_trade_id=trade.id,
            external_ref=external_ref,
        )


def _result_from_pnl(net_pnl: Decimal | None) -> TradeResult:
    if net_pnl is None:
        return TradeResult.BREAKEVEN
    if net_pnl > 0:
        return TradeResult.WIN
    if net_pnl < 0:
        return TradeResult.LOSS
    return TradeResult.BREAKEVEN


def _validate_trade(trade: BacktestTradeModel) -> list[str]:
    errors: list[str] = []
    if trade.entry_time is None:
        errors.append("entry_time is required")
    if trade.exit_time is None:
        errors.append("exit_time is required")
    if trade.entry_price is None:
        errors.append("entry_price is required")
    if trade.exit_price is None:
        errors.append("exit_price is required")
    try:
        TradeDirection(trade.direction)
    except (TypeError, ValueError):
        errors.append("direction is invalid")
    return errors

"""Canonical journal trade service (AT-030 — Journal Intelligence Foundation).

Record-only intelligence layer over existing trading records. This service
never places orders, never mutates positions/paper trades, and is never read
by the execution engine, scheduler, or risk gates. All linked records are
validated against the caller's organization (fail closed via ``NotFoundError``
so cross-tenant probing cannot distinguish "missing" from "foreign").

Unit of work (AT-ADR-008): the service flushes; the route commits.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationAppError
from app.db.models import (
    BacktestRun,
    BacktestTrade,
    JournalTrade,
    JournalTradeEvidence,
    JournalTradeObservation,
    JournalTradeRuleCheck,
    Order,
    PaperTrade,
    PaperValidationRun,
    Position,
    SetupDefinition,
    TradeJournal,
    TradeProposal,
    UserStrategy,
    UserStrategyVersion,
)
from app.repositories.journal_trades import (
    JournalTradeEvidenceRepository,
    JournalTradeObservationRepository,
    JournalTradeRepository,
    JournalTradeRuleCheckRepository,
)
from app.schemas.audit import AuditRecordCreate
from app.schemas.common import (
    ActorType,
    AuditEventType,
    JournalTradeSource,
    JournalTradeStatus,
    TradeResult,
)
from app.schemas.journal_trades import (
    JournalTradeCreate,
    JournalTradeDetail,
    JournalTradeEvidenceCreate,
    JournalTradeEvidenceRead,
    JournalTradeObservationCreate,
    JournalTradeObservationRead,
    JournalTradeRead,
    JournalTradeRuleCheckCreate,
    JournalTradeRuleCheckRead,
    JournalTradeUpdate,
)
from app.services.audit_service import AuditService

_REQUEST_TAG = "journal-trades-api"


class JournalTradeService:
    """CRUD + linkage + intelligence sub-records for canonical journal trades."""

    def __init__(self, session: Session, audit_service: AuditService) -> None:
        self._session = session
        self._trades = JournalTradeRepository(session)
        self._evidence = JournalTradeEvidenceRepository(session)
        self._rule_checks = JournalTradeRuleCheckRepository(session)
        self._observations = JournalTradeObservationRepository(session)
        self._audit = audit_service

    # ------------------------------------------------------------------ #
    # Create / read / update / delete
    # ------------------------------------------------------------------ #

    def create(
        self,
        data: JournalTradeCreate,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> JournalTradeRead:
        self._validate_strategy_links(
            organization_id=organization_id,
            setup_id=data.setup_id,
            user_strategy_id=data.user_strategy_id,
            strategy_version_id=data.strategy_version_id,
        )
        self._validate_record_links(data, organization_id=organization_id)

        row = JournalTrade(
            organization_id=organization_id,
            user_id=user_id,
            source=data.source,
            status=data.status,
            symbol=str(data.symbol),
            exchange=data.exchange,
            timeframe=data.timeframe.value,
            market_regime=data.market_regime,
            regime_notes=data.regime_notes,
            setup_id=data.setup_id,
            user_strategy_id=data.user_strategy_id,
            strategy_version_id=data.strategy_version_id,
            strategy_label=data.strategy_label,
            direction=data.direction,
            thesis=data.thesis,
            trigger=data.trigger,
            entry_plan=data.entry_plan,
            invalidation=data.invalidation,
            planned_entry_price=data.planned_entry_price,
            planned_stop_price=data.planned_stop_price,
            planned_targets=[t.model_dump(mode="json") for t in data.planned_targets],
            runner_enabled=data.runner_enabled,
            runner_plan=data.runner_plan,
            planned_risk_amount=data.planned_risk_amount,
            entry_price=data.entry_price,
            entry_time=data.entry_time,
            exit_price=data.exit_price,
            exit_time=data.exit_time,
            exit_reason=data.exit_reason,
            size=data.size,
            leverage=data.leverage,
            fees=data.fees,
            funding=data.funding,
            slippage=data.slippage,
            gross_pnl=data.gross_pnl,
            net_pnl=data.net_pnl,
            result=data.result,
            notes=data.notes,
            tags=list(data.tags),
            linked_position_id=data.links.linked_position_id,
            linked_paper_trade_id=data.links.linked_paper_trade_id,
            linked_proposal_id=data.links.linked_proposal_id,
            linked_order_id=data.links.linked_order_id,
            linked_backtest_trade_id=data.links.linked_backtest_trade_id,
            linked_journal_entry_id=data.links.linked_journal_entry_id,
            linked_paper_validation_run_id=data.links.linked_paper_validation_run_id,
            external_ref=data.external_ref,
        )
        self._trades.add(row)
        self._record_audit(row, AuditEventType.JOURNAL_TRADE_CREATED, action="create")
        return JournalTradeRead.model_validate(row)

    def create_from_position(
        self,
        position_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> JournalTradeRead:
        """Create a journal trade prefilled from an existing paper position.

        Copies the execution snapshot from the position and the plan fields
        (thesis, invalidation, stop, targets, runner) from the linked proposal
        when one exists. Idempotent per position: an existing journal trade
        linked to the position is returned unchanged.
        """
        position = self._session.scalar(
            select(Position).where(
                Position.id == position_id,
                Position.organization_id == organization_id,
            )
        )
        if position is None:
            raise NotFoundError("Position not found")

        existing = self._trades.find_by_link(
            organization_id=organization_id, linked_position_id=position.id
        )
        if existing is not None:
            return JournalTradeRead.model_validate(existing)

        proposal: TradeProposal | None = None
        if position.linked_proposal_id is not None:
            proposal = self._session.scalar(
                select(TradeProposal).where(
                    TradeProposal.id == position.linked_proposal_id,
                    TradeProposal.organization_id == organization_id,
                )
            )

        is_closed = position.closed_at is not None
        row = JournalTrade(
            organization_id=organization_id,
            user_id=user_id,
            source=JournalTradeSource.PAPER_EXECUTION,
            status=JournalTradeStatus.CLOSED if is_closed else JournalTradeStatus.OPEN,
            symbol=position.symbol,
            timeframe=proposal.timeframe if proposal is not None else "1h",
            direction=position.direction,
            thesis=proposal.rationale if proposal is not None else None,
            invalidation=proposal.invalidation if proposal is not None else None,
            planned_entry_price=proposal.entry_price if proposal is not None else None,
            planned_stop_price=(proposal.stop_loss if proposal is not None else position.stop_loss),
            planned_targets=(
                list(proposal.take_profits or [])
                if proposal is not None
                else list(position.take_profits or [])
            ),
            runner_enabled=proposal.runner_enabled if proposal is not None else False,
            runner_plan=proposal.runner_notes if proposal is not None else None,
            entry_price=position.entry_price,
            entry_time=position.opened_at,
            exit_time=position.closed_at,
            size=position.size,
            leverage=position.leverage,
            net_pnl=position.realized_pnl if is_closed else None,
            result=_result_from_pnl(position.realized_pnl) if is_closed else TradeResult.OPEN,
            linked_position_id=position.id,
            linked_proposal_id=position.linked_proposal_id,
            tags=[],
        )
        self._trades.add(row)
        self._record_audit(
            row,
            AuditEventType.JOURNAL_TRADE_CREATED,
            action="create_from_position",
        )
        return JournalTradeRead.model_validate(row)

    def create_from_paper_trade(
        self,
        paper_trade_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> JournalTradeRead:
        """Create a journal trade prefilled from a paper-validation trade.

        Idempotent per paper trade: an existing journal trade linked to the
        paper trade is returned unchanged.
        """
        paper_trade = self._session.scalar(
            select(PaperTrade).where(
                PaperTrade.id == paper_trade_id,
                PaperTrade.organization_id == organization_id,
            )
        )
        if paper_trade is None:
            raise NotFoundError("Paper trade not found")

        existing = self._trades.find_by_link(
            organization_id=organization_id, linked_paper_trade_id=paper_trade.id
        )
        if existing is not None:
            return JournalTradeRead.model_validate(existing)

        is_closed = paper_trade.exit_time is not None
        tp_plan = paper_trade.tp_plan or {}
        targets_raw = tp_plan.get("targets") if isinstance(tp_plan, dict) else None
        row = JournalTrade(
            organization_id=organization_id,
            user_id=user_id,
            source=JournalTradeSource.PAPER_VALIDATION,
            status=JournalTradeStatus.CLOSED if is_closed else JournalTradeStatus.OPEN,
            symbol=paper_trade.symbol,
            exchange=paper_trade.exchange,
            timeframe=paper_trade.timeframe,
            user_strategy_id=paper_trade.strategy_id,
            strategy_version_id=paper_trade.strategy_version_id,
            direction=paper_trade.direction,
            invalidation=paper_trade.invalidation,
            planned_stop_price=paper_trade.stop_loss,
            planned_targets=list(targets_raw) if isinstance(targets_raw, list) else [],
            runner_enabled=bool(paper_trade.runner_plan),
            entry_price=paper_trade.entry_price,
            entry_time=paper_trade.entry_time,
            exit_price=paper_trade.exit_price,
            exit_time=paper_trade.exit_time,
            exit_reason=paper_trade.exit_reason,
            size=paper_trade.size,
            fees=paper_trade.fees,
            slippage=paper_trade.slippage,
            gross_pnl=paper_trade.gross_pnl,
            net_pnl=paper_trade.net_pnl,
            result=_result_from_pnl(paper_trade.net_pnl) if is_closed else TradeResult.OPEN,
            linked_paper_trade_id=paper_trade.id,
            linked_paper_validation_run_id=paper_trade.paper_validation_run_id,
            tags=[],
        )
        self._trades.add(row)
        self._record_audit(
            row,
            AuditEventType.JOURNAL_TRADE_CREATED,
            action="create_from_paper_trade",
        )
        return JournalTradeRead.model_validate(row)

    def list_trades(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
        source: JournalTradeSource | None = None,
        status: JournalTradeStatus | None = None,
        symbol: str | None = None,
        user_strategy_id: uuid.UUID | None = None,
        setup_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[JournalTradeRead], int]:
        rows, total = self._trades.list_trades(
            organization_id=organization_id,
            user_id=user_id,
            source=source,
            status=status,
            symbol=symbol,
            user_strategy_id=user_strategy_id,
            setup_id=setup_id,
            limit=limit,
            offset=offset,
        )
        return [JournalTradeRead.model_validate(row) for row in rows], total

    def get(self, trade_id: uuid.UUID, *, organization_id: uuid.UUID) -> JournalTradeRead:
        row = self._get_row(trade_id, organization_id=organization_id)
        return JournalTradeRead.model_validate(row)

    def get_detail(self, trade_id: uuid.UUID, *, organization_id: uuid.UUID) -> JournalTradeDetail:
        row = self._get_row(trade_id, organization_id=organization_id)
        return JournalTradeDetail(
            trade=JournalTradeRead.model_validate(row),
            evidence=[
                JournalTradeEvidenceRead.model_validate(e)
                for e in self._evidence.list_for_trade(row.id)
            ],
            rule_checks=[
                JournalTradeRuleCheckRead.model_validate(c)
                for c in self._rule_checks.list_for_trade(row.id)
            ],
            observations=[
                JournalTradeObservationRead.model_validate(o)
                for o in self._observations.list_for_trade(row.id)
            ],
        )

    def update(
        self,
        trade_id: uuid.UUID,
        data: JournalTradeUpdate,
        *,
        organization_id: uuid.UUID,
    ) -> JournalTradeRead:
        row = self._get_row(trade_id, organization_id=organization_id)
        updates = data.model_dump(exclude_unset=True)
        if any(k in updates for k in ("setup_id", "user_strategy_id", "strategy_version_id")):
            self._validate_strategy_links(
                organization_id=organization_id,
                setup_id=updates.get("setup_id", row.setup_id),
                user_strategy_id=updates.get("user_strategy_id", row.user_strategy_id),
                strategy_version_id=updates.get("strategy_version_id", row.strategy_version_id),
            )
        if "planned_targets" in updates and data.planned_targets is not None:
            updates["planned_targets"] = [t.model_dump(mode="json") for t in data.planned_targets]
        for key, value in updates.items():
            setattr(row, key, value)
        _derive_realized_vs_available(row, explicit="realized_vs_available_pct" in updates)
        self._trades.add(row)
        self._record_audit(row, AuditEventType.JOURNAL_TRADE_UPDATED, action="update")
        return JournalTradeRead.model_validate(row)

    def delete(self, trade_id: uuid.UUID, *, organization_id: uuid.UUID) -> None:
        row = self._get_row(trade_id, organization_id=organization_id)
        for child_repo in (self._evidence, self._rule_checks, self._observations):
            for child in child_repo.list_for_trade(row.id):
                self._session.delete(child)
        self._record_audit(row, AuditEventType.JOURNAL_TRADE_DELETED, action="delete")
        self._trades.delete(row)

    # ------------------------------------------------------------------ #
    # Evidence, rule checks, observations
    # ------------------------------------------------------------------ #

    def add_evidence(
        self,
        trade_id: uuid.UUID,
        data: JournalTradeEvidenceCreate,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> JournalTradeEvidenceRead:
        row = self._get_row(trade_id, organization_id=organization_id)
        child = JournalTradeEvidence(
            journal_trade_id=row.id,
            organization_id=organization_id,
            kind=data.kind,
            ref=data.ref,
            caption=data.caption,
            recorded_by=user_id,
        )
        self._evidence.add(child)
        self._record_audit(
            row,
            AuditEventType.JOURNAL_TRADE_EVIDENCE_ADDED,
            action="add_evidence",
            extra={"kind": data.kind.value},
        )
        return JournalTradeEvidenceRead.model_validate(child)

    def add_rule_check(
        self,
        trade_id: uuid.UUID,
        data: JournalTradeRuleCheckCreate,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> JournalTradeRuleCheckRead:
        row = self._get_row(trade_id, organization_id=organization_id)
        child = JournalTradeRuleCheck(
            journal_trade_id=row.id,
            organization_id=organization_id,
            rule_key=data.rule_key,
            rule_source=data.rule_source,
            status=data.status,
            notes=data.notes,
            assessed_by=user_id,
            assessed_at=data.assessed_at or datetime.now(UTC),
        )
        self._rule_checks.add(child)
        self._record_audit(
            row,
            AuditEventType.JOURNAL_TRADE_RULE_CHECKED,
            action="add_rule_check",
            extra={"rule_key": data.rule_key, "status": data.status.value},
        )
        return JournalTradeRuleCheckRead.model_validate(child)

    def add_observation(
        self,
        trade_id: uuid.UUID,
        data: JournalTradeObservationCreate,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> JournalTradeObservationRead:
        row = self._get_row(trade_id, organization_id=organization_id)
        child = JournalTradeObservation(
            journal_trade_id=row.id,
            organization_id=organization_id,
            category=data.category,
            observation=data.observation,
            emotion_tags=list(data.emotion_tags),
            recorded_by=user_id,
            observed_at=data.observed_at or datetime.now(UTC),
        )
        self._observations.add(child)
        self._record_audit(
            row,
            AuditEventType.JOURNAL_TRADE_OBSERVED,
            action="add_observation",
            extra={"category": data.category.value},
        )
        return JournalTradeObservationRead.model_validate(child)

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _get_row(self, trade_id: uuid.UUID, *, organization_id: uuid.UUID) -> JournalTrade:
        row = self._trades.get_scoped(trade_id, organization_id=organization_id)
        if row is None:
            raise NotFoundError("Journal trade not found")
        return row

    def _validate_strategy_links(
        self,
        *,
        organization_id: uuid.UUID,
        setup_id: uuid.UUID | None,
        user_strategy_id: uuid.UUID | None,
        strategy_version_id: uuid.UUID | None,
    ) -> None:
        if setup_id is not None:
            setup = self._session.get(SetupDefinition, setup_id)
            if setup is None:
                raise NotFoundError("Setup definition not found")
        strategy: UserStrategy | None = None
        if user_strategy_id is not None:
            strategy = self._session.scalar(
                select(UserStrategy).where(
                    UserStrategy.id == user_strategy_id,
                    UserStrategy.organization_id == organization_id,
                )
            )
            if strategy is None:
                raise NotFoundError("Strategy not found")
        if strategy_version_id is not None:
            version = self._session.get(UserStrategyVersion, strategy_version_id)
            if version is None:
                raise NotFoundError("Strategy version not found")
            if strategy is not None and version.strategy_id != strategy.id:
                raise ValidationAppError("strategy_version_id does not belong to user_strategy_id.")
            if strategy is None:
                owner = self._session.scalar(
                    select(UserStrategy).where(
                        UserStrategy.id == version.strategy_id,
                        UserStrategy.organization_id == organization_id,
                    )
                )
                if owner is None:
                    raise NotFoundError("Strategy version not found")

    def _validate_record_links(
        self,
        data: JournalTradeCreate,
        *,
        organization_id: uuid.UUID,
    ) -> None:
        links = data.links
        self._require_scoped(
            Position, links.linked_position_id, organization_id, "Position not found"
        )
        self._require_scoped(
            PaperTrade, links.linked_paper_trade_id, organization_id, "Paper trade not found"
        )
        self._require_scoped(
            TradeProposal, links.linked_proposal_id, organization_id, "Trade proposal not found"
        )
        self._require_scoped(Order, links.linked_order_id, organization_id, "Order not found")
        self._require_scoped(
            TradeJournal,
            links.linked_journal_entry_id,
            organization_id,
            "Journal entry not found",
        )
        self._require_scoped(
            PaperValidationRun,
            links.linked_paper_validation_run_id,
            organization_id,
            "Paper validation run not found",
        )
        if links.linked_backtest_trade_id is not None:
            found = self._session.scalar(
                select(BacktestTrade)
                .join(BacktestRun, BacktestTrade.backtest_run_id == BacktestRun.id)
                .where(
                    BacktestTrade.id == links.linked_backtest_trade_id,
                    BacktestRun.organization_id == organization_id,
                )
            )
            if found is None:
                raise NotFoundError("Backtest trade not found")

    def _require_scoped(
        self,
        model: type[Any],
        record_id: uuid.UUID | None,
        organization_id: uuid.UUID,
        message: str,
    ) -> None:
        if record_id is None:
            return
        found = self._session.scalar(
            select(model.id).where(
                model.id == record_id,
                model.organization_id == organization_id,
            )
        )
        if found is None:
            raise NotFoundError(message)

    def _record_audit(
        self,
        row: JournalTrade,
        event_type: AuditEventType,
        *,
        action: str,
        extra: dict[str, str] | None = None,
    ) -> None:
        metadata: dict[str, Any] = {
            "action": action,
            "symbol": row.symbol,
            "source": row.source.value,
        }
        if extra:
            metadata.update(extra)
        self._audit.record(
            AuditRecordCreate(
                request_id=_REQUEST_TAG,
                trace_id=_REQUEST_TAG,
                event_type=event_type,
                resource_type="journal_trade",
                resource_id=str(row.id),
                organization_id=row.organization_id,
                user_id=row.user_id,
                actor_type=ActorType.USER,
                metadata=metadata,
            )
        )


def _result_from_pnl(pnl: Decimal | None) -> TradeResult:
    if pnl is None:
        return TradeResult.OPEN
    if pnl > 0:
        return TradeResult.WIN
    if pnl < 0:
        return TradeResult.LOSS
    return TradeResult.BREAKEVEN


def _derive_realized_vs_available(row: JournalTrade, *, explicit: bool) -> None:
    """Derive realized-vs-available percent when both inputs are present.

    Deterministic arithmetic only. An explicitly provided percentage wins.
    """
    if explicit:
        return
    if row.net_pnl is None or row.available_profit is None:
        return
    if row.available_profit == 0:
        return
    row.realized_vs_available_pct = float(row.net_pnl / row.available_profit * Decimal("100"))

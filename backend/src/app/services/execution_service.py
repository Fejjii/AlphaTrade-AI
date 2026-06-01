"""Paper execution only. Real exchange trading is blocked by default."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import NotFoundError, TradingPolicyError
from app.db.models import Order, Position
from app.repositories.approvals import ApprovalRepository
from app.repositories.orders import OrderRepository
from app.repositories.proposals import ProposalRepository
from app.schemas.audit import AuditRecordCreate
from app.schemas.common import (
    ActorType,
    ApprovalStatus,
    AuditEventType,
    ExecutionMode,
    OrderStatus,
    PositionStatus,
    RiskAction,
    TradeDirection,
)
from app.schemas.execution import PaperOrder, PaperOrderRequest
from app.schemas.risk import RiskCheckResult
from app.services.audit_service import AuditService


class ExecutionService:
    def __init__(self, session: Session, settings: Settings, audit_service: AuditService) -> None:
        self._session = session
        self._settings = settings
        self._orders = OrderRepository(session)
        self._proposals = ProposalRepository(session)
        self._approvals = ApprovalRepository(session)
        self._audit = audit_service

    def place_paper_order(self, request: PaperOrderRequest) -> PaperOrder:
        if self._settings.real_trading_enabled:
            raise TradingPolicyError(
                "Real trading is disabled in this environment.",
                details={"execution_mode": self._settings.execution_mode.value},
            )

        proposal = self._proposals.get(request.proposal_id)
        if proposal is None:
            raise NotFoundError("Trade proposal not found")

        approval = self._approvals.get(request.approval_id)
        if approval is None:
            raise NotFoundError("Approval not found")
        if approval.proposal_id != proposal.id:
            raise TradingPolicyError("Approval does not match proposal.")
        if approval.status is not ApprovalStatus.APPROVED:
            self._audit_reject(request, reason="approval_not_granted")
            raise TradingPolicyError(
                "Paper execution requires an approved approval record.",
                details={"approval_status": approval.status.value},
            )
        if proposal.approval_required and approval.status is not ApprovalStatus.APPROVED:
            self._audit_reject(request, reason="approval_required")
            raise TradingPolicyError("Approval is required before paper execution.")

        if proposal.risk_result:
            risk = RiskCheckResult.model_validate(proposal.risk_result)
            if risk.action is RiskAction.BLOCK:
                self._audit_reject(request, reason="risk_blocked")
                raise TradingPolicyError(
                    "Paper execution blocked by risk engine.",
                    details={"risk_action": risk.action.value},
                )

        existing = self._orders.get_by_idempotency_key(request.idempotency_key)
        if existing is not None:
            return self._to_schema(existing)

        organization_id = proposal.organization_id
        user_id = proposal.user_id

        row = Order(
            organization_id=organization_id,
            user_id=user_id,
            proposal_id=request.proposal_id,
            approval_id=request.approval_id,
            mode=ExecutionMode.PAPER,
            symbol=str(request.symbol),
            side=request.side,
            order_type=request.type,
            size=request.size,
            price=request.price,
            status=OrderStatus.FILLED,
            reduce_only=request.reduce_only,
            idempotency_key=request.idempotency_key,
            exchange_order_id=f"paper-{uuid.uuid4().hex[:12]}",
        )
        self._orders.add(row)
        self._create_or_update_position(proposal=proposal, order=row)
        proposal.status = proposal.status  # touch
        self._proposals.add(proposal)

        self._audit.record(
            AuditRecordCreate(
                request_id=request.idempotency_key,
                trace_id=request.idempotency_key,
                event_type=AuditEventType.PAPER_ORDER_CREATED,
                resource_type="paper_order",
                resource_id=str(row.id),
                organization_id=organization_id,
                user_id=user_id,
                actor_type=ActorType.USER,
                metadata={"symbol": str(request.symbol), "mode": "paper"},
            )
        )
        return self._to_schema(row)

    def get_order(self, order_id: uuid.UUID) -> PaperOrder:
        row = self._orders.get(order_id)
        if row is None:
            raise NotFoundError("Order not found")
        return self._to_schema(row)

    def list_orders(
        self,
        *,
        organization_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[PaperOrder], int]:
        rows, total = self._orders.list_orders(
            organization_id=organization_id,
            user_id=user_id,
            limit=limit,
            offset=offset,
        )
        return [self._to_schema(row) for row in rows], total

    def _create_or_update_position(self, *, proposal, order: Order) -> None:
        direction = TradeDirection.LONG if order.side.value == "buy" else TradeDirection.SHORT
        position = Position(
            organization_id=order.organization_id,
            user_id=order.user_id,
            symbol=str(order.symbol),
            direction=direction,
            size=order.size,
            entry_price=order.price or proposal.entry_price,
            leverage=proposal.leverage,
            stop_loss=proposal.stop_loss,
            take_profits=proposal.take_profits or [],
            risk_state={"source": "paper_execution", "proposal_id": str(proposal.id)},
            status=PositionStatus.OPEN,
            opened_at=datetime.now(UTC),
        )
        self._session.add(position)
        self._session.flush()

    def _audit_reject(self, request: PaperOrderRequest, *, reason: str) -> None:
        self._audit.record(
            AuditRecordCreate(
                request_id=request.idempotency_key,
                trace_id=request.idempotency_key,
                event_type=AuditEventType.PAPER_ORDER_REJECTED,
                resource_type="paper_order",
                resource_id=str(request.proposal_id),
                actor_type=ActorType.SYSTEM,
                metadata={"reason": reason, "mode": "paper"},
            )
        )

    @staticmethod
    def _to_schema(row: Order) -> PaperOrder:
        return PaperOrder(
            id=row.id,
            organization_id=row.organization_id,
            user_id=row.user_id,
            proposal_id=row.proposal_id,
            approval_id=row.approval_id,
            mode=row.mode,
            symbol=row.symbol,
            side=row.side,
            type=row.order_type,
            size=row.size,
            price=row.price,
            status=row.status,
            reduce_only=row.reduce_only,
            idempotency_key=row.idempotency_key,
            exchange_order_id=row.exchange_order_id,
            created_at=row.created_at or datetime.now(UTC),
        )

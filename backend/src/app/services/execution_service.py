"""Paper execution only. Real exchange trading is blocked by default.

When ``exchange_mode=paper_exchange_demo`` and a demo execution provider is wired,
the internal paper fill is additionally mirrored to the BloFin *demo* venue. This
mirroring is best-effort: a demo-venue failure never blocks the internal paper
order, and there is no code path that can place a real-money order.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import structlog
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import NotFoundError, TradingPolicyError
from app.db.models import ExchangeFill, ExchangeOrder, Order, Position
from app.providers.exchange.base import (
    ExchangeExecutionProvider,
    ExchangeOrderRequest,
    ExchangeOrderResult,
)
from app.providers.exchange.mapping import to_blofin_inst_id
from app.repositories.approvals import ApprovalRepository
from app.repositories.exchange_orders import ExchangeFillRepository, ExchangeOrderRepository
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

logger = structlog.get_logger(__name__)

_EXCHANGE_DEMO_TAG = "paper_exchange_demo"


class ExecutionService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        audit_service: AuditService,
        *,
        exchange_execution: ExchangeExecutionProvider | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._orders = OrderRepository(session)
        self._proposals = ProposalRepository(session)
        self._approvals = ApprovalRepository(session)
        self._exchange_orders = ExchangeOrderRepository(session)
        self._exchange_fills = ExchangeFillRepository(session)
        self._exchange_execution = exchange_execution
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
        elif self._demo_routing_enabled():
            self._audit_reject(request, reason="demo_mirror_risk_result_required")
            raise TradingPolicyError(
                "Demo venue mirroring requires a risk engine result on the proposal.",
                details={"exchange_mode": self._settings.exchange_mode.value},
            )

        existing = self._orders.get_by_idempotency_key(request.idempotency_key)
        if existing is not None:
            return self._to_schema(existing)

        organization_id = proposal.organization_id
        user_id = proposal.user_id

        row = Order(
            organization_id=organization_id,
            user_id=user_id,
            strategy_id=proposal.strategy_id,
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

        mode_tag = _EXCHANGE_DEMO_TAG if self._demo_routing_enabled() else "paper"
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
                metadata={"symbol": str(request.symbol), "mode": mode_tag},
            )
        )

        if mode_tag == _EXCHANGE_DEMO_TAG:
            self._mirror_to_demo_venue(request=request, order=row)

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

    def _demo_routing_enabled(self) -> bool:
        """Demo mirroring is only active in demo mode with a wired provider.

        Real trading being disabled is an invariant guaranteed earlier in
        :meth:`place_paper_order`; we re-check defensively here.
        """
        return (
            not self._settings.real_trading_enabled
            and self._settings.exchange_demo_active
            and self._exchange_execution is not None
        )

    def _mirror_to_demo_venue(self, *, request: PaperOrderRequest, order: Order) -> None:
        """Best-effort mirror of the paper fill onto the BloFin demo venue.

        Failures are audited and swallowed: the internal paper order remains the
        source of truth, and a demo-venue outage must not break paper trading.
        """
        assert self._exchange_execution is not None  # guarded by caller
        inst_id = to_blofin_inst_id(str(request.symbol))
        exchange_order = ExchangeOrder(
            internal_order_id=order.id,
            organization_id=order.organization_id,
            exchange="blofin-demo",
            exchange_mode=_EXCHANGE_DEMO_TAG,
            inst_id=inst_id,
            symbol=str(request.symbol),
            side=request.side.value,
            order_type=request.type.value,
            size=request.size,
            price=request.price,
            status="submitted",
        )
        try:
            result = self._exchange_execution.place_order(
                ExchangeOrderRequest(
                    symbol=str(request.symbol),
                    inst_id=inst_id,
                    side=request.side,
                    order_type=request.type,
                    size=request.size,
                    price=request.price,
                    reduce_only=request.reduce_only,
                    client_order_id=request.idempotency_key,
                )
            )
        except Exception as exc:  # demo mirror is best-effort; never break paper
            logger.warning(
                "exchange_demo_order_failed",
                inst_id=inst_id,
                error=type(exc).__name__,
            )
            exchange_order.status = "failed"
            self._exchange_orders.add(exchange_order)
            self._audit.record(
                AuditRecordCreate(
                    request_id=request.idempotency_key,
                    trace_id=request.idempotency_key,
                    event_type=AuditEventType.EXCHANGE_DEMO_ORDER_FAILED,
                    resource_type="exchange_order",
                    resource_id=str(exchange_order.id),
                    organization_id=order.organization_id,
                    user_id=order.user_id,
                    actor_type=ActorType.SYSTEM,
                    metadata={"inst_id": inst_id, "mode": _EXCHANGE_DEMO_TAG},
                )
            )
            return

        self._persist_demo_result(exchange_order=exchange_order, result=result)
        order.exchange_order_id = result.exchange_order_id or order.exchange_order_id
        self._audit.record(
            AuditRecordCreate(
                request_id=request.idempotency_key,
                trace_id=request.idempotency_key,
                event_type=AuditEventType.EXCHANGE_DEMO_ORDER_CREATED,
                resource_type="exchange_order",
                resource_id=str(exchange_order.id),
                organization_id=order.organization_id,
                user_id=order.user_id,
                actor_type=ActorType.SYSTEM,
                metadata={
                    "inst_id": inst_id,
                    "mode": _EXCHANGE_DEMO_TAG,
                    "exchange_order_id": result.exchange_order_id,
                },
            )
        )

    def _persist_demo_result(
        self, *, exchange_order: ExchangeOrder, result: ExchangeOrderResult
    ) -> None:
        exchange_order.exchange_order_id = result.exchange_order_id or None
        exchange_order.status = result.status
        exchange_order.filled_size = result.filled_size or Decimal("0")
        exchange_order.average_price = result.average_price
        self._exchange_orders.add(exchange_order)
        for fill in result.fills:
            self._exchange_fills.add(
                ExchangeFill(
                    exchange_order_id=exchange_order.id,
                    fill_id=fill.fill_id or None,
                    price=fill.price,
                    size=fill.size,
                    fee=fill.fee,
                    fee_currency=fill.fee_currency,
                )
            )

    def _create_or_update_position(self, *, proposal, order: Order) -> None:
        direction = TradeDirection.LONG if order.side.value == "buy" else TradeDirection.SHORT
        position = Position(
            organization_id=order.organization_id,
            user_id=order.user_id,
            strategy_id=proposal.strategy_id,
            linked_proposal_id=proposal.id,
            symbol=str(order.symbol),
            direction=direction,
            size=order.size,
            entry_price=order.price or proposal.entry_price,
            leverage=proposal.leverage,
            stop_loss=proposal.stop_loss,
            take_profits=proposal.take_profits or [],
            risk_state={
                "source": "paper_execution",
                "proposal_id": str(proposal.id),
                "setup_type": proposal.strategy_id.value,
            },
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
            strategy_id=row.strategy_id,
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

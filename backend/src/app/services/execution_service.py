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
from app.db.models import ExchangeFill, ExchangeOrder, Order, Position, TradeProposal
from app.providers.exchange.base import (
    ExchangeExecutionProvider,
    ExchangeOrderRequest,
    ExchangeOrderResult,
)
from app.providers.exchange.client_order_id import derive_blofin_venue_client_order_id
from app.providers.exchange.mapping import to_blofin_inst_id
from app.providers.exchange.venue_diagnostics import (
    build_demo_mirror_failure_metadata,
    client_order_id_fingerprint,
    endpoint_label,
    log_fields_for_mirror_failure,
)
from app.repositories.approvals import ApprovalRepository
from app.repositories.exchange_orders import ExchangeFillRepository, ExchangeOrderRepository
from app.repositories.orders import OrderRepository
from app.repositories.proposals import ProposalRepository
from app.schemas.approval import ApprovalRequest
from app.schemas.audit import AuditRecordCreate
from app.schemas.common import (
    ActorType,
    ApprovalStatus,
    AuditEventType,
    ExecutionMode,
    OrderSide,
    OrderStatus,
    PositionStatus,
    TradeDirection,
)
from app.schemas.execution import PaperOrder, PaperOrderPlacementResult, PaperOrderRequest
from app.services.audit_service import AuditService
from app.services.market_data_service import MarketDataService
from app.services.paper_execution_risk_gate import BoundPaperPlacement, PaperExecutionRiskGate
from app.services.risk.daily_risk_accounting import DailyRiskAccounting
from app.services.risk.kill_switch import KillSwitchService
from app.services.risk.settings_service import RiskSettingsService
from app.services.risk_service import RiskService

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
        risk_service: RiskService | None = None,
        risk_settings: RiskSettingsService | None = None,
        market_data_service: MarketDataService | None = None,
        kill_switch: KillSwitchService | None = None,
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
        self._risk_service = risk_service or RiskService()
        self._risk_settings = risk_settings or RiskSettingsService(session, audit_service)
        self._market_data = market_data_service
        self._kill_switch = kill_switch or KillSwitchService(session, audit_service, settings)
        self._daily_risk = DailyRiskAccounting(session, self._risk_settings)
        self._risk_gate = PaperExecutionRiskGate(
            risk_service=self._risk_service,
            daily_risk=self._daily_risk,
            kill_switch=self._kill_switch,
        )

    def place_paper_order(self, request: PaperOrderRequest) -> PaperOrderPlacementResult:
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

        # Idempotent replay must short-circuit before fresh risk (open exposure already
        # includes the prior fill for this key). Concurrent first-writers with the same
        # key can still race past this lookup and hit the unique constraint on
        # ``orders.idempotency_key`` (or related daily-risk uniqueness). Current
        # contract: surface IntegrityError; clients retry and converge via this
        # lookup. Server-side Postgres convergence is tracked separately (AT-028).
        existing = self._orders.get_by_idempotency_key(request.idempotency_key)
        if existing is not None:
            return PaperOrderPlacementResult(
                order=self._to_schema(existing),
                created_new=False,
            )

        organization_id = proposal.organization_id
        user_id = proposal.user_id

        # Authoritative kill switch before any new execution side effect (AT-014).
        try:
            self._kill_switch.assert_execution_allowed(
                organization_id=organization_id,
                user_id=user_id,
            )
        except TradingPolicyError as exc:
            self._audit_reject(
                request,
                reason=str(exc.details.get("reason", "kill_switch_active")),
            )
            raise

        approval_schema = ApprovalRequest.model_validate(approval, from_attributes=True)
        try:
            bound = self._risk_gate.evaluate(
                proposal=proposal,
                approval=approval_schema,
                request=request,
            )
        except TradingPolicyError as exc:
            reason = str(exc.details.get("reason", "risk_gate_blocked"))
            self._audit_reject(
                request,
                reason=reason,
                extra={
                    k: str(v) for k, v in exc.details.items() if k != "reason" and v is not None
                },
            )
            raise

        self._assert_market_data_usable(bound.symbol, request=request)

        # Re-check immediately before fill — covers mid-request activation.
        try:
            self._kill_switch.assert_execution_allowed(
                organization_id=organization_id,
                user_id=user_id,
            )
        except TradingPolicyError as exc:
            self._audit_reject(
                request,
                reason=str(exc.details.get("reason", "kill_switch_active")),
            )
            raise

        # Persist fresh risk evidence on the proposal for auditability.
        proposal.risk_result = bound.risk_result.model_dump(mode="json")
        self._proposals.add(proposal)

        row = Order(
            organization_id=organization_id,
            user_id=user_id,
            strategy_id=proposal.strategy_id,
            proposal_id=request.proposal_id,
            approval_id=request.approval_id,
            mode=ExecutionMode.PAPER,
            symbol=bound.symbol,
            side=OrderSide(bound.side),
            order_type=request.type,
            size=bound.size,
            price=bound.price,
            status=OrderStatus.FILLED,
            reduce_only=request.reduce_only,
            idempotency_key=request.idempotency_key,
            exchange_order_id=f"paper-{uuid.uuid4().hex[:12]}",
        )
        self._orders.add(row)
        self._create_or_update_position(proposal=proposal, order=row, bound=bound)
        # Persist trade_count / open exposure before any subsequent place_paper_order.
        post_fill = self._daily_risk.record_after_paper_fill(
            organization_id=organization_id,
            user_id=user_id,
        )

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
                metadata={
                    "symbol": bound.symbol,
                    "side": bound.side,
                    "mode": mode_tag,
                    "bound_size": str(bound.size),
                    "bound_price": str(bound.price) if bound.price is not None else None,
                    "bound_stop_loss": str(bound.stop_loss),
                    "risk_action": bound.risk_result.action.value,
                    "account_equity": str(bound.account_equity),
                    "open_exposure_before": str(bound.open_exposure_notional),
                    "realized_pnl_today": str(bound.realized_pnl_today),
                    "trade_count_today": str(post_fill.trade_count),
                    "open_exposure_after": str(post_fill.open_exposure_notional),
                },
            )
        )

        if mode_tag == _EXCHANGE_DEMO_TAG:
            self._mirror_to_demo_venue(request=request, order=row, bound=bound)

        return PaperOrderPlacementResult(
            order=self._to_schema(row),
            created_new=True,
        )

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

    def _assert_market_data_usable(self, symbol: str, *, request: PaperOrderRequest) -> None:
        """Fail closed on stale/degraded market data when live data is expected.

        Mock / intentional-fallback provider modes skip this gate so paper tests and
        local mock runs remain usable. When ``provider_mode`` or market provider is
        configured for live/fallback-to-live, stale or fallback tickers refuse placement.
        """
        if self._market_data is None:
            return
        provider_mode = (self._settings.provider_mode or "").lower()
        market_provider = (self._settings.market_data_provider or "").lower()
        if provider_mode == "mock" or market_provider == "mock":
            return

        try:
            ticker = self._market_data.get_ticker(symbol)
        except Exception:
            self._audit_reject(request, reason="market_data_unavailable")
            raise TradingPolicyError(
                "Market data is unavailable; paper execution refused.",
                details={"reason": "market_data_unavailable", "symbol": symbol},
            ) from None

        meta = ticker.meta
        if meta.is_stale or meta.fallback_used:
            self._audit_reject(
                request,
                reason="market_data_degraded",
                extra={
                    "is_stale": str(meta.is_stale),
                    "fallback_used": str(meta.fallback_used),
                },
            )
            raise TradingPolicyError(
                "Market data is stale or degraded; paper execution refused.",
                details={
                    "reason": "market_data_degraded",
                    "symbol": symbol,
                    "is_stale": str(meta.is_stale),
                    "fallback_used": str(meta.fallback_used),
                },
            )

    def _mirror_to_demo_venue(
        self,
        *,
        request: PaperOrderRequest,
        order: Order,
        bound: BoundPaperPlacement,
    ) -> None:
        """Best-effort mirror of the paper fill onto the BloFin demo venue.

        Failures are audited and swallowed: the internal paper order remains the
        source of truth, and a demo-venue outage must not break paper trading.
        """
        assert self._exchange_execution is not None  # guarded by caller

        inst_id = to_blofin_inst_id(bound.symbol)
        venue_client_order_id = derive_blofin_venue_client_order_id(request.idempotency_key)
        bound_side = OrderSide(bound.side)
        exchange_order = ExchangeOrder(
            internal_order_id=order.id,
            organization_id=order.organization_id,
            exchange="blofin-demo",
            exchange_mode=_EXCHANGE_DEMO_TAG,
            inst_id=inst_id,
            symbol=bound.symbol,
            side=bound.side,
            order_type=request.type.value,
            size=bound.size,
            price=bound.price,
            venue_client_order_id=venue_client_order_id,
            status="submitted",
        )
        try:
            result = self._exchange_execution.place_order(
                ExchangeOrderRequest(
                    symbol=bound.symbol,
                    inst_id=inst_id,
                    side=bound_side,
                    order_type=request.type,
                    size=bound.size,
                    price=bound.price,
                    reduce_only=request.reduce_only,
                    client_order_id=venue_client_order_id,
                )
            )
        except Exception as exc:  # demo mirror is best-effort; never break paper
            failure_meta = build_demo_mirror_failure_metadata(
                exc=exc,
                request=request,
                paper_order_id=str(order.id),
                inst_id=inst_id,
                exchange_mode=_EXCHANGE_DEMO_TAG,
                endpoint_name=endpoint_label("POST", "/api/v1/trade/order"),
                venue_client_order_id=venue_client_order_id,
            )
            logger.warning(
                "exchange_demo_order_failed",
                **log_fields_for_mirror_failure(
                    exc=exc,
                    inst_id=inst_id,
                    request=request,
                    paper_order_id=str(order.id),
                    venue_client_order_id=venue_client_order_id,
                ),
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
                    metadata=failure_meta,
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
                    "venue_client_order_id_prefix": venue_client_order_id[:8],
                    "client_order_id_hash": client_order_id_fingerprint(request.idempotency_key),
                    "position_mode": result.position_mode,
                    "position_side": result.position_side,
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

    def _create_or_update_position(
        self,
        *,
        proposal: TradeProposal,
        order: Order,
        bound: BoundPaperPlacement,
    ) -> None:
        direction = TradeDirection.LONG if order.side.value == "buy" else TradeDirection.SHORT
        position = Position(
            organization_id=order.organization_id,
            user_id=order.user_id,
            strategy_id=proposal.strategy_id,
            linked_proposal_id=proposal.id,
            symbol=str(order.symbol),
            direction=direction,
            size=bound.size,
            entry_price=bound.price or bound.entry_price,
            leverage=proposal.leverage,
            stop_loss=bound.stop_loss,
            take_profits=proposal.take_profits or [],
            risk_state={
                "source": "paper_execution",
                "proposal_id": str(proposal.id),
                "setup_type": proposal.strategy_id.value,
                "risk_action": bound.risk_result.action.value,
                "account_equity": str(bound.account_equity),
            },
            status=PositionStatus.OPEN,
            opened_at=datetime.now(UTC),
        )
        self._session.add(position)
        self._session.flush()

    def _audit_reject(
        self,
        request: PaperOrderRequest,
        *,
        reason: str,
        extra: dict[str, str] | None = None,
    ) -> None:
        metadata: dict[str, object] = {"reason": reason, "mode": "paper"}
        if extra:
            metadata.update(extra)
        # Durable outside the business UoW — reject paths raise before route commit.
        self._audit.record_durable_isolated(
            AuditRecordCreate(
                request_id=request.idempotency_key,
                trace_id=request.idempotency_key,
                event_type=AuditEventType.PAPER_ORDER_REJECTED,
                resource_type="paper_order",
                resource_id=str(request.proposal_id),
                actor_type=ActorType.SYSTEM,
                metadata=metadata,
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

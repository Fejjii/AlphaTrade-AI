"""Owner-confirmed manual demo origin using existing claim, fences and venue facts.

No strategy approval or synthetic Candidate. Account history remains held until
operator review; this first-entry acceptance capability does not enable repeat
entries or synthesize exit outcomes.
"""

from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ForbiddenError, NotFoundError, TradingPolicyError
from app.core.execution_credentials import blofin_execution_authorized, manual_demo_access_requested
from app.db.models import (
    AuditLog,
    ExecutionAccount,
    ExecutionCommand,
    ExecutionProjection,
    JournalTrade,
    TradeProposal,
    VenueSubmitEffect,
)
from app.db.models import TradePlanRevision as PlanRow
from app.providers.exchange.demo_preflight import failure_diagnostics
from app.providers.exchange.factory import build_blofin_client
from app.providers.exchange.governed_blofin import DemoFill, GovernedBloFinDemoProvider
from app.schemas.audit import AuditRecordCreate
from app.schemas.common import (
    ActorType,
    AuditEventType,
    JournalEntryMethod,
    JournalTradeSource,
    JournalTradeStatus,
    MembershipRole,
    ProposalStatus,
    RiskAction,
    RiskSeverity,
    TradeDirection,
)
from app.schemas.execution_protocol import (
    ExecutePaperPlanRequest,
    ExecutionCommandOutcome,
    VenueSubmitEffectState,
)
from app.schemas.manual_demo import (
    ManualDemoConfirmation,
    ManualDemoPreview,
    ManualDemoPreviewRequest,
    ManualDemoStatus,
)
from app.schemas.risk import KillSwitchMutationRequest, RiskCheckRequest
from app.schemas.trade_plan import (
    AuthorizationChannel,
    AuthorizationDecision,
    TradePlanRevision,
    TradePlanRevisionSemantic,
)
from app.security.tenant import TenantContext
from app.services.approval_service import ApprovalService
from app.services.audit_service import AuditService
from app.services.canonical_serialization import canonical_sha256
from app.services.execution_account_service import ExecutionAccountService
from app.services.execution_claim import ExecutionClaimHooks, PaperPlanClaimService
from app.services.manual_demo_plan import MANUAL_DEMO_ORIGIN, build_manual_plan
from app.services.mappers.trade_plan_mapper import trade_plan_revision_to_schema
from app.services.planned_reward_risk import PlannedRewardRiskError, planned_reward_risk
from app.services.risk.daily_risk_accounting import DailyRiskAccounting
from app.services.risk.engine import RiskEngine
from app.services.risk.kill_switch import KillSwitchService
from app.services.risk.rules import RiskEvaluationContext
from app.services.risk.settings_service import RiskSettingsService
from app.services.safety_epoch import SafetyEpochService
from app.services.venue_submit_dispatcher import VenueSubmitDispatcher

logger = structlog.get_logger(__name__)


class ManualDemoService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        *,
        provider: GovernedBloFinDemoProvider | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.session, self.settings, self.clock = session, settings, clock
        self.provider = provider
        self.audit = AuditService(session, strict_mode=True)
        self.risk_settings = RiskSettingsService(session, self.audit)
        self.epochs = SafetyEpochService(session, settings, self.risk_settings)

    def _scope(self, tenant: TenantContext) -> ExecutionAccount:
        if tenant.membership_role is not MembershipRole.OWNER:
            raise ForbiddenError("Only the authenticated owner can run a manual demo test.")
        if not manual_demo_access_requested(self.settings) or not blofin_execution_authorized(
            self.settings
        ):
            raise TradingPolicyError(
                "Manual demo capability is disarmed or credentials are sealed."
            )
        account = ExecutionAccountService(self.session).status(tenant).account
        if account is None or (
            str(tenant.organization_id),
            str(tenant.user_id),
            str(account.id),
        ) != (
            self.settings.governed_blofin_demo_organization_id,
            self.settings.governed_blofin_demo_user_id,
            self.settings.governed_blofin_demo_account_id,
        ):
            raise TradingPolicyError(
                "Manual demo account scope does not match the configured pins."
            )
        row = self.session.get(ExecutionAccount, account.id)
        assert row is not None
        return row

    def _provider(self) -> GovernedBloFinDemoProvider:
        if self.provider is None:
            self.provider = GovernedBloFinDemoProvider(
                build_blofin_client(self.settings), clock=self.clock
            )
        return self.provider

    def _plan(self, tenant: TenantContext, revision_id: UUID) -> TradePlanRevision:
        account = self._scope(tenant)
        row = self.session.scalar(
            select(PlanRow).where(
                PlanRow.id == revision_id,
                PlanRow.organization_id == tenant.organization_id,
                PlanRow.user_id == tenant.user_id,
                PlanRow.account_id == account.id,
                PlanRow.plan_authority == MANUAL_DEMO_ORIGIN,
            )
        )
        if row is None:
            raise NotFoundError("Manual demo plan not found in your account.")
        plan = trade_plan_revision_to_schema(row)
        semantic = TradePlanRevisionSemantic.model_validate(row.semantic_payload)
        if (
            plan.schema_version != "ManualDemoTradePlanV1"
            or canonical_sha256(semantic) != plan.content_hash
        ):
            raise TradingPolicyError("Manual demo plan integrity failed.")
        return plan

    def _risk(self, tenant: TenantContext, plan: TradePlanRevisionSemantic) -> None:
        try:
            planned_reward_risk(plan)
        except PlannedRewardRiskError as exc:
            raise TradingPolicyError(str(exc), details={"reason": exc.reason}) from exc
        daily = DailyRiskAccounting(
            self.session, self.risk_settings, clock=self.clock
        ).sync_from_portfolio(organization_id=tenant.organization_id, user_id=tenant.user_id)
        user = self.risk_settings.get(
            organization_id=tenant.organization_id, user_id=tenant.user_id
        )
        observed = {item.name: item.result_value for item in plan.calculation_inputs}
        equity = min(daily.account_equity, observed["venue_equity"], observed["venue_available"])
        if (
            equity <= 0
            or plan.risk_and_exits.maximum_loss.value
            > equity * min(user.max_risk_per_trade_percent, Decimal("1")) / 100
        ):
            raise TradingPolicyError(
                "Manual demo maximum planned loss exceeds the per-trade risk limit."
            )
        result = RiskEngine().evaluate(
            RiskCheckRequest(
                symbol="BTCUSDT",
                direction=TradeDirection.LONG if plan.side.value == "BUY" else TradeDirection.SHORT,
                entry_price=plan.entry_zone.upper,
                stop_loss=plan.risk_and_exits.stop.value,
                position_size=plan.quantity.value * plan.instrument_rules.contract_multiplier,
                leverage=plan.risk_and_exits.leverage,
                account_equity=equity,
            ),
            context=RiskEvaluationContext(
                daily_locked=daily.daily_locked,
                realized_pnl_today=daily.realized_pnl,
                daily_loss_limit=daily.daily_loss_limit,
                trades_today=daily.trade_count,
                kill_switch_active=self.epochs.organization_kill_active(tenant.organization_id),
                protect_green_day=user.green_day_protection_enabled,
                open_exposure_notional=daily.open_exposure_notional,
                is_weekend=self.clock().weekday() >= 5,
                overtrading=daily.trade_count >= user.max_trades_per_day,
            ),
        )
        if result.action is RiskAction.BLOCK:
            raise TradingPolicyError(result.explanation)

    def preview(
        self, tenant: TenantContext, request: ManualDemoPreviewRequest
    ) -> ManualDemoPreview:
        account_id = self._scope(tenant).id
        self.session.commit()  # No DB lock/transaction across venue reads.
        stage = "provider_initialization"
        try:
            provider = self._provider()
            stage = "snapshot"
            snapshot = provider.snapshot(symbol=request.symbol, now=self.clock())
        except Exception as exc:
            diagnostics = failure_diagnostics(exc, stage=stage)
            logger.warning(
                "manual_demo_preflight_failed",
                organization_id=str(tenant.organization_id),
                user_id=str(tenant.user_id),
                account_id=str(account_id),
                **diagnostics,
            )
            raise TradingPolicyError(
                "Demo preflight unavailable; preview cannot be saved.",
                details={"preflight": diagnostics},
            ) from exc
        try:
            semantic = build_manual_plan(
                request,
                snapshot,
                organization_id=tenant.organization_id,
                user_id=tenant.user_id,
                account_id=account_id,
                now=self.clock(),
            )
        except (PlannedRewardRiskError, ValueError) as exc:
            raise TradingPolicyError(str(exc)) from exc
        self._risk(tenant, semantic)
        root = TradeProposal(
            id=semantic.plan_id,
            organization_id=tenant.organization_id,
            user_id=tenant.user_id,
            strategy_id=None,
            symbol=request.symbol,
            timeframe="manual",
            plan_root_kind=MANUAL_DEMO_ORIGIN,
            direction=TradeDirection.LONG if request.side.value == "BUY" else TradeDirection.SHORT,
            entry_price=snapshot.price,
            entry_low=semantic.entry_zone.lower,
            entry_high=semantic.entry_zone.upper,
            position_size=request.quantity * snapshot.multiplier,
            leverage=Decimal("1"),
            stop_loss=request.stop,
            take_profits=[str(request.target)],
            invalidation="Explicit owner stop",
            confidence=0,
            risk_level=RiskSeverity.LOW,
            rationale="Manual demo test; no detected strategy",
            status=ProposalStatus.DRAFT,
            approval_required=True,
        )
        self.session.add(root)
        self.session.flush()
        row = PlanRow(
            id=semantic.revision_id,
            plan_id=semantic.plan_id,
            organization_id=tenant.organization_id,
            user_id=tenant.user_id,
            account_id=account_id,
            exchange_account_id=None,
            schema_version=semantic.schema_version,
            operation=semantic.operation,
            strategy_version_id=None,
            setup_definition_id=None,
            candidate_id=None,
            canonical_candidate_id=None,
            compiled_setup_definition_id=None,
            plan_authority=MANUAL_DEMO_ORIGIN,
            expected_account_mode=semantic.expected_account_mode,
            permission_attestation_id=semantic.permission_attestation_id,
            permission_attestation_version=semantic.permission_attestation_version,
            execution_venue=semantic.execution_venue,
            execution_instrument=semantic.execution_instrument,
            execution_policy_version=semantic.execution_policy_version,
            valid_from=semantic.valid_from,
            valid_until=semantic.valid_until,
            semantic_payload=semantic.model_dump(mode="json"),
            correlation_id=uuid4(),
            content_hash=canonical_sha256(semantic),
            presentation_metadata={"display_title": "Manual demo test"},
        )
        self.session.add(row)
        self.session.flush()
        root.latest_plan_revision_id = row.id
        self._audit(
            tenant,
            AuditEventType.TRADE_PROPOSAL_CREATED,
            row.id,
            "manual_demo_preview",
            {
                "plan_content_hash": row.content_hash,
                "origin": MANUAL_DEMO_ORIGIN,
                "venue": "BLOFIN_DEMO",
            },
        )
        self.session.commit()
        return ManualDemoPreview(
            account_id=account_id,
            revision_id=row.id,
            content_hash=row.content_hash,
            instrument=semantic.execution_instrument,
            side=request.side,
            quantity=request.quantity,
            base_quantity=root.position_size,
            reference_price=snapshot.price,
            entry_lower=semantic.entry_zone.lower,
            entry_upper=semantic.entry_zone.upper,
            stop=request.stop,
            target=request.target,
            maximum_planned_loss=semantic.risk_and_exits.maximum_loss.value,
            gross_reward_risk=planned_reward_risk(semantic).ratio,
            valid_until=semantic.valid_until,
        )

    def confirm(
        self, tenant: TenantContext, confirmation: ManualDemoConfirmation
    ) -> ManualDemoStatus:
        plan = self._plan(tenant, confirmation.revision_id)
        if confirmation.confirm is not True or confirmation.label != "manual demo test":
            raise TradingPolicyError("Explicit manual demo test confirmation is required.")
        if confirmation.content_hash != plan.content_hash:
            raise TradingPolicyError("Confirmation must match the exact preview hash.")
        # Serialize duplicate owner confirmations on this immutable revision.
        # The shared claim service then locks idempotency → account epoch → risk,
        # retaining the same lock order as automatic strategy claims.
        self.session.scalar(
            select(PlanRow.id)
            .where(
                PlanRow.id == plan.revision_id,
                PlanRow.organization_id == tenant.organization_id,
                PlanRow.user_id == tenant.user_id,
            )
            .with_for_update()
        )
        existing = self.session.scalar(
            select(ExecutionCommand).where(
                ExecutionCommand.organization_id == tenant.organization_id,
                ExecutionCommand.user_id == tenant.user_id,
                ExecutionCommand.account_id == plan.account_id,
                ExecutionCommand.revision_id == plan.revision_id,
            )
        )
        if existing is not None:
            command_id = existing.id
            self.session.commit()
            return self.reconcile(tenant, command_id)  # Never resend a replay/restarted command.
        self._risk(tenant, plan)
        approval = ApprovalService(self.session, self.audit, clock=self.clock)
        pending = approval.create_for_plan_revision(
            revision_id=plan.revision_id,
            organization_id=tenant.organization_id,
            user_id=tenant.user_id,
            approval_reason="Owner confirmed manual demo test exact preview",
        )
        authorization = approval.issue_authorization(
            approval_id=pending.id,
            decision=AuthorizationDecision.APPROVE,
            organization_id=tenant.organization_id,
            user_id=tenant.user_id,
            channel=AuthorizationChannel.WEB,
            manual_demo_confirmation_hash=confirmation.content_hash,
        )
        self._audit(
            tenant,
            AuditEventType.APPROVAL_DECISION,
            plan.revision_id,
            "manual_demo_confirmed",
            {
                "origin": MANUAL_DEMO_ORIGIN,
                "plan_content_hash": plan.content_hash,
                "authorization_id": str(authorization.authorization_id),
            },
        )
        result = PaperPlanClaimService(
            self.session,
            self.settings,
            self.epochs,
            clock=self.clock,
            hooks=ExecutionClaimHooks(revalidate=lambda **kw: self._revalidate(tenant, kw["plan"])),
        ).claim(
            ExecutePaperPlanRequest(
                organization_id=tenant.organization_id,
                user_id=tenant.user_id,
                account_id=plan.account_id,
                revision_id=plan.revision_id,
                authorization_id=authorization.authorization_id,
                idempotency_key=f"manual-demo:{plan.revision_id}",
            )
        )
        command_id = result.command_id
        self.session.commit()  # Durable exact authority and reservation before provider IO.
        if result.outcome is ExecutionCommandOutcome.ALLOW:
            dispatch = self._dispatcher()
            owner = f"manual-demo:{command_id}"
            effect = dispatch.lease_effect(command_id=command_id, owner=owner)
            fence = int(effect.fencing_token)
            effect = dispatch.authorize_dispatch(
                command_id=command_id, owner=owner, fencing_token=fence
            )
            if effect.state is VenueSubmitEffectState.DISPATCH_AUTHORIZED:
                dispatch.attempt_governed_demo_send(
                    command_id=command_id,
                    owner=owner,
                    fencing_token=fence,
                    provider=self._provider(),
                    settings=self.settings,
                    plan=plan,
                )
            self.session.commit()
        return self.reconcile(tenant, command_id)

    def _revalidate(self, tenant: TenantContext, plan: TradePlanRevision) -> str | None:
        try:
            self._scope(tenant)
            self._risk(tenant, plan)
        except TradingPolicyError:
            return "manual_demo_risk_or_scope_refused"
        return None

    def _dispatcher(self) -> VenueSubmitDispatcher:
        return VenueSubmitDispatcher(self.session, self.epochs, clock=self.clock)

    def _command(
        self, tenant: TenantContext, command_id: UUID
    ) -> tuple[ExecutionCommand, TradePlanRevision, VenueSubmitEffect | None]:
        self._scope(tenant)
        command = self.session.scalar(
            select(ExecutionCommand).where(
                ExecutionCommand.id == command_id,
                ExecutionCommand.organization_id == tenant.organization_id,
                ExecutionCommand.user_id == tenant.user_id,
            )
        )
        if command is None:
            raise NotFoundError("Manual demo command not found.")
        plan = self._plan(tenant, command.revision_id)
        if command.account_id != plan.account_id or command.plan_content_hash != plan.content_hash:
            raise TradingPolicyError("Manual demo command lineage failed.")
        effect = self.session.scalar(
            select(VenueSubmitEffect).where(VenueSubmitEffect.command_id == command.id)
        )
        return command, plan, effect

    def reconcile(self, tenant: TenantContext, command_id: UUID) -> ManualDemoStatus:
        command, plan, effect = self._command(tenant, command_id)
        status = command.blocked_reason_code or "not_sent"
        protection = "unverified"
        evidence = None
        if effect is not None and effect.state not in {
            VenueSubmitEffectState.CREATED,
            VenueSubmitEffectState.LEASED,
            VenueSubmitEffectState.PROVEN_UNSENT,
        }:
            client_id = effect.client_order_id
            self.session.commit()
            try:
                evidence = self._provider().reconcile(plan=plan, client_order_id=client_id)
            except Exception:
                status = "reconciliation_unavailable_operator_hold"
            else:
                status = "ambiguous_operator_hold" if evidence is None else evidence.status
        if evidence is not None:
            self.epochs.lock_epoch(
                organization_id=tenant.organization_id, account_id=plan.account_id
            )
            self._dispatcher().record_demo_order(
                command_id=command_id, rejected=evidence.status == "rejected" and not evidence.fills
            )
            receipt = {
                "origin": MANUAL_DEMO_ORIGIN,
                "venue_order_id": evidence.order_id,
                "client_order_id": evidence.client_order_id,
                "native_state": evidence.status,
                "fill_identities": [f.identity for f in evidence.fills],
                "protection_status": evidence.protection_status,
                "protection_order_ids": list(evidence.protection_order_ids),
                "instrument": plan.execution_instrument,
                "planned_stop": str(plan.risk_and_exits.stop.value),
                "planned_target": str(plan.risk_and_exits.targets[0].price.value),
                "filled_quantity": str(sum((f.quantity for f in evidence.fills), Decimal("0"))),
                "plan_content_hash": plan.content_hash,
            }
            receipt_hash = canonical_sha256(receipt)
            prior_receipt = self.session.scalar(
                select(AuditLog.id).where(
                    AuditLog.organization_id == tenant.organization_id,
                    AuditLog.user_id == tenant.user_id,
                    AuditLog.resource_id == str(command_id),
                    AuditLog.resource_type == "manual_demo_test",
                    AuditLog.redacted_metadata["receipt_hash"].as_string() == receipt_hash,
                )
            )
            if prior_receipt is None:
                self._audit(
                    tenant,
                    AuditEventType.EXCHANGE_DEMO_ORDER_CREATED,
                    command_id,
                    "manual_demo_native_order_receipt",
                    {"receipt_hash": receipt_hash, **receipt},
                )
            fees = sum((f.fee for f in evidence.fills), Decimal("0"))
            for fact in evidence.fills:
                fill = self._dispatcher().apply_unique_fill(
                    command_id=command_id,
                    fill_quantity=fact.quantity,
                    fill_price=fact.price,
                    source_identity=fact.identity,
                    occurred_at=fact.occurred_at,
                    venue_source="blofin_demo",
                )
                if fill.replayed:
                    prior_fee = self.session.scalar(
                        select(AuditLog).where(
                            AuditLog.organization_id == tenant.organization_id,
                            AuditLog.user_id == tenant.user_id,
                            AuditLog.resource_type == "manual_demo_test",
                            AuditLog.resource_id == str(command_id),
                            AuditLog.action == AuditEventType.POSITION_UPDATED,
                            AuditLog.redacted_metadata["fill_identity"].as_string()
                            == fact.identity,
                        )
                    )
                    if prior_fee is None or Decimal(prior_fee.redacted_metadata["fee"]) != fact.fee:
                        raise TradingPolicyError(
                            "Verified manual demo fill fee conflicts with its stored receipt; "
                            "operator review required."
                        )
                if not fill.replayed:
                    self._audit(
                        tenant,
                        AuditEventType.POSITION_UPDATED,
                        command_id,
                        "manual_demo_actual_fill",
                        {
                            "fill_identity": fact.identity,
                            "fee": str(fact.fee),
                            "fee_currency": "USDT",
                            "protection": evidence.protection_status,
                        },
                    )
            protection = evidence.protection_status
            self._journal(tenant, command, plan, evidence.fills, fees, protection)
            if evidence.status in {"canceled", "cancelled", "expired"}:
                self._dispatcher().record_demo_terminal(command_id=command_id)
            if evidence.fills and not evidence.protected:
                KillSwitchService(self.session, self.audit, self.settings).activate(
                    organization_id=tenant.organization_id,
                    actor_user_id=tenant.user_id,
                    payload=KillSwitchMutationRequest(
                        confirm=True,
                        reason="Manual demo protection is not verified; operator action required",
                    ),
                )
                status = "protection_failed_operator_hold"
            elif evidence.fills:
                status = (
                    "filled_protected"
                    if sum((f.quantity for f in evidence.fills), Decimal("0"))
                    == plan.quantity.value
                    else "partial_fill_protected_operator_hold"
                )
            if any(
                not plan.entry_zone.lower <= f.price <= plan.entry_zone.upper
                for f in evidence.fills
            ):
                KillSwitchService(self.session, self.audit, self.settings).activate(
                    organization_id=tenant.organization_id,
                    actor_user_id=tenant.user_id,
                    payload=KillSwitchMutationRequest(
                        confirm=True,
                        reason="Manual demo fill exceeded the planned entry range; operator review",
                    ),
                )
                status = "actual_fill_outside_plan_operator_hold"
            self.session.commit()
        projection = self.session.scalar(
            select(ExecutionProjection)
            .join(VenueSubmitEffect, VenueSubmitEffect.receipt_id == ExecutionProjection.receipt_id)
            .where(VenueSubmitEffect.command_id == command_id)
        )
        trade = self.session.scalar(
            select(JournalTrade).where(
                JournalTrade.organization_id == tenant.organization_id,
                JournalTrade.user_id == tenant.user_id,
                JournalTrade.execution_lifecycle_id == command_id,
            )
        )
        missing = [
            "Exit and realized outcome are not reconciled by this first-entry manual capability.",
            "Account remains held for operator review; no automatic repeat entry.",
        ]
        cancel_requested = self.session.scalar(
            select(AuditLog.id).where(
                AuditLog.organization_id == tenant.organization_id,
                AuditLog.user_id == tenant.user_id,
                AuditLog.resource_id == str(command_id),
                AuditLog.action == AuditEventType.MANUAL_DEMO_CANCEL_REQUESTED,
            )
        )
        if cancel_requested and (
            evidence is None
            or evidence.status not in {"canceled", "cancelled", "expired", "filled"}
        ):
            missing.append(
                "Cancellation requested; terminal cancellation is not verified. Do not retry."
            )
        if evidence is None or not evidence.fills:
            missing.append("No actual venue fill has been verified.")
        if protection != "verified":
            missing.append("Stop and target protection are not verified.")
        return ManualDemoStatus(
            revision_id=plan.revision_id,
            command_id=command_id,
            client_order_id=effect.client_order_id if effect else "",
            venue_order_id=evidence.order_id if evidence else None,
            protection_order_ids=evidence.protection_order_ids if evidence else (),
            status=status,
            filled_quantity=projection.filled_quantity if projection else Decimal("0"),
            remaining_quantity=projection.remaining_quantity if projection else plan.quantity.value,
            average_fill_price=projection.weighted_price if projection else None,
            fees=trade.fees if trade else None,
            protection=protection,
            journal_trade_id=trade.id if trade else None,
            missing_evidence=tuple(missing),
        )

    def _journal(
        self,
        tenant: TenantContext,
        command: ExecutionCommand,
        plan: TradePlanRevision,
        fills: tuple[DemoFill, ...],
        fees: Decimal,
        protection: str,
    ) -> None:
        if not fills:
            return
        trade = self.session.scalar(
            select(JournalTrade).where(
                JournalTrade.organization_id == tenant.organization_id,
                JournalTrade.execution_lifecycle_id == command.id,
            )
        )
        if trade is None:
            trade = JournalTrade(
                organization_id=tenant.organization_id,
                user_id=tenant.user_id,
                source=JournalTradeSource.MANUAL_DEMO_TEST,
                entry_method=JournalEntryMethod.MANUAL,
                symbol="BTCUSDT",
                exchange="BLOFIN_DEMO",
                timeframe="manual",
                direction=TradeDirection.LONG if plan.side.value == "BUY" else TradeDirection.SHORT,
                strategy_label="Manual demo test — excluded from strategy validation",
                thesis="Supervised manual demo test; no detected or approved strategy claimed",
                planned_entry_price=plan.basis_policy.execution_price.value,
                planned_stop_price=plan.risk_and_exits.stop.value,
                planned_targets=[
                    {
                        "price": str(plan.risk_and_exits.targets[0].price.value),
                        "quantity_fraction": "1",
                        "label": "TP1",
                    }
                ],
                planned_risk_amount=plan.risk_and_exits.maximum_loss.value,
                linked_proposal_id=plan.plan_id,
                execution_lifecycle_id=command.id,
                account_id=plan.account_id,
                leverage=Decimal("1"),
                tags=["manual demo test", "excluded from strategy validation"],
            )
            self.session.add(trade)
        total = sum((f.quantity for f in fills), Decimal("0"))
        trade.entry_price = sum((f.quantity * f.price for f in fills), Decimal("0")) / total
        trade.size = total * plan.instrument_rules.contract_multiplier
        trade.entry_time = min(f.occurred_at for f in fills)
        trade.fees = fees
        trade.status = JournalTradeStatus.OPEN
        trade.entry_plan = (
            f"Actual BloFin demo fills; protection {protection}; plan {plan.revision_id}"
        )
        self.session.flush()

    def cancel(self, tenant: TenantContext, command_id: UUID) -> ManualDemoStatus:
        _command, plan, effect = self._command(tenant, command_id)
        if effect is None:
            raise TradingPolicyError("No venue order identity to cancel.")
        client_id = effect.client_order_id
        self.session.commit()
        # Reconcile first; never cancel protection or guess a venue order identity.
        evidence = self._provider().reconcile(plan=plan, client_order_id=client_id)
        if evidence is None or evidence.status not in {"live", "partially_filled"}:
            return self.reconcile(tenant, command_id)
        self.epochs.lock_epoch(organization_id=tenant.organization_id, account_id=plan.account_id)
        prior = self.session.scalar(
            select(AuditLog.id).where(
                AuditLog.organization_id == tenant.organization_id,
                AuditLog.user_id == tenant.user_id,
                AuditLog.resource_id == str(command_id),
                AuditLog.action == AuditEventType.MANUAL_DEMO_CANCEL_REQUESTED,
            )
        )
        if prior is None:
            self._audit(
                tenant,
                AuditEventType.MANUAL_DEMO_CANCEL_REQUESTED,
                command_id,
                "manual_demo_cancel_requested",
                {
                    "order_id": evidence.order_id,
                    "client_order_id": client_id,
                    "origin": MANUAL_DEMO_ORIGIN,
                },
            )
        self.session.commit()  # Durable cancellation intent before one POST; never retry.
        if prior is None:
            # Any uncertain cancellation is followed by reads, never another POST.
            with suppress(Exception):
                self._provider().cancel_entry(plan=plan, evidence=evidence)
        return self.reconcile(tenant, command_id)

    def _audit(
        self,
        tenant: TenantContext,
        event: AuditEventType,
        resource: UUID,
        action: str,
        metadata: dict[str, object],
    ) -> None:
        self.audit.record(
            AuditRecordCreate(
                request_id=str(resource),
                trace_id=str(resource),
                event_type=event,
                resource_type="manual_demo_test",
                resource_id=str(resource),
                actor_type=ActorType.USER,
                action=action,
                organization_id=tenant.organization_id,
                user_id=tenant.user_id,
                metadata={"operation": action, **metadata},
            )
        )

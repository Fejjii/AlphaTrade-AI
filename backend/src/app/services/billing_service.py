"""Billing orchestration: customers, checkout, portal, webhooks, plan quotas."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy.orm import Session

from app.billing.plans import PLAN_FREE, get_plan, list_plans, plan_to_quota_update
from app.core.config import Settings
from app.core.errors import NotFoundError, ServiceUnavailableError, ValidationAppError
from app.db.models import (
    BillingCustomer as BillingCustomerModel,
)
from app.db.models import (
    BillingEvent as BillingEventModel,
)
from app.db.models import (
    Subscription as SubscriptionModel,
)
from app.db.models import (
    WebhookEvent as WebhookEventModel,
)
from app.providers.billing.base import BillingProvider
from app.providers.billing.factory import resolve_billing_provider
from app.providers.billing.stripe_provider import redact_stripe_payload
from app.repositories.billing import (
    BillingCustomerRepository,
    BillingEventRepository,
    SubscriptionRepository,
    WebhookEventRepository,
)
from app.schemas.audit import AuditRecordCreate
from app.schemas.billing import (
    BillingCustomerCreate,
    BillingCustomerStatus,
    BillingCustomerView,
    BillingEventStatus,
    BillingProviderName,
    BillingStatusResponse,
    CheckoutRequest,
    CheckoutResponse,
    PortalResponse,
    SubscriptionPlanView,
    SubscriptionStatus,
    SubscriptionView,
    UsageExportRequest,
    UsageExportResponse,
)
from app.schemas.common import AuditEventType, AuditResult, AuditSeverity
from app.services.audit_service import AuditService
from app.services.quota_service import QuotaService
from app.services.usage_export_service import UsageExportService

logger = structlog.get_logger(__name__)

_SUPPORTED_WEBHOOK_EVENTS = frozenset(
    {
        "checkout.session.completed",
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
        "invoice.paid",
        "invoice.payment_failed",
    }
)


class BillingService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        *,
        provider: BillingProvider | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._provider = provider or resolve_billing_provider(settings)
        self._customers = BillingCustomerRepository(session)
        self._subscriptions = SubscriptionRepository(session)
        self._billing_events = BillingEventRepository(session)
        self._webhooks = WebhookEventRepository(session)
        self._audit = audit_service or AuditService(session)
        self._quota = QuotaService(session, audit_service=self._audit)

    @property
    def provider_name(self) -> BillingProviderName:
        return self._provider.provider_name

    def list_plans(self) -> list[SubscriptionPlanView]:
        return list_plans()

    def get_status(self, organization_id: uuid.UUID) -> BillingStatusResponse:
        customer = self._customers.get_by_organization(organization_id)
        subscription = self._subscriptions.get_by_organization(organization_id)
        plan_id = subscription.plan_id if subscription else PLAN_FREE
        live_checkout = (
            self._settings.billing_enabled
            and bool(self._settings.stripe_secret_key.strip())
            and self.provider_name is BillingProviderName.STRIPE
        )
        return BillingStatusResponse(
            billing_enabled=self._settings.billing_enabled,
            provider=self.provider_name,
            is_mock=self.provider_name is BillingProviderName.MOCK,
            live_checkout_available=live_checkout,
            current_plan_id=plan_id,
            customer=_customer_view(customer) if customer else None,
            subscription=_subscription_view(subscription) if subscription else None,
        )

    def create_customer(
        self,
        organization_id: uuid.UUID,
        data: BillingCustomerCreate,
        *,
        actor_user_id: uuid.UUID | None,
        billing_email_fallback: str,
        request_id: str | None = None,
    ) -> BillingCustomerView:
        existing = self._customers.get_by_organization(organization_id)
        if existing:
            return _customer_view(existing)

        email = (data.billing_email or billing_email_fallback).strip()
        if not email:
            raise ValidationAppError("billing_email is required.")

        provider_id = self._provider.create_customer(
            organization_id=organization_id,
            billing_email=email,
        )
        row = BillingCustomerModel(
            organization_id=organization_id,
            provider=self.provider_name.value,
            provider_customer_id=provider_id,
            billing_email=email,
            status=BillingCustomerStatus.ACTIVE.value,
        )
        self._customers.add(row)
        self._ensure_subscription(organization_id, PLAN_FREE)
        self._session.flush()

        self._audit.record(
            AuditRecordCreate(
                request_id=request_id or "billing-customer",
                trace_id=request_id or "billing-customer",
                organization_id=organization_id,
                user_id=actor_user_id,
                event_type=AuditEventType.BILLING_CUSTOMER_CREATED,
                resource_type="billing_customer",
                resource_id=str(row.id),
                result=AuditResult.SUCCESS,
                severity=AuditSeverity.INFO,
            )
        )
        return _customer_view(row)

    def create_checkout(
        self,
        organization_id: uuid.UUID,
        body: CheckoutRequest,
        *,
        actor_user_id: uuid.UUID | None,
        request_id: str | None = None,
    ) -> CheckoutResponse:
        plan = get_plan(body.plan_id)
        if plan is None:
            raise NotFoundError(f"Unknown plan: {body.plan_id}")

        customer = self._customers.get_by_organization(organization_id)
        if customer is None:
            raise ValidationAppError("Create a billing customer before checkout.")

        url, session_id = self._provider.create_checkout_session(
            organization_id=organization_id,
            provider_customer_id=customer.provider_customer_id,
            plan_id=plan.plan_id,
        )
        self._audit.record(
            AuditRecordCreate(
                request_id=request_id or "billing-checkout",
                trace_id=request_id or "billing-checkout",
                organization_id=organization_id,
                user_id=actor_user_id,
                event_type=AuditEventType.BILLING_CHECKOUT_CREATED,
                resource_type="billing_checkout",
                resource_id=session_id,
                metadata={"plan_id": plan.plan_id, "is_mock": self.provider_name.value == "mock"},
                result=AuditResult.SUCCESS,
                severity=AuditSeverity.INFO,
            )
        )
        return CheckoutResponse(
            checkout_url=url,
            session_id=session_id,
            is_mock=self.provider_name is BillingProviderName.MOCK,
        )

    def create_portal(
        self,
        organization_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID | None,
        request_id: str | None = None,
    ) -> PortalResponse:
        customer = self._customers.get_by_organization(organization_id)
        if customer is None:
            raise ValidationAppError("Create a billing customer before opening the portal.")

        url = self._provider.create_portal_session(
            provider_customer_id=customer.provider_customer_id,
        )
        self._audit.record(
            AuditRecordCreate(
                request_id=request_id or "billing-portal",
                trace_id=request_id or "billing-portal",
                organization_id=organization_id,
                user_id=actor_user_id,
                event_type=AuditEventType.BILLING_PORTAL_OPENED,
                resource_type="billing_portal",
                resource_id=customer.provider_customer_id,
                result=AuditResult.SUCCESS,
                severity=AuditSeverity.INFO,
            )
        )
        return PortalResponse(
            portal_url=url,
            is_mock=self.provider_name is BillingProviderName.MOCK,
        )

    def export_usage(
        self,
        organization_id: uuid.UUID,
        body: UsageExportRequest,
        *,
        actor_user_id: uuid.UUID | None = None,
        request_id: str | None = None,
    ) -> UsageExportResponse:
        export_service = UsageExportService(self._session)
        result = export_service.export_for_period(
            organization_id,
            period_start=body.period_start,
            period_end=body.period_end,
            provider_name=self.provider_name.value,
        )
        self._provider.record_usage_export(
            organization_id=organization_id,
            batch_id=result.batch_id,
            payload_summary={
                "total_events": result.total_events,
                "total_tokens": result.total_tokens,
                "billing_grade_cost": str(result.billing_grade_cost),
                "cost_is_billing_grade": result.cost_is_billing_grade,
            },
        )
        self._audit.record(
            AuditRecordCreate(
                request_id=request_id or "billing-export",
                trace_id=request_id or "billing-export",
                organization_id=organization_id,
                user_id=actor_user_id,
                event_type=AuditEventType.BILLING_USAGE_EXPORTED,
                resource_type="usage_export_batch",
                resource_id=str(result.batch_id),
                metadata={
                    "cost_is_billing_grade": result.cost_is_billing_grade,
                    "total_events": result.total_events,
                },
                result=AuditResult.SUCCESS,
                severity=AuditSeverity.INFO,
            )
        )
        return result

    def handle_webhook(
        self,
        payload: bytes,
        signature_header: str | None,
        *,
        request_id: str | None = None,
    ) -> dict[str, str]:
        if not self._settings.billing_enabled:
            raise ServiceUnavailableError("Billing is disabled.", code="billing_disabled")

        if not self._provider.verify_webhook_signature(payload, signature_header):
            logger.warning("billing_webhook_invalid_signature")
            raise ValidationAppError("Invalid webhook signature.")

        try:
            event = json.loads(payload.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValidationAppError("Invalid webhook JSON.") from exc

        event_id = str(event.get("id", ""))
        event_type = str(event.get("type", "unknown"))
        if not event_id:
            raise ValidationAppError("Webhook missing event id.")

        if self._webhooks.get_by_provider_event_id(event_id):
            return {"status": "duplicate_ignored", "event_id": event_id}

        redacted = redact_stripe_payload(event if isinstance(event, dict) else {})
        webhook_row = WebhookEventModel(
            provider=self.provider_name.value,
            provider_event_id=event_id,
            event_type=event_type,
            status="processed",
            organization_id=_org_from_event(event),
            redacted_payload=redacted,
            created_at=datetime.now(UTC),
        )
        self._webhooks.add(webhook_row)

        billing_row = BillingEventModel(
            organization_id=webhook_row.organization_id,
            event_type=event_type,
            provider=self.provider_name.value,
            provider_event_id=event_id,
            status=BillingEventStatus.PROCESSED.value,
            redacted_payload=redacted,
            created_at=datetime.now(UTC),
        )
        self._billing_events.add(billing_row)

        self._audit.record(
            AuditRecordCreate(
                request_id=request_id or "billing-webhook",
                trace_id=request_id or "billing-webhook",
                organization_id=webhook_row.organization_id,
                event_type=AuditEventType.BILLING_WEBHOOK_RECEIVED,
                resource_type="webhook_event",
                resource_id=event_id,
                metadata={"event_type": event_type},
                result=AuditResult.SUCCESS,
                severity=AuditSeverity.INFO,
            )
        )

        if event_type in _SUPPORTED_WEBHOOK_EVENTS:
            self._process_webhook_event(event_type, event)
        else:
            billing_row.status = BillingEventStatus.IGNORED.value

        self._session.flush()
        return {"status": "ok", "event_id": event_id}

    def apply_plan(
        self,
        organization_id: uuid.UUID,
        plan_id: str,
        *,
        actor_user_id: uuid.UUID | None = None,
        request_id: str | None = None,
    ) -> SubscriptionView:
        plan = get_plan(plan_id)
        if plan is None:
            raise NotFoundError(f"Unknown plan: {plan_id}")

        sub = self._ensure_subscription(organization_id, plan_id)
        sub.plan_id = plan_id
        sub.status = SubscriptionStatus.ACTIVE.value
        now = datetime.now(UTC)
        sub.current_period_start = now
        sub.current_period_end = now + timedelta(days=30)
        self._session.flush()

        self._quota.get_or_create_quota(organization_id)
        patch = plan_to_quota_update(plan)
        self._quota.update_quota(
            organization_id,
            patch,
            actor_user_id=actor_user_id,
            request_id=request_id,
        )
        from app.repositories.quota import QuotaRepository

        quota_db = QuotaRepository(self._session).get_by_organization(organization_id)
        if quota_db:
            quota_db.plan_id = plan_id
            self._session.flush()

        self._audit.record(
            AuditRecordCreate(
                request_id=request_id or "billing-plan",
                trace_id=request_id or "billing-plan",
                organization_id=organization_id,
                user_id=actor_user_id,
                event_type=AuditEventType.BILLING_PLAN_CHANGED,
                resource_type="subscription",
                resource_id=str(sub.id),
                metadata={"plan_id": plan_id},
                result=AuditResult.SUCCESS,
                severity=AuditSeverity.INFO,
            )
        )
        return _subscription_view(sub)

    def _ensure_subscription(
        self,
        organization_id: uuid.UUID,
        plan_id: str,
    ) -> SubscriptionModel:
        sub = self._subscriptions.get_by_organization(organization_id)
        if sub is not None:
            return sub
        now = datetime.now(UTC)
        sub = SubscriptionModel(
            organization_id=organization_id,
            plan_id=plan_id,
            status=SubscriptionStatus.ACTIVE.value,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
        )
        self._subscriptions.add(sub)
        return sub

    def _process_webhook_event(self, event_type: str, event: dict[str, object]) -> None:
        data = event.get("data")
        obj: dict[str, object] = {}
        if isinstance(data, dict):
            raw_obj = data.get("object")
            if isinstance(raw_obj, dict):
                obj = raw_obj

        org_id = _org_from_event(event)
        if org_id is None:
            customer_id = obj.get("customer")
            if isinstance(customer_id, str):
                org_id = _org_for_stripe_customer(self._session, customer_id)

        plan_id = PLAN_FREE
        metadata = obj.get("metadata")
        if isinstance(metadata, dict):
            raw_plan = metadata.get("plan_id")
            if isinstance(raw_plan, str):
                plan_id = raw_plan

        if event_type in {
            "checkout.session.completed",
            "customer.subscription.created",
            "customer.subscription.updated",
        }:
            if org_id:
                self.apply_plan(org_id, plan_id, request_id=f"webhook-{event_type}")
        elif event_type == "customer.subscription.deleted" and org_id:
            sub = self._subscriptions.get_by_organization(org_id)
            if sub:
                sub.status = SubscriptionStatus.CANCELED.value
                sub.cancel_at_period_end = True


def _customer_view(row: BillingCustomerModel) -> BillingCustomerView:
    return BillingCustomerView(
        id=row.id,
        organization_id=row.organization_id,
        provider=BillingProviderName(row.provider),
        provider_customer_id=row.provider_customer_id,
        billing_email=row.billing_email,
        status=BillingCustomerStatus(row.status),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _subscription_view(row: SubscriptionModel) -> SubscriptionView:
    return SubscriptionView(
        id=row.id,
        organization_id=row.organization_id,
        provider_subscription_id=row.provider_subscription_id,
        plan_id=row.plan_id,
        status=SubscriptionStatus(row.status),
        current_period_start=row.current_period_start,
        current_period_end=row.current_period_end,
        cancel_at_period_end=row.cancel_at_period_end,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _org_from_event(event: dict[str, object]) -> uuid.UUID | None:
    data = event.get("data")
    if not isinstance(data, dict):
        return None
    obj = data.get("object")
    if not isinstance(obj, dict):
        return None
    for key in ("organization_id", "client_reference_id"):
        raw = obj.get(key)
        if isinstance(raw, str):
            try:
                return uuid.UUID(raw)
            except ValueError:
                continue
    metadata = obj.get("metadata")
    if isinstance(metadata, dict):
        raw_org = metadata.get("organization_id")
        if isinstance(raw_org, str):
            try:
                return uuid.UUID(raw_org)
            except ValueError:
                pass
    return None


def _org_for_stripe_customer(session: Session, provider_customer_id: str) -> uuid.UUID | None:
    from sqlalchemy import select

    from app.db.models import BillingCustomer as BillingCustomerModel

    stmt = select(BillingCustomerModel.organization_id).where(
        BillingCustomerModel.provider_customer_id == provider_customer_id
    )
    org_id = session.scalar(stmt)
    return org_id

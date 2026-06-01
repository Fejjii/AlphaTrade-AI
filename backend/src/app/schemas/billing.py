"""Billing API schemas (Slice 26)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class BillingProviderName(StrEnum):
    MOCK = "mock"
    STRIPE = "stripe"


class BillingCustomerStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"


class SubscriptionStatus(StrEnum):
    ACTIVE = "active"
    TRIALING = "trialing"
    CANCELED = "canceled"
    PAST_DUE = "past_due"
    INCOMPLETE = "incomplete"


class BillingEventStatus(StrEnum):
    PENDING = "pending"
    PROCESSED = "processed"
    IGNORED = "ignored"
    FAILED = "failed"


class SubscriptionPlanView(BaseModel):
    """Static plan definition mapped to organization quotas."""

    model_config = ConfigDict(frozen=True)

    plan_id: str
    name: str
    description: str
    monthly_token_limit: int
    monthly_cost_limit: Decimal
    daily_request_limit: int
    limit_agent_chat: int
    limit_rag_ingest: int
    limit_market_analyze: int
    limit_agent_narrative: int
    limit_paper_execution: int
    seat_limit: int = Field(description="Placeholder for future per-seat billing.")
    price_display: str = Field(description="Placeholder price label; not a live charge.")
    price_currency: str = "usd"
    stripe_price_id: str | None = None


class BillingCustomerCreate(BaseModel):
    billing_email: str | None = None


class BillingCustomerView(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    provider: BillingProviderName
    provider_customer_id: str
    billing_email: str | None
    status: BillingCustomerStatus
    created_at: datetime
    updated_at: datetime


class SubscriptionView(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    provider_subscription_id: str | None
    plan_id: str
    status: SubscriptionStatus
    current_period_start: datetime | None
    current_period_end: datetime | None
    cancel_at_period_end: bool
    created_at: datetime
    updated_at: datetime


class BillingStatusResponse(BaseModel):
    billing_enabled: bool
    provider: BillingProviderName
    is_mock: bool
    live_checkout_available: bool
    current_plan_id: str
    customer: BillingCustomerView | None = None
    subscription: SubscriptionView | None = None


class CheckoutRequest(BaseModel):
    plan_id: str


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str
    is_mock: bool


class PortalResponse(BaseModel):
    portal_url: str
    is_mock: bool


class UsageExportRequest(BaseModel):
    period_start: datetime | None = None
    period_end: datetime | None = None


class UsageExportLineItem(BaseModel):
    feature: str
    event_count: int
    total_tokens: int
    provider_reported_cost: Decimal
    estimated_cost: Decimal
    cost_is_billing_grade: bool


class UsageExportResponse(BaseModel):
    batch_id: uuid.UUID
    organization_id: uuid.UUID
    period_start: datetime
    period_end: datetime
    total_events: int
    total_tokens: int
    provider_reported_cost: Decimal
    estimated_cost: Decimal
    billing_grade_cost: Decimal
    cost_is_billing_grade: bool
    fallback_event_count: int
    line_items: list[UsageExportLineItem]
    provider: BillingProviderName
    exported_at: datetime

"""Billing provider contract."""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable

from app.providers.base import ProviderKind, ProviderStatus
from app.schemas.billing import BillingProviderName


@runtime_checkable
class BillingProvider(Protocol):
    """Checkout, portal, usage export, and webhook verification."""

    name: str
    kind: ProviderKind
    provider_name: BillingProviderName

    def status(self) -> ProviderStatus: ...

    def create_customer(
        self,
        *,
        organization_id: uuid.UUID,
        billing_email: str,
    ) -> str: ...

    def create_checkout_session(
        self,
        *,
        organization_id: uuid.UUID,
        provider_customer_id: str,
        plan_id: str,
    ) -> tuple[str, str]: ...

    def create_portal_session(
        self,
        *,
        provider_customer_id: str,
    ) -> str: ...

    def record_usage_export(
        self,
        *,
        organization_id: uuid.UUID,
        batch_id: uuid.UUID,
        payload_summary: dict[str, object],
    ) -> None: ...

    def verify_webhook_signature(
        self,
        payload: bytes,
        signature_header: str | None,
    ) -> bool: ...

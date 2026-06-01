"""Mock billing provider for local development and tests."""

from __future__ import annotations

import uuid

import structlog

from app.providers.base import ProviderHealth, ProviderKind, ProviderStatus
from app.schemas.billing import BillingProviderName

logger = structlog.get_logger(__name__)

_MOCK_CHECKOUT_BASE = "https://mock.billing.local/checkout"
_MOCK_PORTAL_BASE = "https://mock.billing.local/portal"


class MockBillingProvider:
    """Safe mock URLs; no external payment calls."""

    name = "mock-billing"
    kind = ProviderKind.BILLING
    provider_name = BillingProviderName.MOCK

    def __init__(self, *, billing_enabled: bool = False) -> None:
        self._billing_enabled = billing_enabled
        self._customers: dict[str, str] = {}
        self._exports: list[dict[str, object]] = []

    def status(self) -> ProviderStatus:
        detail = (
            "Mock billing provider; checkout and portal return safe local URLs. No live charges."
        )
        if not self._billing_enabled:
            detail += " Billing feature flag disabled (BILLING_ENABLED=false)."
        return ProviderStatus(
            name=self.name,
            kind=self.kind,
            health=ProviderHealth.HEALTHY,
            is_mock=True,
            detail=detail,
        )

    def create_customer(
        self,
        *,
        organization_id: uuid.UUID,
        billing_email: str,
    ) -> str:
        customer_id = f"mock_cus_{organization_id.hex[:12]}"
        self._customers[str(organization_id)] = customer_id
        domain = billing_email.split("@")[-1] if "@" in billing_email else "unknown"
        logger.info("billing_mock_customer_created", recipient_domain=domain)
        return customer_id

    def create_checkout_session(
        self,
        *,
        organization_id: uuid.UUID,
        provider_customer_id: str,
        plan_id: str,
    ) -> tuple[str, str]:
        session_id = f"mock_cs_{uuid.uuid4().hex[:16]}"
        url = f"{_MOCK_CHECKOUT_BASE}/{session_id}?plan={plan_id}&org={organization_id}"
        logger.info("billing_mock_checkout_created", plan_id=plan_id)
        return url, session_id

    def create_portal_session(
        self,
        *,
        provider_customer_id: str,
    ) -> str:
        logger.info("billing_mock_portal_created")
        return f"{_MOCK_PORTAL_BASE}/{provider_customer_id}"

    def record_usage_export(
        self,
        *,
        organization_id: uuid.UUID,
        batch_id: uuid.UUID,
        payload_summary: dict[str, object],
    ) -> None:
        self._exports.append(
            {
                "organization_id": str(organization_id),
                "batch_id": str(batch_id),
                "summary": payload_summary,
            }
        )
        logger.info(
            "billing_mock_usage_export_recorded",
            organization_id=str(organization_id),
            batch_id=str(batch_id),
        )

    def verify_webhook_signature(
        self,
        payload: bytes,
        signature_header: str | None,
    ) -> bool:
        return signature_header == "mock-signature-valid"

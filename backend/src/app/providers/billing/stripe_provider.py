"""Stripe billing provider placeholder (no live API calls in scaffold)."""

from __future__ import annotations

import hashlib
import hmac
import time
import uuid

import structlog

from app.core.config import Settings
from app.core.errors import ServiceUnavailableError
from app.providers.base import ProviderHealth, ProviderKind, ProviderStatus
from app.schemas.billing import BillingProviderName

logger = structlog.get_logger(__name__)

_STRIPE_CHECKOUT_PLACEHOLDER = "https://checkout.stripe.com/c/pay/placeholder"
_STRIPE_PORTAL_PLACEHOLDER = "https://billing.stripe.com/p/session/placeholder"


class StripeBillingProvider:
    """Stripe integration scaffold — live API wiring deferred to production slice."""

    name = "stripe-billing"
    kind = ProviderKind.BILLING
    provider_name = BillingProviderName.STRIPE

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._secret = settings.stripe_secret_key.strip()
        self._webhook_secret = settings.stripe_webhook_secret.strip()

    @property
    def _live_mode(self) -> bool:
        return bool(
            self._settings.billing_enabled
            and self._secret
            and self._secret.startswith(("sk_test_", "sk_live_"))
        )

    def status(self) -> ProviderStatus:
        if not self._settings.billing_enabled:
            return ProviderStatus(
                name=self.name,
                kind=self.kind,
                health=ProviderHealth.DEGRADED,
                is_mock=False,
                detail="Stripe configured but BILLING_ENABLED=false.",
            )
        if not self._secret:
            return ProviderStatus(
                name=self.name,
                kind=self.kind,
                health=ProviderHealth.UNAVAILABLE,
                is_mock=False,
                detail="STRIPE_SECRET_KEY not configured.",
            )
        return ProviderStatus(
            name=self.name,
            kind=self.kind,
            health=ProviderHealth.HEALTHY,
            is_mock=False,
            detail="Stripe keys present; checkout uses placeholder URLs until API wiring.",
        )

    def create_customer(
        self,
        *,
        organization_id: uuid.UUID,
        billing_email: str,
    ) -> str:
        self._require_live()
        return f"stripe_cus_{organization_id.hex[:24]}"

    def create_checkout_session(
        self,
        *,
        organization_id: uuid.UUID,
        provider_customer_id: str,
        plan_id: str,
    ) -> tuple[str, str]:
        self._require_live()
        session_id = f"cs_placeholder_{uuid.uuid4().hex[:16]}"
        logger.info(
            "billing_stripe_checkout_placeholder",
            plan_id=plan_id,
            organization_id=str(organization_id),
        )
        return f"{_STRIPE_CHECKOUT_PLACEHOLDER}_{plan_id}", session_id

    def create_portal_session(self, *, provider_customer_id: str) -> str:
        self._require_live()
        logger.info("billing_stripe_portal_placeholder")
        return f"{_STRIPE_PORTAL_PLACEHOLDER}_{provider_customer_id[-12:]}"

    def record_usage_export(
        self,
        *,
        organization_id: uuid.UUID,
        batch_id: uuid.UUID,
        payload_summary: dict[str, object],
    ) -> None:
        self._require_live()
        logger.info(
            "billing_stripe_usage_export_placeholder",
            organization_id=str(organization_id),
            batch_id=str(batch_id),
            event_count=payload_summary.get("total_events"),
        )

    def verify_webhook_signature(
        self,
        payload: bytes,
        signature_header: str | None,
    ) -> bool:
        if not self._webhook_secret:
            return False
        if not signature_header:
            return False
        try:
            return _verify_stripe_signature(
                payload,
                signature_header,
                self._webhook_secret,
            )
        except Exception:
            logger.warning("billing_stripe_webhook_verify_failed")
            return False

    def _require_live(self) -> None:
        if not self._live_mode:
            raise ServiceUnavailableError(
                "Live Stripe billing requires BILLING_ENABLED=true and STRIPE_SECRET_KEY.",
                code="billing_not_configured",
            )


def _verify_stripe_signature(payload: bytes, sig_header: str, secret: str) -> bool:
    """Verify Stripe-Signature header (v1 scheme)."""
    parts: dict[str, str] = {}
    for item in sig_header.split(","):
        if "=" in item:
            key, value = item.split("=", 1)
            parts[key.strip()] = value.strip()
    timestamp = parts.get("t")
    signature = parts.get("v1")
    if not timestamp or not signature:
        return False
    try:
        if abs(time.time() - int(timestamp)) > 300:
            return False
    except ValueError:
        return False
    signed = f"{timestamp}.{payload.decode('utf-8')}".encode()
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def redact_stripe_payload(payload: dict[str, object]) -> dict[str, object]:
    """Redact secrets and PII from webhook payloads before persistence."""
    from app.guardrails.redaction import redact_value

    return redact_value(payload)  # type: ignore[return-value]

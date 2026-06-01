"""SendGrid-style HTTP email provider placeholder."""

from __future__ import annotations

import structlog

from app.core.config import Settings
from app.providers.base import ProviderHealth, ProviderKind, ProviderStatus
from app.providers.email.base import EmailMessage

logger = structlog.get_logger(__name__)


class SendGridEmailProvider:
    name = "sendgrid-email"
    kind = ProviderKind.EMAIL

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def send(self, message: EmailMessage) -> None:
        if not self._settings.sendgrid_api_key:
            raise RuntimeError("SENDGRID_API_KEY is not configured.")
        logger.info("email_sent_sendgrid", template=message.template)
        raise NotImplementedError(
            "SendGrid delivery is not fully wired; set EMAIL_PROVIDER=mock for local dev."
        )

    def status(self) -> ProviderStatus:
        configured = bool(self._settings.sendgrid_api_key.strip())
        return ProviderStatus(
            name=self.name,
            kind=self.kind,
            health=ProviderHealth.DEGRADED if configured else ProviderHealth.UNAVAILABLE,
            detail="SendGrid placeholder — set SENDGRID_API_KEY for staging/production.",
            is_mock=False,
        )

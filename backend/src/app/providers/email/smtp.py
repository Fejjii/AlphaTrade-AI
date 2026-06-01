"""SMTP email provider placeholder (configure host/credentials to enable)."""

from __future__ import annotations

import structlog

from app.core.config import Settings
from app.providers.base import ProviderHealth, ProviderKind, ProviderStatus
from app.providers.email.base import EmailMessage

logger = structlog.get_logger(__name__)


class SmtpEmailProvider:
    name = "smtp-email"
    kind = ProviderKind.EMAIL

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def send(self, message: EmailMessage) -> None:
        if not self._settings.smtp_host:
            raise RuntimeError("SMTP host is not configured.")
        # Placeholder: production wiring uses smtplib with TLS; bodies are never logged.
        logger.info("email_sent_smtp", template=message.template)
        raise NotImplementedError(
            "SMTP delivery is not fully wired; set EMAIL_PROVIDER=mock for local dev."
        )

    def status(self) -> ProviderStatus:
        configured = bool(self._settings.smtp_host.strip())
        return ProviderStatus(
            name=self.name,
            kind=self.kind,
            health=ProviderHealth.DEGRADED if configured else ProviderHealth.UNAVAILABLE,
            detail="SMTP placeholder — configure SMTP_HOST and credentials for production.",
            is_mock=False,
        )

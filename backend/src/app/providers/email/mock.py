"""In-memory mock email provider for tests and local development."""

from __future__ import annotations

import structlog

from app.providers.base import ProviderHealth, ProviderKind, ProviderStatus
from app.providers.email.base import EmailMessage

logger = structlog.get_logger(__name__)


class MockEmailProvider:
    """Captures sent messages in memory without logging sensitive bodies."""

    name = "mock-email"
    kind = ProviderKind.EMAIL

    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> None:
        self.sent.append(message)
        domain = message.to_address.split("@")[-1] if "@" in message.to_address else "unknown"
        logger.info("email_sent_mock", template=message.template, recipient_domain=domain)

    def status(self) -> ProviderStatus:
        return ProviderStatus(
            name=self.name,
            kind=self.kind,
            health=ProviderHealth.HEALTHY,
            is_mock=True,
            detail="Mock email provider; messages stored in memory only.",
        )

    def clear(self) -> None:
        self.sent.clear()

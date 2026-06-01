"""Email provider contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.providers.base import ProviderKind, ProviderStatus


@dataclass(frozen=True)
class EmailMessage:
    """Outbound email payload (links may contain secrets — never log body)."""

    to_address: str
    subject: str
    text_body: str
    html_body: str | None = None
    template: str = "generic"


@runtime_checkable
class EmailProvider(Protocol):
    name: str
    kind: ProviderKind

    def send(self, message: EmailMessage) -> None:
        """Deliver message; raise on hard failure."""

    def status(self) -> ProviderStatus: ...

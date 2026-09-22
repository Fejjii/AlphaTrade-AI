"""Paper Telegram agent errors. Never used as trading authority."""

from __future__ import annotations


class PaperTelegramError(ValueError):
    def __init__(self, message: str, *, details: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


class PaperTelegramDisabledError(PaperTelegramError):
    def __init__(self) -> None:
        super().__init__("Telegram paper interaction is disabled.")


class PaperTelegramTenantError(PaperTelegramError):
    pass


class ConflictingPaperNotificationError(PaperTelegramError):
    pass


class PaperConfirmationRequiredError(PaperTelegramError):
    pass


class PaperActionRefusedError(PaperTelegramError):
    """Refused because Telegram must not hold that authority."""

"""Fail-closed errors for paper Telegram activation. Never include secrets."""

from __future__ import annotations


class TelegramActivationError(Exception):
    """Activation refused or an inbound update could not be applied."""

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason

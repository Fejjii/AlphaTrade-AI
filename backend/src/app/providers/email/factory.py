"""Resolve email provider from settings."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import Settings, get_settings
from app.providers.email.base import EmailProvider
from app.providers.email.mock import MockEmailProvider
from app.providers.email.resend import ResendEmailProvider
from app.providers.email.sendgrid import SendGridEmailProvider
from app.providers.email.smtp import SmtpEmailProvider

_process_mock: MockEmailProvider | None = None


def resolve_email_provider(settings: Settings) -> EmailProvider:
    global _process_mock
    mode = settings.email_provider
    if mode == "mock":
        if _process_mock is None:
            _process_mock = MockEmailProvider()
        return _process_mock
    if mode == "smtp":
        return SmtpEmailProvider(settings)
    if mode == "resend":
        return ResendEmailProvider(settings)
    if mode == "sendgrid":
        return SendGridEmailProvider(settings)
    return MockEmailProvider()


@lru_cache
def get_email_provider() -> EmailProvider:
    return resolve_email_provider(get_settings())


def reset_email_provider_for_tests() -> None:
    global _process_mock
    _process_mock = None
    get_email_provider.cache_clear()

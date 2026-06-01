"""Email provider abstraction for account lifecycle messages."""

from app.providers.email.base import EmailMessage, EmailProvider
from app.providers.email.factory import get_email_provider, resolve_email_provider

__all__ = [
    "EmailMessage",
    "EmailProvider",
    "get_email_provider",
    "resolve_email_provider",
]

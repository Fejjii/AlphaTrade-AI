"""Resolve billing provider from settings."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import Settings, get_settings
from app.providers.billing.base import BillingProvider
from app.providers.billing.mock import MockBillingProvider
from app.providers.billing.stripe_provider import StripeBillingProvider

_process_mock: MockBillingProvider | None = None


def resolve_billing_provider(settings: Settings) -> BillingProvider:
    global _process_mock
    stripe_key = settings.stripe_secret_key.strip()
    if settings.billing_enabled and stripe_key:
        return StripeBillingProvider(settings)
    if _process_mock is None:
        _process_mock = MockBillingProvider(billing_enabled=settings.billing_enabled)
    else:
        _process_mock._billing_enabled = settings.billing_enabled
    return _process_mock


@lru_cache
def get_billing_provider() -> BillingProvider:
    return resolve_billing_provider(get_settings())


def reset_billing_provider_for_tests() -> None:
    global _process_mock
    _process_mock = None
    get_billing_provider.cache_clear()

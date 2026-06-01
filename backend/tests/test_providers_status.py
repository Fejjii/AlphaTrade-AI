"""Tests for the provider status endpoint and registry behavior."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.providers.base import (
    BaseMockProvider,
    Provider,
    ProviderHealth,
    ProviderKind,
    ProviderStatus,
)
from app.providers.registry import ProviderRegistry


def test_provider_status_endpoint_lists_providers(client: TestClient) -> None:
    response = client.get("/providers/status")
    assert response.status_code == 200

    body = response.json()
    assert body["providers"], "expected at least one provider"
    kinds = {p["kind"] for p in body["providers"]}
    assert "exchange" in kinds
    assert "llm" in kinds
    llm = next(p for p in body["providers"] if p["kind"] == "llm")
    assert llm["name"] == "mock-llm"
    exchange = next(p for p in body["providers"] if p["kind"] == "exchange")
    assert exchange["is_mock"] is True
    assert "real trading disabled" in (exchange.get("detail") or "").lower()


def test_registry_rejects_duplicate_registration() -> None:
    registry = ProviderRegistry()
    registry.register(BaseMockProvider("dup", ProviderKind.LLM))
    with pytest.raises(ValueError, match="already registered"):
        registry.register(BaseMockProvider("dup", ProviderKind.LLM))


def test_registry_degrades_gracefully_on_status_exception() -> None:
    """A misbehaving provider must not crash status aggregation (fallback)."""

    class BrokenProvider:
        name = "broken"
        kind = ProviderKind.MARKET_DATA

        def status(self) -> ProviderStatus:
            raise RuntimeError("probe failed")

    registry = ProviderRegistry()
    broken: Provider = BrokenProvider()
    registry.register(broken)

    statuses = registry.statuses()
    assert len(statuses) == 1
    assert statuses[0].health is ProviderHealth.UNAVAILABLE

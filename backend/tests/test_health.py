"""Tests for the health and readiness endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "ok"
    assert body["execution_mode"] == "paper"
    assert body["real_trading_enabled"] is False
    assert body["version"]


def test_health_sets_request_id_header(client: TestClient) -> None:
    response = client.get("/health")
    assert response.headers.get("X-Request-ID")


def test_health_propagates_inbound_request_id(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "test-correlation-id"})
    assert response.headers["X-Request-ID"] == "test-correlation-id"


def test_readiness_ready_with_mock_providers(client: TestClient) -> None:
    response = client.get("/health/ready")
    assert response.status_code == 200

    body = response.json()
    assert body["ready"] is True
    assert body["providers_unavailable"] == 0
    assert body["providers_total"] > 0

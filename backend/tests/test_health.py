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


def test_health_includes_git_sha_when_configured(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("GIT_SHA", "d52588eabc1234567890abcdef1234567890abcd")
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["git_sha"] == "d52588eabc1234567890abcdef1234567890abcd"


def test_health_git_sha_null_when_unconfigured(client: TestClient, monkeypatch) -> None:
    for key in ("GIT_SHA", "RENDER_GIT_COMMIT", "SOURCE_VERSION"):
        monkeypatch.delenv(key, raising=False)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["git_sha"] is None


def test_health_git_sha_from_render_env(client: TestClient, monkeypatch) -> None:
    monkeypatch.delenv("GIT_SHA", raising=False)
    monkeypatch.setenv("RENDER_GIT_COMMIT", "089739b")
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["git_sha"] == "089739b"


def test_readiness_ready_with_mock_providers(client: TestClient) -> None:
    response = client.get("/health/ready")
    assert response.status_code == 200

    body = response.json()
    assert body["ready"] is True
    assert body["providers_unavailable"] == 0
    assert body["providers_total"] > 0

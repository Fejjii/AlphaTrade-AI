"""Exercise the readiness smoke against actual isolated authentication/read routes."""

import importlib.util
from pathlib import Path

import pytest

from tests.test_auth import auth_client as _auth_client
from tests.test_auth import auth_settings as _auth_settings

auth_client = _auth_client
auth_settings = _auth_settings

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/mvp-readiness-smoke.py"
spec = importlib.util.spec_from_file_location("mvp_smoke", SCRIPT)
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


def configure(client):
    body = {
        "email": "readiness@example.com",
        "password": "secure-password-1",
        "organization_name": "Isolated readiness fixture",
    }
    response = client.post("/auth/register", json=body)
    assert response.status_code == 201
    client.headers["Authorization"] = "Bearer " + response.json()["tokens"]["access_token"]
    config = client.get("/watcher/watchlist").json()
    result = client.put(
        "/watcher/watchlist",
        json={"revision": config["revision"], "slots": [{"symbol": "BTCUSDT", "enabled": True}]},
    )
    assert result.status_code == 200
    del client.headers["Authorization"]
    return body


def test_login_universe_status_absent_setup_grounded_agent_and_read_surfaces(auth_client, capsys):
    body = configure(auth_client)
    smoke.run(auth_client, email=body["email"], password=body["password"], symbols={"BTCUSDT"})
    assert "linkage NOT VALIDATED" in capsys.readouterr().out


def test_wrong_expected_universe_fails(auth_client):
    body = configure(auth_client)
    with pytest.raises(RuntimeError, match="Configured universe differs"):
        smoke.run(auth_client, email=body["email"], password=body["password"], symbols={"ETHUSDT"})


def test_missing_safety_flag_fails_before_login():
    import httpx

    calls = []

    def respond(request):
        calls.append(request.url.path)
        return httpx.Response(
            200,
            json={
                "environment": "staging",
                "execution_mode": "paper",
                "exchange_mode": "paper_internal",
            },
        )

    with (
        httpx.Client(
            base_url="https://smoke.invalid", transport=httpx.MockTransport(respond)
        ) as client,
        pytest.raises(RuntimeError, match="Unsafe or absent health flag"),
    ):
        smoke.run(client, email="unused", password="unused", symbols={"BTCUSDT"})
    assert calls == ["/health"]


@pytest.mark.parametrize("mismatch", [False, True])
def test_existing_linked_setup_checks_nested_decision_and_journal_contracts(mismatch):
    import httpx

    setup_id = "00000000-0000-0000-0000-000000000001"
    candidate_id = "00000000-0000-0000-0000-000000000002"
    decision_id = "00000000-0000-0000-0000-000000000003"
    journal_id = "00000000-0000-0000-0000-000000000004"
    from app.schemas.health import HealthResponse

    health = HealthResponse(
        app="smoke",
        version="test",
        environment="local",
        execution_mode="paper",
        real_trading_enabled=False,
        exchange_mode="paper_internal",
        must_verify_email=False,
        perpetual_evidence_source="replay",
        perpetual_evidence_activation="inactive",
        timestamp="2026-10-01T00:00:00Z",
    ).model_dump(mode="json")
    responses = {
        "/health": health,
        "/auth/login": {"tokens": {"access_token": "test-only"}},
        "/watcher/watchlist": {
            "paper_only": True,
            "revision": 1,
            "slots": [{"symbol": "BTCUSDT", "enabled": True}],
        },
        "/watcher/watchlist/status": {
            "configuration_revision": 1,
            "real_trading_enabled": False,
            "symbols": [{"symbol": "BTCUSDT", "enabled": True}],
        },
        "/watcher/paper-runtime/status": {"enabled": False, "running": False},
        "/strategy-brain/overview": {"watched_symbols": ["BTCUSDT"], "setups": []},
        "/agent/turns": {
            "capability": "strategy_brain",
            "operation": "read",
            "execution_attempted": False,
            "real_trading_enabled": False,
            "authority_mutated": False,
            "proposals": [],
            "connections": [{"record_id": setup_id}],
        },
        f"/strategy-brain/setups/{setup_id}": {
            "setup_id": setup_id,
            "current_market_claim": False,
            "candidate_id": candidate_id,
            "decision_id": decision_id,
            "journal": {"id": journal_id},
        },
        f"/canonical/candidates/{candidate_id}": {"candidate": {"candidate_id": candidate_id}},
        f"/canonical/candidates/{candidate_id}/eligibility": {
            "evaluation": {
                "eligibility": {"eligibility_id": journal_id if mismatch else decision_id}
            }
        },
        f"/journal/trades/{journal_id}": {"trade": {"id": journal_id}},
    }

    def respond(request):
        return httpx.Response(200, json=responses[request.url.path])

    with httpx.Client(
        base_url="https://smoke.invalid", transport=httpx.MockTransport(respond)
    ) as client:
        if mismatch:
            with pytest.raises(RuntimeError, match="Decision mismatch"):
                smoke.run(
                    client,
                    email="fixture",
                    password="fixture",
                    symbols={"BTCUSDT"},
                    setup_id=setup_id,
                )
        else:
            smoke.run(
                client, email="fixture", password="fixture", symbols={"BTCUSDT"}, setup_id=setup_id
            )

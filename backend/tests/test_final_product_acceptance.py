"""Offline staging-harness failure paths; no HTTP or trading authority."""

import copy
import hashlib
import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from tests.support.postgres_persistence import persistence_session_factory, requires_postgres


def load(name):
    spec = importlib.util.spec_from_file_location(
        name.replace("-", "_"), Path(__file__).resolve().parents[2] / "scripts" / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


acceptance = load("final-product-acceptance")
telegram = load("telegram-staging-readiness")
SHA = "a" * 40
JS = b"agent-voice-status Start recording Send transcript Read Agent reply Stop speech"
ASSET = {
    "path": "/_next/static/chunks/app/(app)/agent/page-fixture.js",
    "sha256": hashlib.sha256(JS).hexdigest(),
}


class FixtureReader:
    api = "http://localhost:8000"
    frontend = "http://localhost:3000"

    def __init__(self):
        now = datetime.now(UTC).isoformat()
        paper = {
            "execution_mode": "paper",
            "exchange_mode": "paper_internal",
            "real_trading_enabled": False,
        }
        worker = {
            "available": True,
            "health_state": "RUNNING",
            "worker_id": "fixture",
            "heartbeat_at": now,
            "activation_state": "disarmed",
            "last_error_code": "",
            "telegram_runtime_state": "disarmed",
        }
        self.payloads = {
            "/health": {
                **paper,
                "status": "ok",
                "environment": "staging",
                "git_sha": SHA,
                "timestamp": now,
                "telegram_network_permitted": False,
                "telegram_paper_activation_armed": False,
                "telegram_interaction_enabled": False,
                "telegram_alerts_enabled": False,
                "automatic_telegram_delivery_enabled": False,
                "watcher_orchestration_enabled": False,
                "worker_runtime": {
                    "available": True,
                    "watcher": dict(worker),
                    "telegram": dict(worker),
                },
            },
            "/watcher/paper-runtime/status": {
                "paper_only": True,
                "enabled": False,
                "running": False,
                "real_trading_enabled": False,
            },
            "/agent/capabilities": {
                "schema_version": "InteractiveAgent/v1",
                "paper_safety": {
                    **paper,
                    "agent_can_enable_real_trading": False,
                    "execution_attempted": False,
                },
                "items": [
                    {"capability": "general_conversation", "status": "implemented"},
                    {"capability": "voice_io", "status": "contract_only"},
                ],
            },
            "/health/ready": {
                "ready": True,
                "providers_total": 3,
                "providers_unavailable": 0,
                "timestamp": now,
            },
            "/providers/status": {
                "generated_at": now,
                "providers": [
                    {"kind": kind, "health": "healthy", "is_mock": False, "using_fallback": False}
                    for kind in ("llm", "embeddings", "vector")
                ],
            },
            "/health/telegram-paper-activation": {
                **paper,
                **{key.lower(): False for key, value in telegram.SAFE.items() if value == "false"},
                "runtime_armable": False,
                "verdict": "NOT_ARMED",
                "confirmation_identity_required": True,
                "forbidden": dict.fromkeys(
                    (
                        "mint_candidate",
                        "override_setup_assessment",
                        "override_risk",
                        "activate_strategy",
                        "create_live_order",
                        "enable_live_trading",
                    ),
                    False,
                ),
                "blockers": ["activation_not_armed", "recipient_binding_missing"],
            },
        }
        for path in (
            "/journal/trades?limit=1",
            "/strategies?limit=1",
            "/knowledge/documents?limit=1",
            "/knowledge/chunks?limit=1",
            "/tradingview/signals?limit=1",
            "/paper-signal-orchestration/decisions?limit=1",
        ):
            self.payloads[path] = {"items": [], "total": 0}
        self.reads = []
        self.asset = JS

    def json(self, path, authenticated=False):
        self.reads.append(path)
        value = self.payloads[path]
        if isinstance(value, Exception):
            raise value
        return copy.deepcopy(value)

    def read(self, base, path, **kwargs):
        self.reads.append(path)
        return (
            self.asset
            if path == ASSET["path"]
            else f'<script src="{ASSET["path"]}"></script>'.encode()
        )


def result(reader):
    return acceptance.run(reader, SHA, ASSET)


def test_all_components_have_explicit_results_without_mutation():
    reader = FixtureReader()
    payload = result(reader)
    assert payload["status"] == "PASS"
    assert len(payload["checks"]) == 11
    assert payload["network_delivery_activated"] is False
    assert payload["execution_called"] is False
    assert all("execution/" not in path and "enrollment/start" not in path for path in reader.reads)
    detail = next(item for item in payload["checks"] if item["component"] == "telegram_readiness")[
        "detail"
    ]
    assert detail["delivery"] == "DISABLED"
    assert detail["physical_message"] == "NOT_TESTED"


@pytest.mark.parametrize(
    "component,change",
    [
        ("deployment_identity", lambda r: r.payloads["/health"].update(git_sha="b" * 40)),
        ("paper_safety", lambda r: r.payloads["/health"].update(real_trading_enabled=True)),
        ("paper_safety", lambda r: r.payloads["/health"].update(exchange_mode="trade_live")),
        (
            "watcher_health",
            lambda r: r.payloads["/health"]["worker_runtime"]["watcher"].update(
                health_state="STALE"
            ),
        ),
        (
            "watcher_health",
            lambda r: r.payloads["/health"]["worker_runtime"]["watcher"].update(
                heartbeat_at=(datetime.now(UTC) - timedelta(minutes=10)).isoformat()
            ),
        ),
        (
            "agent_capabilities",
            lambda r: r.payloads["/agent/capabilities"]["paper_safety"].update(
                agent_can_enable_real_trading=True
            ),
        ),
        ("journal_read", lambda r: r.payloads.update({"/journal/trades?limit=1": {}})),
        (
            "strategies_read",
            lambda r: r.payloads.update(
                {"/strategies?limit=1": acceptance.AcceptanceError("HTTP 503")}
            ),
        ),
        (
            "knowledge_readiness",
            lambda r: r.payloads["/providers/status"]["providers"][0].update(is_mock=True),
        ),
        ("knowledge_readiness", lambda r: r.payloads["/health/ready"].update(ready=False)),
        (
            "signal_readiness",
            lambda r: r.payloads.update(
                {"/tradingview/signals?limit=1": acceptance.AcceptanceError("HTTP 403")}
            ),
        ),
        (
            "telegram_readiness",
            lambda r: r.payloads["/health"].update(telegram_network_permitted=True),
        ),
        (
            "telegram_readiness",
            lambda r: r.payloads["/health/telegram-paper-activation"].update(
                confirmation_identity_required=False
            ),
        ),
        (
            "telegram_readiness",
            lambda r: r.payloads["/health/telegram-paper-activation"]["forbidden"].update(
                create_live_order=True
            ),
        ),
        ("voice_frontend_contract", lambda r: setattr(r, "asset", b"stale frontend")),
    ],
)
def test_unavailable_or_stale_components_fail_by_name(component, change):
    reader = FixtureReader()
    change(reader)
    payload = result(reader)
    assert payload["status"] == "FAIL"
    assert len(payload["checks"]) == 11
    assert (
        next(item for item in payload["checks"] if item["component"] == component)["status"]
        == "FAIL"
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://api.telegram.org",
        "https://telegram.org",
        "http://example.com",
        "https://user:secret@example.com",
        "https://example.com/?token=secret",
    ],
)
def test_reader_refuses_unsafe_destinations(url):
    with pytest.raises(acceptance.AcceptanceError):
        acceptance.Reader(url, "https://frontend.example.com", "fixture")


def test_redirects_are_never_followed():
    with pytest.raises(acceptance.AcceptanceError, match="redirect refused"):
        acceptance.NoRedirect().redirect_request(
            None, None, 302, "", {}, "https://api.telegram.org"
        )


def test_readiness_requires_safe_environment_and_verified_binding_without_secrets():
    env = {
        **telegram.SAFE,
        "ENVIRONMENT": "staging",
        "TELEGRAM_BOT_ID": "123",
        "TELEGRAM_BOT_TOKEN": "123:fixture-secret",
        "TELEGRAM_CHAT_ID": "42",
    }
    unbound = telegram.report(env)
    assert unbound["status"] == "BLOCKED"
    assert unbound["binding"]["state"] == "NOT_CHECKED"
    bound = telegram.report(env, {"state": "VERIFIED_PRIVATE", "reason": "binding_verified"})
    assert bound["status"] == "OPERATOR_REVIEW_REQUIRED"
    assert bound["network_activated"] is False
    assert bound["real_message"] == "NOT_TESTED"
    assert "fixture-secret" not in json.dumps(bound)
    env["TELEGRAM_BOT_ID"] = "999"
    assert "numeric_bot_identity_and_matching_secret_required" in telegram.report(env)["blockers"]
    env["TELEGRAM_NETWORK_PERMITTED"] = "true"
    assert "TELEGRAM_NETWORK_PERMITTED_must_be_false" in telegram.report(env)["blockers"]


def test_capture_frontend_contract_is_local_and_pins_content(tmp_path, monkeypatch):
    directory = tmp_path / "static/chunks/app/(app)/agent"
    directory.mkdir(parents=True)
    (directory / "page-fixture.js").write_bytes(JS)
    output = tmp_path / "contract.json"
    monkeypatch.setattr(
        "sys.argv",
        ["acceptance", "--capture-frontend-contract", str(output), "--build-dir", str(tmp_path)],
    )
    assert acceptance.main() == 0
    assert json.loads(output.read_text()) == ASSET


def test_cli_missing_input_is_failure_without_any_network(monkeypatch, capsys):
    monkeypatch.delenv("ACCEPTANCE_API_URL", raising=False)
    monkeypatch.setattr("sys.argv", ["acceptance"])
    assert acceptance.main() == 2
    assert "ACCEPTANCE_API_URL is required" in capsys.readouterr().err


@requires_postgres
@pytest.mark.parametrize("invalid", [None, "tenant", "group", "close", "revoked"])
def test_readiness_select_validates_actual_persisted_binding(invalid):
    from app.db.telegram_security import TelegramBindingRow

    factory = persistence_session_factory()
    org, user = uuid4(), uuid4()
    with factory() as session:
        session.add(
            TelegramBindingRow(
                binding_id=uuid4(),
                organization_id=org,
                user_id=user,
                telegram_user_id="7",
                chat_id="42",
                bot_id="123",
                chat_type="group" if invalid == "group" else "private",
                state="VERIFIED",
                verified_at=datetime.now(UTC),
                revoked_at=datetime.now(UTC) if invalid == "revoked" else None,
                allowed_actions=["CLOSE"] if invalid == "close" else ["EXPLAIN"],
            )
        )
        session.commit()
    environment = {
        "DATABASE_URL": factory.kw["bind"].url.render_as_string(hide_password=False),
        "ACCEPTANCE_ORGANIZATION_ID": str(uuid4() if invalid == "tenant" else org),
        "ACCEPTANCE_USER_ID": str(user),
        "TELEGRAM_BOT_ID": "123",
        "TELEGRAM_CHAT_ID": "42",
    }
    observed = telegram.inspect_binding(environment)
    assert observed["state"] == ("VERIFIED_PRIVATE" if invalid is None else "BLOCKED")
    with factory() as session:
        assert (
            session.get(
                TelegramBindingRow, session.query(TelegramBindingRow.binding_id).scalar()
            ).state
            == "VERIFIED"
        )


def test_preparation_cli_refuses_network_enabled_before_database_read(monkeypatch, capsys):
    monkeypatch.setenv("TELEGRAM_NETWORK_PERMITTED", "true")
    monkeypatch.setattr("sys.argv", ["readiness", "--check-binding"])
    monkeypatch.setattr(telegram, "inspect_binding", lambda _: pytest.fail("inspection forbidden"))
    assert telegram.main() == 2
    assert (
        json.loads(capsys.readouterr().out)["reason"] == "network_must_be_disabled_for_preparation"
    )


def test_disarmed_workers_may_be_absent_without_inventing_running_state():
    from app.schemas.health import WorkerComponentObservation

    reader = FixtureReader()
    absent = WorkerComponentObservation().model_dump(mode="json")
    reader.payloads["/health"]["worker_runtime"].update(watcher=absent, telegram=absent)
    assert result(reader)["status"] == "PASS"
    reader.payloads["/health"]["watcher_orchestration_enabled"] = True
    assert result(reader)["status"] == "FAIL"
    reader.payloads["/health"]["watcher_orchestration_enabled"] = False
    reader.payloads["/health"]["worker_runtime"]["available"] = False
    assert result(reader)["status"] == "FAIL"

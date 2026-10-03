#!/usr/bin/env python3
"""Read-only staging acceptance. GET only; never activates delivery or execution."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import unquote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class AcceptanceError(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise AcceptanceError(reason)


def origin(value):
    parsed = urlsplit(value)
    require(parsed.scheme in {"https", "http"} and bool(parsed.hostname), "valid URL required")
    require(not parsed.username and not parsed.password, "URL credentials forbidden")
    require(
        parsed.path in {"", "/"} and not parsed.query and not parsed.fragment,
        "URL must be an origin",
    )
    host = parsed.hostname.lower()
    require(
        host != "telegram.org" and not host.endswith(".telegram.org"), "Telegram origin forbidden"
    )
    require(
        parsed.scheme == "https" or host in {"127.0.0.1", "localhost", "::1"},
        "HTTPS required outside loopback",
    )
    return value.rstrip("/")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise AcceptanceError("redirect refused: use the exact deployment origin")


class Reader:
    def __init__(self, api_url, frontend_url, token, timeout=15):
        self.api = origin(api_url)
        self.frontend = origin(frontend_url)
        self.token = token
        self.timeout = timeout
        self.opener = build_opener(NoRedirect())

    def read(self, base, path, *, authenticated=False, frontend=False):
        require(path.startswith("/") and not path.startswith("//"), "relative GET path required")
        headers = {"Accept": "application/json", "Cache-Control": "no-cache"}
        if authenticated:
            headers["Authorization"] = f"Bearer {self.token}"
        if frontend:
            # Presence marker only; this does not authenticate an API operation.
            headers["Cookie"] = "alphatrade_session=1"
        try:
            with self.opener.open(
                Request(base + path, headers=headers, method="GET"), timeout=self.timeout
            ) as response:
                require(response.status == 200, f"{path}: HTTP {response.status}")
                raw = response.read(8_000_001)
                require(len(raw) <= 8_000_000, f"{path}: oversized response")
                return raw
        except HTTPError as error:
            raise AcceptanceError(f"{path}: HTTP {error.code}") from None
        except (OSError, TimeoutError):
            raise AcceptanceError(f"{path}: unavailable or timed out") from None

    def json(self, path, authenticated=False):
        try:
            payload = json.loads(self.read(self.api, path, authenticated=authenticated))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise AcceptanceError(f"{path}: invalid JSON") from None
        require(isinstance(payload, dict), f"{path}: expected object")
        return payload


def fresh(timestamp, max_age=90):
    require(isinstance(timestamp, str), "missing observation timestamp")
    try:
        observed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        age = (datetime.now(UTC) - observed).total_seconds()
    except (ValueError, TypeError):
        raise AcceptanceError("invalid observation timestamp") from None
    require(0 <= age <= max_age, "stale or future observation")


def paper(payload):
    require(payload.get("execution_mode") == "paper", "execution_mode must be paper")
    require(payload.get("real_trading_enabled") is False, "real trading must be false")
    require(
        payload.get("exchange_mode") == "paper_internal", "exchange_mode must be paper_internal"
    )


def paginated(payload):
    require(isinstance(payload.get("items"), list), "list component unavailable: items missing")
    require(
        type(payload.get("total")) is int and payload["total"] >= len(payload["items"]),
        "invalid list total",
    )


def worker(payload, name):
    runtime = payload.get("worker_runtime", {})
    require(runtime.get("available") is True, "worker status store unavailable")
    component = runtime.get(name, {})
    require(
        component.get("available") is True and component.get("health_state") == "RUNNING",
        f"{name}: stale or unavailable heartbeat",
    )
    fresh(
        component.get("heartbeat_at"), min(90, component.get("heartbeat_stale_after_seconds", 90))
    )
    require(bool(component.get("worker_id")), f"{name}: worker identity missing")
    require(not component.get("last_error_code"), f"{name}: worker reports an error")
    return component


def disarmed_worker(payload, name):
    """Disarmed entrypoints idle without rows; recorded stale rows still fail."""
    runtime = payload.get("worker_runtime", {})
    require(runtime.get("available") is True, "worker status store unavailable")
    component = runtime.get(name, {})
    if not component.get("worker_id"):
        require(
            component.get("health_state") == "UNAVAILABLE"
            and component.get("available") is False
            and component.get("heartbeat_at") is None
            and not component.get("last_error_code"),
            f"{name}: invalid absent-worker contract",
        )
        return "DISABLED; no worker row expected"
    component = worker(payload, name)
    require(component.get("activation_state") == "disarmed", f"{name}: should be disarmed")
    return "fresh disarmed worker"


def run(reader, expected_sha, asset):
    results = []

    def check(name, action):
        try:
            detail = action()
            results.append({"component": name, "status": "PASS", "detail": detail or "ready"})
        except (AcceptanceError, KeyError, TypeError, AttributeError, ValueError):
            error = sys.exc_info()[1]
            # Contract errors only: no payload, token, URL query or credentials.
            detail = (
                str(error) if isinstance(error, AcceptanceError) else "invalid component contract"
            )
            results.append({"component": name, "status": "FAIL", "detail": detail})

    health = {}

    def health_check():
        health.update(reader.json("/health"))
        require(health.get("status") == "ok", "health is not ok")
        fresh(health.get("timestamp"))

    check("health", health_check)

    def identity():
        require(bool(re.fullmatch(r"[0-9a-f]{40}", expected_sha)), "full expected Git SHA required")
        require(health.get("git_sha") == expected_sha, "deployment SHA mismatch or missing")
        require(health.get("environment") == "staging", "deployment must report staging")

    check("deployment_identity", identity)
    check("paper_safety", lambda: paper(health))

    def watcher_check():
        require(
            type(health.get("watcher_orchestration_enabled")) is bool,
            "Watcher configuration absent",
        )
        status = reader.json("/watcher/paper-runtime/status", True)
        require(
            status.get("paper_only") is True and status.get("real_trading_enabled") is False,
            "Watcher paper safety unavailable",
        )
        if health.get("watcher_orchestration_enabled"):
            component = worker(health, "watcher")
            require(
                status.get("enabled") is True and status.get("running") is True,
                "armed Watcher is not running",
            )
            require(component.get("fence_held") is True, "Watcher lease not held")
            fresh(component.get("last_scan_at"))
            return "fresh paper worker and scan"
        require(status.get("enabled") is False, "Watcher process/API posture mismatch")
        require(status.get("running") is False, "disabled Watcher reports running")
        return disarmed_worker(health, "watcher") + "; scanning not enabled"

    check("watcher_health", watcher_check)
    catalog = {}

    def agent_check():
        catalog.update(reader.json("/agent/capabilities", True))
        require(
            catalog.get("schema_version") == "InteractiveAgent/v1",
            "Agent catalog version unavailable",
        )
        paper(catalog.get("paper_safety", {}))
        safety = catalog["paper_safety"]
        require(
            safety.get("agent_can_enable_real_trading") is False
            and safety.get("execution_attempted") is False,
            "Agent authority contract unsafe",
        )
        require(
            any(
                item.get("capability") == "general_conversation"
                and item.get("status") == "implemented"
                for item in catalog.get("items", [])
            ),
            "Agent conversation unavailable",
        )

    check("agent_capabilities", agent_check)
    check("journal_read", lambda: paginated(reader.json("/journal/trades?limit=1", True)))
    check("strategies_read", lambda: paginated(reader.json("/strategies?limit=1", True)))

    def knowledge_check():
        readiness = reader.json("/health/ready")
        fresh(readiness.get("timestamp"))
        require(
            readiness.get("ready") is True
            and readiness.get("providers_unavailable") == 0
            and readiness.get("providers_total", 0) > 0,
            "provider readiness degraded or empty",
        )
        providers = reader.json("/providers/status")
        fresh(providers.get("generated_at"))
        for kind in ("llm", "embeddings", "vector"):
            matches = [item for item in providers.get("providers", []) if item.get("kind") == kind]
            require(bool(matches), f"{kind} provider absent")
            require(
                all(
                    item.get("health") == "healthy"
                    and item.get("is_mock") is False
                    and item.get("using_fallback") is False
                    for item in matches
                ),
                f"{kind} provider degraded, mock or fallback",
            )
        paginated(reader.json("/knowledge/documents?limit=1", True))
        paginated(reader.json("/knowledge/chunks?limit=1", True))
        return "provider and storage readiness; no inference or ingestion performed"

    check("knowledge_readiness", knowledge_check)

    def signal_check():
        paginated(reader.json("/tradingview/signals?limit=1", True))
        paginated(reader.json("/paper-signal-orchestration/decisions?limit=1", True))
        return "read interfaces ready; no signal injected or orchestrated"

    check("signal_readiness", signal_check)

    def telegram_check():
        require(
            health.get("telegram_network_permitted") is False,
            "Telegram network must remain disabled",
        )
        for flag in (
            "telegram_paper_activation_armed",
            "telegram_interaction_enabled",
            "telegram_alerts_enabled",
            "automatic_telegram_delivery_enabled",
        ):
            require(health.get(flag) is False, f"Telegram health {flag} must be false")
        observed_worker = disarmed_worker(health, "telegram")
        posture = reader.json("/health/telegram-paper-activation")
        paper(posture)
        for key in (
            "enable_real_trading",
            "telegram_network_permitted",
            "telegram_paper_activation_armed",
            "telegram_interaction_enabled",
            "telegram_alerts_enabled",
            "automatic_telegram_delivery_enabled",
            "runtime_armable",
        ):
            require(posture.get(key) is False, f"Telegram {key} must be false")
        require(
            posture.get("confirmation_identity_required") is True,
            "Telegram confirmation identity contract missing",
        )
        forbidden = posture.get("forbidden", {})
        keys = (
            "mint_candidate",
            "override_setup_assessment",
            "override_risk",
            "activate_strategy",
            "create_live_order",
            "enable_live_trading",
        )
        require(
            all(forbidden.get(key) is False for key in keys),
            "Telegram forbidden authority contract unsafe",
        )
        require(posture.get("verdict") == "NOT_ARMED", "Telegram must report NOT_ARMED")
        return {
            "delivery": "DISABLED",
            "worker": observed_worker,
            "operator_blockers": posture.get("blockers", []),
            "recipient_bound": posture.get("recipient_bound", False),
            "physical_message": "NOT_TESTED",
        }

    check("telegram_readiness", telegram_check)

    def voice_check():
        voice = [item for item in catalog.get("items", []) if item.get("capability") == "voice_io"]
        require(
            len(voice) == 1 and voice[0].get("status") == "contract_only",
            "backend Voice must remain contract-only",
        )
        html = reader.read(reader.frontend, "/agent", frontend=True).decode()
        path = asset.get("path", "")
        require(
            path.startswith("/_next/static/") and path.endswith(".js") and ".." not in path,
            "pinned Agent asset path required",
        )
        require(path in unquote(html), "frontend Agent asset missing or stale")
        raw = reader.read(reader.frontend, path)
        require(
            hashlib.sha256(raw).hexdigest() == asset.get("sha256"),
            "frontend Agent asset SHA256 mismatch",
        )
        source = raw.decode()
        for marker in (
            "agent-voice-status",
            "Start recording",
            "Send transcript",
            "Read Agent reply",
            "Stop speech",
        ):
            require(marker in source, f"frontend Voice contract missing: {marker}")
        return "pinned browser Voice controls; physical microphone/speech NOT_TESTED"

    check("voice_frontend_contract", voice_check)
    return {
        "status": "PASS" if all(item["status"] == "PASS" for item in results) else "FAIL",
        "expected_git_sha": expected_sha,
        "network_delivery_activated": False,
        "execution_called": False,
        "checks": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend-contract", type=Path)
    parser.add_argument(
        "--capture-frontend-contract", type=Path, help="Write a local build asset pin; no network"
    )
    parser.add_argument("--build-dir", type=Path, default=Path("frontend/.next"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        if args.capture_frontend_contract:
            assets = list(args.build_dir.glob("static/chunks/app/(app)/agent/page-*.js"))
            require(len(assets) == 1, "build must contain exactly one Agent page bundle")
            asset = assets[0]
            payload = {
                "path": "/_next/" + asset.relative_to(args.build_dir).as_posix(),
                "sha256": hashlib.sha256(asset.read_bytes()).hexdigest(),
            }
            args.capture_frontend_contract.write_text(json.dumps(payload, indent=2) + "\n")
            print("Pinned local Agent build asset; no network used")
            return 0
        for name in (
            "ACCEPTANCE_API_URL",
            "ACCEPTANCE_FRONTEND_URL",
            "ACCEPTANCE_EXPECTED_SHA",
            "SMOKE_ACCESS_TOKEN",
        ):
            require(bool(os.environ.get(name)), f"{name} is required")
        require(
            args.frontend_contract is not None,
            "--frontend-contract from the accepted local build is required",
        )
        asset = json.loads(args.frontend_contract.read_text())
        reader = Reader(
            os.environ["ACCEPTANCE_API_URL"],
            os.environ["ACCEPTANCE_FRONTEND_URL"],
            os.environ["SMOKE_ACCESS_TOKEN"],
        )
        result = run(reader, os.environ["ACCEPTANCE_EXPECTED_SHA"], asset)
        rendered = json.dumps(result, indent=2) + "\n"
        if args.output:
            args.output.write_text(rendered)
        print(rendered, end="")
        return 0 if result["status"] == "PASS" else 1
    except (AcceptanceError, OSError, json.JSONDecodeError) as error:
        # File/connection errors may contain credential-bearing paths: redact.
        reason = str(error) if isinstance(error, AcceptanceError) else "input/output unavailable"
        print(f"ACCEPTANCE FAILED: {reason}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

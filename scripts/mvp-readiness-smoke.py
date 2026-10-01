#!/usr/bin/env python3
"""Disarmed staging reads. No registration, scans, approvals or execution."""

import argparse
import os
from uuid import UUID

import httpx


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def run(client, *, email, password, symbols, setup_id=None):
    def request(method, path, **kwargs):
        response = client.request(method, path, **kwargs)
        require(response.status_code == 200, f"{method} {path}: HTTP {response.status_code}")
        return response.json()

    health = request("GET", "/health")
    require(health.get("environment") in {"local", "staging"}, "Refusing production")
    require(health.get("execution_mode") == "paper", "Execution must be paper")
    require(health.get("exchange_mode") == "paper_internal", "Exchange must be paper_internal")
    for flag in (
        "real_trading_enabled",
        "watcher_orchestration_enabled",
        "watcher_paper_staging_activation",
        "market_watcher_enabled",
        "market_watcher_bridge_enabled",
        "telegram_alerts_enabled",
        "telegram_interaction_enabled",
        "automatic_telegram_delivery_enabled",
        "telegram_paper_activation_armed",
        "telegram_network_permitted",
    ):
        require(health.get(flag) is False, f"Unsafe or absent health flag: {flag}")
    require(health.get("telegram_inbound_mode") == "off", "Telegram inbound must be off")
    login = request("POST", "/auth/login", json={"email": email, "password": password})
    client.headers["Authorization"] = "Bearer " + login["tokens"]["access_token"]
    config = request("GET", "/watcher/watchlist")
    configured = {slot["symbol"] for slot in config["slots"] if slot["enabled"]}
    require(config.get("paper_only") is True, "Watchlist must be paper only")
    require(configured == symbols, "Configured universe differs from SMOKE_SYMBOLS")
    status = request("GET", "/watcher/watchlist/status")
    require(status["configuration_revision"] == config["revision"], "Watchlist revision drift")
    require(status.get("real_trading_enabled") is False, "Unsafe Watcher status")
    require(
        {s["symbol"] for s in status["symbols"] if s["enabled"]} == symbols,
        "Watcher status universe differs",
    )
    runtime = request("GET", "/watcher/paper-runtime/status")
    require(
        runtime.get("enabled") is False and runtime.get("running") is False,
        "Watcher runtime must be disarmed; inspect persisted status",
    )
    brain = request("GET", "/strategy-brain/overview")
    require(set(brain["watched_symbols"]) == symbols, "Brain universe differs")
    message = "Which Nested setups are forming?"
    if setup_id:
        message += " " + str(UUID(setup_id))
    agent = request("POST", "/agent/turns", json={"message": message})
    require(
        agent.get("capability") == "strategy_brain" and agent.get("operation") == "read",
        "Agent must perform grounded Brain read",
    )
    for flag in ("execution_attempted", "real_trading_enabled", "authority_mutated"):
        require(agent.get(flag) is False, f"Unsafe Agent result: {flag}")
    require(not agent.get("proposals"), "Read must not propose changes")
    if not setup_id:
        request("GET", "/risk/kill-switch")
        request("GET", "/journal/trades")
        if not brain["setups"]:
            require("unknown" in agent["reply"].lower(), "Agent must disclose absent evidence")
        print("READS PASS; Candidate/risk/journal linkage NOT VALIDATED (use isolated fixture)")
        return
    setup = request("GET", f"/strategy-brain/setups/{UUID(setup_id)}")
    require(setup.get("current_market_claim") is False, "Stored setup must not claim live data")
    require(
        setup.get("candidate_id") and setup.get("decision_id") and setup.get("journal"),
        "Selected setup lacks Candidate, risk decision or journal linkage",
    )
    candidate_id = UUID(setup["candidate_id"])
    candidate = request("GET", f"/canonical/candidates/{candidate_id}")
    require(candidate["candidate"]["candidate_id"] == str(candidate_id), "Candidate mismatch")
    decision = request("GET", f"/canonical/candidates/{candidate_id}/eligibility")
    require(
        decision["evaluation"]["eligibility"]["eligibility_id"] == setup["decision_id"],
        "Decision mismatch",
    )
    journal_id = UUID(setup["journal"]["id"])
    journal = request("GET", f"/journal/trades/{journal_id}")
    require(journal["trade"]["id"] == str(journal_id), "Journal mismatch")
    require(
        any(ref["record_id"] == setup["setup_id"] for ref in agent["connections"]),
        "Agent lacks selected stored setup reference",
    )
    print("READS AND STORED PAPER LINKAGE PASS (no execution performed)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--setup-id", help="Existing tenant setup; never fabricated")
    args = parser.parse_args()
    base = os.environ["BASE_URL"].rstrip("/")
    url = httpx.URL(base)
    require(
        not url.username and not url.password and not url.query and not url.fragment,
        "BASE_URL must not contain credentials, query or fragment",
    )
    require(
        url.scheme == "https" or (url.scheme == "http" and url.host in {"localhost", "127.0.0.1"}),
        "Use HTTPS, or loopback HTTP",
    )
    symbols = {s.strip().upper() for s in os.environ["SMOKE_SYMBOLS"].split(",") if s.strip()}
    require(bool(symbols), "Explicit nonempty SMOKE_SYMBOLS required")
    with httpx.Client(base_url=base, timeout=15, follow_redirects=False) as client:
        run(
            client,
            email=os.environ["SMOKE_EMAIL"],
            password=os.environ["SMOKE_PASSWORD"],
            symbols=symbols,
            setup_id=args.setup_id,
        )


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, KeyError, ValueError, httpx.HTTPError) as exc:
        # Never dump responses, authentication tokens, credentials or request objects.
        raise SystemExit(
            f"SMOKE FAILED ({type(exc).__name__}); check inputs and readiness"
        ) from None

"""Run with ``python -m app.external_integrations.acceptance`` after deployment.

Public market probes run from this process using the production adapters. API
probes persist an advisory signal, a paper Candidate and an orchestration decision.
They never approve a proposal, execute an order, or activate Telegram.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx

from app.core.config import ExchangeMode, ExecutionMode, Settings
from app.evidence_pipeline.current_price import quote_current_price
from app.market_contracts.adapters.binance_usdm import BinanceUsdmPerpetualSource
from app.market_contracts.adapters.bybit_usdt_perpetual import BybitUsdtPerpetualSource
from app.market_contracts.adapters.protocol import PerpetualMarketSource
from app.market_contracts.derivatives import DerivativeMetric, require_derivative_observations
from app.market_contracts.errors import IncompleteTradeWindowError
from app.market_contracts.first_slice import first_slice_identity
from app.market_contracts.freshness import evaluate_freshness, first_slice_freshness_policy
from app.market_contracts.identity import InstrumentIdentity, binance_usdm_btcusdt
from app.market_contracts.identity import bybit_usdt_perpetual_btcusdt as bybit_instrument
from app.market_contracts.order_flow import (
    closed_order_flow_bounds,
    order_flow_identity,
    order_flow_lineage,
    order_flow_observation,
    require_order_flow,
)
from app.schemas.common import Timeframe
from app.schemas.tradingview_signal import CREATE_TRADINGVIEW_CANDIDATE_CONFIRM
from app.security.tradingview_webhook import compute_tradingview_signature

PASS, FAIL, NOT_CONFIGURED = "PASS", "FAIL", "NOT CONFIGURED"
INTEGRATIONS = ("Binance", "Bybit", "TradingView", "Paper Signal Orchestration", "BloFin demo sync")
_TELEGRAM_FLAGS = (
    "telegram_alerts_enabled",
    "telegram_interaction_enabled",
    "telegram_network_permitted",
    "telegram_paper_activation_armed",
    "automatic_telegram_delivery_enabled",
)


class AcceptanceError(ValueError):
    """Static, secret-free acceptance failure detail."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AcceptanceError(message)


def result(name: str, status: str, detail: str, **evidence: Any) -> dict[str, Any]:
    return {"integration": name, "status": status, "detail": detail, **evidence}


def run_check(name: str, check: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        return check()
    except AcceptanceError as exc:
        return result(name, FAIL, str(exc))
    except Exception as exc:
        # Raw HTTP bodies, headers, URLs and exception messages can contain secrets.
        return result(name, FAIL, f"Check failed ({type(exc).__name__}); inspect safe server logs.")


def check_market(
    name: str,
    source: PerpetualMarketSource,
    instrument: InstrumentIdentity,
    *,
    warmup_seconds: int = 0,
) -> dict[str, Any]:
    identity = first_slice_identity(
        timeframe=Timeframe.M15, replay=False, is_live=True, instrument=instrument
    )
    if warmup_seconds:
        # Reuse the adapter's bounded overlap proof. Never claim a truncated REST page
        # covers a ten-minute window, and never widen any freshness threshold.
        deadline = time.monotonic() + warmup_seconds
        flow_identity = order_flow_identity(identity)
        while time.monotonic() < deadline:
            now = datetime.now(UTC)
            start, _end = closed_order_flow_bounds(now)
            with suppress(IncompleteTradeWindowError):
                source.fetch_ordered_trades(
                    identity=flow_identity,
                    instrument=instrument,
                    start=start,
                    end=now,
                    source_connection_id=order_flow_lineage(flow_identity),
                    receive_at=now,
                )
            time.sleep(min(2.0, max(0.0, deadline - time.monotonic())))
    for timeframe, minimum, seconds in ((Timeframe.M15, 100, 900), (Timeframe.H4, 30, 14400)):
        now = datetime.now(UTC)
        scoped = identity.model_copy(update={"timeframe": timeframe})
        series = source.fetch_closed_ohlcv(
            identity=scoped,
            instrument=instrument,
            timeframe=timeframe,
            min_final_bars=minimum,
            evaluated_at=now,
        )
        age = (now - series.bars[-1].interval_end).total_seconds()
        require(series.identity == scoped and 0 <= age <= seconds + 10, "OHLCV identity/age.")

    now = datetime.now(UTC)
    observations = [
        source.fetch_derivative_observation(
            identity=identity, instrument=instrument, metric=metric, observed_at=now
        )
        for metric in DerivativeMetric
    ]
    require_derivative_observations(
        observations,
        required_metrics=list(DerivativeMetric),
        identity=identity,
        evaluated_at=datetime.now(UTC),
    )
    now = datetime.now(UTC)
    flow_identity = order_flow_identity(identity)
    start, end = closed_order_flow_bounds(now)
    snapshot = source.fetch_order_flow_snapshot(
        identity=flow_identity,
        instrument=instrument,
        start=start,
        end=end,
        source_connection_id=order_flow_lineage(flow_identity),
        receive_at=now,
    )
    flow = order_flow_observation(identity=flow_identity, observed_at=now, snapshot=snapshot)
    require_order_flow(flow, identity=flow_identity, evaluated_at=datetime.now(UTC))
    quote = quote_current_price(
        source,
        identity=identity,
        instrument=instrument,
        evaluated_at=datetime.now(UTC),
        connection_id=uuid4(),
        replay=False,
    )
    require(quote.usable_as_current_market_price, "Current price must be fresh live evidence.")
    completed_at = datetime.now(UTC)
    evaluate_freshness(
        source_time=quote.source_time,
        evaluated_at=completed_at,
        policy=first_slice_freshness_policy(),
        require_fresh=True,
    )
    require_derivative_observations(
        observations,
        required_metrics=list(DerivativeMetric),
        identity=identity,
        evaluated_at=completed_at,
    )
    require_order_flow(flow, identity=flow_identity, evaluated_at=completed_at)
    return result(
        name,
        PASS,
        "Closed OHLCV, trade-backed price, OI, funding and proven order flow verified.",
        instrument_id=instrument.instrument_id,
        provider=source.name,
        quote_source_time=quote.source_time.isoformat(),
        coverage_content_hash=flow.coverage_content_hash,
    )


class ApiAcceptance:
    def __init__(self, client: httpx.Client, organization_id: UUID, secret: str) -> None:
        self.client, self.organization_id, self.secret = client, organization_id, secret
        self.signal_id: str | None = None

    def data(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        response = self.client.request(method, path, **kwargs)
        response.raise_for_status()
        return response.json()

    def safety(self) -> None:
        health = self.data("GET", "/health")
        require(
            health.get("execution_mode") == "paper"
            and health.get("real_trading_enabled") is False
            and health.get("exchange_mode") == "paper_internal"
            and all(health.get(flag) is False for flag in _TELEGRAM_FLAGS),
            "Deployment must use paper_internal with Telegram disarmed.",
        )
        identity = self.data("GET", "/auth/me")
        require(
            identity["organization"]["id"] == str(self.organization_id),
            "Token organization must match the acceptance organization before writes.",
        )

    def tradingview(self) -> dict[str, Any]:
        alert = f"external-acceptance-{uuid4()}"
        payload = {
            "organization_id": str(self.organization_id),
            "alert_id": alert,
            "idempotency_key": alert,
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "direction": "long",
            "confidence": 1.0,
            "source": {"purpose": "external_integration_acceptance"},
        }
        raw = json.dumps(payload, separators=(",", ":")).encode()
        timestamp = int(time.time())

        def send(body: bytes, moment: int, signature: str) -> httpx.Response:
            return self.client.post(
                "/webhooks/tradingview",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-AT-Timestamp": str(moment),
                    "X-AT-Signature": signature,
                },
            )

        signature = compute_tradingview_signature(raw, timestamp=timestamp, secret=self.secret)
        probe = send(raw, timestamp, "0" * 64)
        if probe.status_code == 503 and probe.json().get("error", {}).get("code") == (
            "tradingview_webhook_disabled"
        ):
            return result("TradingView", NOT_CONFIGURED, "Webhook intake is disabled.")
        for body, moment, sig in (
            (raw, timestamp, "0" * 64),
            (raw + b" ", timestamp, signature),
            (
                raw,
                timestamp - 7200,
                compute_tradingview_signature(raw, timestamp=timestamp - 7200, secret=self.secret),
            ),
            (
                raw,
                timestamp + 7200,
                compute_tradingview_signature(raw, timestamp=timestamp + 7200, secret=self.secret),
            ),
        ):
            require(send(body, moment, sig).status_code == 401, "HMAC/replay must fail closed.")
        accepted = send(raw, timestamp, signature)
        accepted.raise_for_status()
        item = accepted.json()["signal"]
        self.signal_id = item["id"]
        require(item["organization_id"] == str(self.organization_id), "Signed organization scope.")
        duplicate = send(raw, timestamp, signature)
        duplicate.raise_for_status()
        require(
            duplicate.json()["duplicate"] is True
            and duplicate.json()["signal"]["id"] == self.signal_id,
            "Idempotent intake.",
        )
        changed = raw.replace(b'"long"', b'"short"')
        require(
            send(
                changed,
                timestamp,
                compute_tradingview_signature(changed, timestamp=timestamp, secret=self.secret),
            ).status_code
            == 422,
            "Idempotency payload mismatch must reject.",
        )
        stored = self.data("GET", f"/tradingview/signals/{self.signal_id}")
        require(stored["id"] == self.signal_id, "Signal Inbox persistence.")
        path = f"/tradingview/signals/{self.signal_id}/create-candidate"
        require(
            self.client.post(path, json={"confirm": "INVALID"}).status_code == 422,
            "Candidate creation requires exact confirmation.",
        )
        candidate = self.data("POST", path, json={"confirm": CREATE_TRADINGVIEW_CANDIDATE_CONFIRM})
        again = self.data("POST", path, json={"confirm": CREATE_TRADINGVIEW_CANDIDATE_CONFIRM})
        require(
            candidate["candidate_id"] == again["candidate_id"] and again["already_exists"],
            "Candidate creation must converge.",
        )
        return result(
            "TradingView",
            PASS,
            "HMAC, replay, idempotency, Inbox and Candidate verified.",
            signal_id=self.signal_id,
            candidate_id=candidate["candidate_id"],
        )

    def orchestration(self) -> dict[str, Any]:
        listing = self.data("GET", "/paper-signal-orchestration/decisions")
        if listing.get("enabled") is not True:
            return result(
                "Paper Signal Orchestration", NOT_CONFIGURED, "Orchestration is disabled."
            )
        if self.signal_id is None:
            return result(
                "Paper Signal Orchestration", FAIL, "TradingView acceptance did not complete."
            )
        path = f"/paper-signal-orchestration/signals/{self.signal_id}/orchestrate"
        decision = self.data("POST", path)["decision"]
        again = self.data("POST", path)["decision"]
        require(decision["id"] == again["id"], "Orchestration must converge.")
        require(
            decision["status"] in {"eligible", "paper_candidate_created", "awaiting_review"},
            "Signal must be eligible; risk blocks must not be converted to PASS.",
        )
        require(
            decision["risk_checks"] and all(c["passed"] for c in decision["risk_checks"]),
            "Risk checks must pass.",
        )
        require(decision["links"]["proposal_id"] is None, "No proposal without human approval.")
        if decision["mode"] != "observe_only":
            require(decision["links"]["candidate_id"] is not None, "Candidate authority required.")
        return result(
            "Paper Signal Orchestration",
            PASS,
            "Governed, idempotent paper decision verified.",
            decision_id=decision["id"],
            mode=decision["mode"],
        )

    def blofin(self) -> dict[str, Any]:
        config = self.data("GET", "/health")
        if (
            config.get("blofin_readonly_sync_enabled") is False
            or config.get("blofin_readonly_sync_credentials_configured") is False
        ):
            return result(
                "BloFin demo sync",
                NOT_CONFIGURED,
                "Dedicated demo sync is disabled or credentials are missing.",
            )
        snap = self.data("POST", "/exchange/blofin/sync")["snapshot"]
        if (
            snap.get("provenance", {}).get("credentials_configured") is False
            or snap.get("provenance", {}).get("readonly_sync_enabled") is False
        ):
            return result(
                "BloFin demo sync", NOT_CONFIGURED, "Dedicated demo sync credentials missing."
            )
        require(snap["health_status"] == "ok" and snap["is_stale"] is False, "BloFin health/age.")
        permissions = snap["account_snapshot"]["permissions"]
        require(
            permissions["can_read"]
            and not permissions["can_trade"]
            and not permissions["can_withdraw"]
            and not permissions["can_transfer"],
            "Read-only credentials without money-movement scopes required.",
        )
        require(
            snap["account_snapshot"]["provider_status"]["is_mock"] is False,
            "Mock account data cannot pass live sync acceptance.",
        )
        require(
            snap["provenance"]["read_only"] is True
            and snap["provenance"]["order_mutations"] is False,
            "Read-only sync provenance.",
        )
        require(
            isinstance(snap["account_snapshot"]["balances"], list)
            and isinstance(snap["positions_snapshot"]["items"], list),
            "Account evidence.",
        )
        latest = self.data("GET", "/exchange/blofin/sync/latest")
        require(latest["id"] == snap["id"] and latest["is_stale"] is False, "Snapshot persistence.")
        return result(
            "BloFin demo sync",
            PASS,
            "Fresh read-only account/position snapshot persisted.",
            snapshot_id=snap["id"],
        )


def run(
    settings: Settings,
    *,
    api_url: str,
    token: str,
    organization_id: UUID | None,
    api_transport: httpx.BaseTransport | None = None,
    market_transport: httpx.BaseTransport | None = None,
    bybit_warmup_seconds: int = 0,
) -> dict[str, Any]:
    names = INTEGRATIONS
    safe = (
        settings.execution_mode is ExecutionMode.PAPER
        and not settings.enable_real_trading
        and settings.exchange_mode is ExchangeMode.PAPER_INTERNAL
        and all(getattr(settings, flag) is False for flag in _TELEGRAM_FLAGS)
    )
    if not safe:
        return {
            "results": [
                result(n, FAIL, "Unsafe local configuration; no probes performed.") for n in names
            ]
        }
    results = []
    for name, source, instrument in (
        (
            "Binance",
            BinanceUsdmPerpetualSource(transport=market_transport, max_retries=0),
            binance_usdm_btcusdt(),
        ),
        (
            "Bybit",
            BybitUsdtPerpetualSource(transport=market_transport, max_retries=0),
            bybit_instrument(),
        ),
    ):
        try:
            results.append(
                run_check(
                    name,
                    partial(
                        check_market,
                        name,
                        source,
                        instrument,
                        warmup_seconds=bybit_warmup_seconds if name == "Bybit" else 0,
                    ),
                )
            )
        finally:
            source.close()
    if not api_url or not token or organization_id is None:
        results.extend(
            result(n, NOT_CONFIGURED, "API URL, owner token and organization ID required.")
            for n in names[2:]
        )
    else:
        with httpx.Client(
            base_url=api_url.rstrip("/"),
            transport=api_transport,
            timeout=30,
            follow_redirects=False,
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            api = ApiAcceptance(client, organization_id, settings.tradingview_webhook_secret)
            safety = run_check("deployment safety", lambda: api.safety() or {"status": PASS})
            if safety["status"] != PASS:
                results.extend(
                    result(n, FAIL, "Deployment safety preflight failed; no API writes.")
                    for n in names[2:]
                )
            else:
                results.append(run_check("BloFin demo sync", api.blofin))
                results.append(
                    run_check("TradingView", api.tradingview)
                    if api.secret
                    else result("TradingView", NOT_CONFIGURED, "Webhook signing secret missing.")
                )
                if results[-1]["status"] == NOT_CONFIGURED:
                    results.append(
                        result(
                            "Paper Signal Orchestration",
                            NOT_CONFIGURED,
                            "TradingView acceptance is not configured.",
                        )
                    )
                else:
                    results.append(run_check("Paper Signal Orchestration", api.orchestration))
    return {"checked_at": datetime.now(UTC).isoformat(), "results": results}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default=os.getenv("AT_ACCEPTANCE_API_URL", ""))
    parser.add_argument(
        "--organization-id", type=UUID, default=os.getenv("AT_ACCEPTANCE_ORGANIZATION_ID")
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--bybit-warmup-seconds",
        type=int,
        default=0,
        help="Collect bounded overlap proof before Bybit acceptance (0..900).",
    )
    args = parser.parse_args()
    if not 0 <= args.bybit_warmup_seconds <= 900:
        parser.error("--bybit-warmup-seconds must be between 0 and 900")
    try:
        settings = Settings()
    except Exception:
        report = {
            "results": [
                result(name, FAIL, "Invalid runtime settings; no probes performed.")
                for name in INTEGRATIONS
            ]
        }
    else:
        report = run(
            settings,
            api_url=args.api_url,
            token=os.getenv("AT_ACCEPTANCE_TOKEN", ""),
            organization_id=args.organization_id,
            bybit_warmup_seconds=args.bybit_warmup_seconds,
        )
    encoded = json.dumps(report, indent=2)
    if args.output:
        args.output.write_text(encoded + "\n")
    print(encoded)
    return 0 if all(r["status"] == PASS for r in report["results"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())

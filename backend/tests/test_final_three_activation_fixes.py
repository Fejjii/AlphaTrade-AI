"""The three still-open PR132 findings. Paper only. No deploy and no activation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
import yaml

from app.api.routes.health import _read_worker_runtime
from app.core.config import Settings
from app.core.dependencies import get_canonical_evidence_service
from app.market_contracts.adapters.aggtrade_cache import (
    ClosedAggTradeCache,
    closed_agg_trade_window_key,
)
from app.market_contracts.adapters.binance_usdm import BinanceUsdmPerpetualSource
from app.market_contracts.adapters.evidence_pool import reset_shared_binance_evidence_pools
from app.market_contracts.adapters.factory import (
    canonical_evidence_source_for_process,
    resolve_perpetual_evidence_source,
)
from app.market_contracts.adapters.http import ReadOnlyHttpGetClient
from app.market_contracts.adapters.request_budget import SlidingWeightBudget
from app.market_contracts.errors import RateLimitedError, RegionalProviderFailureError
from app.market_contracts.request_progress import (
    bind_market_request_progress,
    reset_market_request_progress,
)
from app.persistence.composition import build_postgres_watcher_store
from app.persistence.runtime_health import project_worker_component
from app.persistence.runtime_status import (
    TELEGRAM_COMPONENT,
    WATCHER_COMPONENT,
    RuntimeStatusWrite,
    load_runtime_rows,
    publish_runtime_status,
)
from app.watcher.memory import FakeClock, InMemoryWatcherStore
from tests.support.postgres_persistence import persistence_session_factory, requires_postgres

ROOT = Path(__file__).resolve().parents[2]
START = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)
END = START + timedelta(minutes=30)
EVENT_MS = int(START.timestamp() * 1000) + 1_000
_SECRET_PLACEHOLDERS = {
    "DATABASE_URL": "postgresql+psycopg://user:pass@db.example.com:5432/alphatrade",
    "REDIS_URL": "redis://redis.example.com:6379/0",
    "QDRANT_URL": "https://qdrant.example.com",
    "JWT_SECRET": "j" * 48,
    "OPENAI_API_KEY": "sk-test-not-a-real-key",
}
_WORKER_SERVICES = (
    ("alphatrade-watcher-paper-staging", "python -m app.workers.watcher_paper"),
    ("alphatrade-telegram-paper-staging", "python -m app.telegram_activation run"),
)


@pytest.fixture(autouse=True)
def _isolated_evidence_pools() -> object:
    reset_shared_binance_evidence_pools()
    yield
    reset_shared_binance_evidence_pools()


def _live_settings(**overrides: object) -> Settings:
    payload: dict[str, object] = {
        "environment": "local",
        "execution_mode": "paper",
        "enable_real_trading": False,
        "exchange_mode": "paper_internal",
        "provider_mode": "mock",
        "rate_limit_use_redis": False,
        "market_data_cache_use_redis": False,
        "access_token_denylist_use_redis": False,
        "perpetual_evidence_source": "binance_usdm",
        "market_data_futures_base_url": "https://fapi.binance.com",
        "binance_request_weight_per_minute": 1800,
        "binance_evidence_cache_entries": 4,
        "binance_evidence_cache_ttl_seconds": 120,
    }
    payload.update(overrides)
    return Settings(**payload)


def _trade(price: str, agg_id: int = 1) -> dict[str, object]:
    return {"a": agg_id, "p": price, "q": "1", "T": EVENT_MS, "m": False}


def _source(
    handler: object,
    *,
    cache: ClosedAggTradeCache | None = None,
    budget: SlidingWeightBudget | None = None,
    weight_per_minute: int = 1800,
    progress_interval_seconds: float = 0.05,
) -> BinanceUsdmPerpetualSource:
    return BinanceUsdmPerpetualSource(
        transport=httpx.MockTransport(handler),  # type: ignore[arg-type]
        trade_cache=cache,
        budget=budget,
        weight_per_minute=weight_per_minute,
        max_backoff_seconds=0,
        progress_interval_seconds=progress_interval_seconds,
        trade_cache_entries=4,
        cache_ttl_seconds=120,
    )


def _read(source: BinanceUsdmPerpetualSource, symbol: str = "BTCUSDT") -> tuple[object, ...]:
    return source._cached_agg_trades(symbol=symbol, start=START, end=END)


def test_process_canonical_reads_share_one_cache_and_budget() -> None:
    settings = _live_settings()
    state = SimpleNamespace()
    first = canonical_evidence_source_for_process(state, settings)
    second = canonical_evidence_source_for_process(state, settings)
    assert first is second
    assert isinstance(first, BinanceUsdmPerpetualSource)
    again = resolve_perpetual_evidence_source(settings, shared=True)
    isolated = resolve_perpetual_evidence_source(settings)
    assert again is not first
    assert again.evidence_cache is first.evidence_cache
    assert again.request_budget is first.request_budget
    assert isolated.evidence_cache is not first.evidence_cache
    assert isolated.request_budget is not first.request_budget
    request = SimpleNamespace(app=SimpleNamespace(state=state))
    service_a = get_canonical_evidence_service(request, settings, None)  # type: ignore[arg-type]
    service_b = get_canonical_evidence_service(request, settings, None)  # type: ignore[arg-type]
    assert service_a._source is service_b._source is first
    first.close()
    again.close()
    isolated.close()


def test_concurrent_reads_reuse_one_closed_window_and_keep_symbols_apart() -> None:
    calls = {"n": 0}
    entered = {"n": 0}
    release = threading.Event()

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        symbol = request.url.params["symbol"]
        if symbol == "BTCUSDT" and calls["n"] == 1:
            entered["n"] += 1
            assert release.wait(2)
        price = "10" if symbol == "BTCUSDT" else "20"
        agg_id = 1 if symbol == "BTCUSDT" else 2
        return httpx.Response(200, json=[_trade(price, agg_id)])

    cache = ClosedAggTradeCache(max_entries=4, ttl_seconds=120, clock=lambda: 0.0)
    budget = SlidingWeightBudget(limit=200, max_wait_seconds=0.0, _clock=lambda: 0.0)
    left = _source(handler, cache=cache, budget=budget)
    right = _source(handler, cache=cache, budget=budget)
    assert left.evidence_cache is right.evidence_cache
    assert left.request_budget is right.request_budget
    found: list[tuple[object, ...]] = []

    def read_btc() -> None:
        found.append(_read(left, "BTCUSDT"))

    worker = threading.Thread(target=read_btc)
    worker.start()
    deadline = time.monotonic() + 2
    while entered["n"] < 1 and time.monotonic() < deadline:
        time.sleep(0.01)
    other = threading.Thread(target=read_btc)
    other.start()
    time.sleep(0.05)
    assert other.is_alive()
    assert calls["n"] == 1
    release.set()
    worker.join(2)
    other.join(2)
    assert len(found) == 2
    assert found[0] == found[1]
    assert calls["n"] == 1
    eth = _read(right, "ETHUSDT")
    assert calls["n"] == 2
    assert eth != found[0]
    assert str(uuid4()) not in "".join(closed_agg_trade_window_key("BTCUSDT", START, END))
    shifted = START.astimezone(timezone(timedelta(hours=1)))
    shifted_end = END.astimezone(timezone(timedelta(hours=1)))
    assert closed_agg_trade_window_key("btcusdt", shifted, shifted_end) == (
        closed_agg_trade_window_key("BTCUSDT", START, END)
    )
    assert _read(left, "BTCUSDT") == found[0]
    assert calls["n"] == 2
    left.close()
    right.close()


def test_window_correction_replaces_rows_and_expiry_does_not_serve_stale() -> None:
    clock = {"t": 0.0}
    prices = {"BTCUSDT": "1"}
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json=[_trade(prices[request.url.params["symbol"]])])

    cache = ClosedAggTradeCache(max_entries=1, ttl_seconds=10, clock=lambda: clock["t"])
    source = _source(handler, cache=cache)
    first = _read(source)
    assert first[0]["p"] == "1"  # type: ignore[index]
    prices["BTCUSDT"] = "2"
    assert _read(source) == first
    assert calls["n"] == 1
    assert cache.corrections == 0
    clock["t"] = 10
    assert _read(source) == first
    assert calls["n"] == 1
    clock["t"] = 10.001
    corrected = _read(source)
    assert corrected[0]["p"] == "2"  # type: ignore[index]
    assert corrected != first
    assert cache.corrections == 1
    assert calls["n"] == 2
    assert _read(source) == corrected
    assert calls["n"] == 2
    prices["ETHUSDT"] = "3"
    eth = _read(source, "ETHUSDT")
    assert eth[0]["p"] == "3"  # type: ignore[index]
    assert calls["n"] == 3
    prices["BTCUSDT"] = "4"
    refilled = _read(source, "BTCUSDT")
    assert refilled[0]["p"] == "4"  # type: ignore[index]
    assert calls["n"] == 4
    source.close()


def test_failed_windows_release_locks_so_memory_stays_bounded() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("network down")

    cache = ClosedAggTradeCache(max_entries=2, ttl_seconds=30, clock=lambda: 0.0)
    source = BinanceUsdmPerpetualSource(
        transport=httpx.MockTransport(handler),
        trade_cache=cache,
        max_retries=0,
        max_backoff_seconds=0,
        weight_per_minute=1800,
    )
    for index in range(12):
        with pytest.raises(RegionalProviderFailureError):
            _read(source, f"S{index}USDT")
    assert cache.tracked_lock_count() == 0
    assert len(cache) == 0
    source.close()


def test_shared_budget_fails_closed_and_restart_drops_the_cache() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        symbol = request.url.params["symbol"]
        return httpx.Response(200, json=[_trade("1" if symbol == "BTCUSDT" else "2")])

    budget = SlidingWeightBudget(limit=20, max_wait_seconds=0.0, _clock=lambda: 0.0)
    cache = ClosedAggTradeCache(max_entries=4, ttl_seconds=120, clock=lambda: 0.0)
    primary = _source(handler, cache=cache, budget=budget, weight_per_minute=20)
    secondary = _source(handler, cache=cache, budget=budget, weight_per_minute=20)
    assert _read(primary, "BTCUSDT")[0]["p"] == "1"  # type: ignore[index]
    with pytest.raises(RateLimitedError):
        _read(secondary, "ETHUSDT")
    assert calls["n"] == 1
    assert budget.used() == 20
    primary.close()
    secondary.close()

    settings = _live_settings(binance_evidence_cache_ttl_seconds=30)
    created = resolve_perpetual_evidence_source(
        settings, transport=httpx.MockTransport(handler), shared=True
    )
    assert isinstance(created, BinanceUsdmPerpetualSource)
    _read(created, "BTCUSDT")
    before = calls["n"]
    reset_shared_binance_evidence_pools()
    restarted = resolve_perpetual_evidence_source(
        settings, transport=httpx.MockTransport(handler), shared=True
    )
    assert isinstance(restarted, BinanceUsdmPerpetualSource)
    assert restarted.evidence_cache is not created.evidence_cache
    _read(restarted, "BTCUSDT")
    assert calls["n"] == before + 1
    created.close()
    restarted.close()


def test_slow_successful_get_heartbeats_and_timeout_and_429_do_too() -> None:
    beats = {"during": 0}
    phase = {"in_get": False}

    def hook() -> None:
        if phase["in_get"]:
            beats["during"] += 1

    def slow(request: httpx.Request) -> httpx.Response:
        del request
        phase["in_get"] = True
        deadline = time.monotonic() + 2
        while beats["during"] < 1:
            if time.monotonic() > deadline:
                raise AssertionError("slow GET completed without a heartbeat")
            time.sleep(0.01)
        phase["in_get"] = False
        return httpx.Response(200, json={"ok": True})

    token = bind_market_request_progress(hook)
    try:
        client = ReadOnlyHttpGetClient(
            base_url="https://fapi.binance.com",
            timeout_seconds=2.0,
            transport=httpx.MockTransport(slow),
            progress_interval_seconds=0.05,
            sleeper=lambda _seconds: None,
        )
        assert client.get_json("/fapi/v1/ping") == {"ok": True}
        client.close()
        assert beats["during"] >= 1

        beats["during"] = 0
        calls = {"n": 0}

        def limited(_request: httpx.Request) -> httpx.Response:
            phase["in_get"] = True
            deadline = time.monotonic() + 2
            while beats["during"] < 1:
                if time.monotonic() > deadline:
                    raise AssertionError("429 GET completed without a heartbeat")
                time.sleep(0.01)
            phase["in_get"] = False
            calls["n"] += 1
            if calls["n"] == 1:
                return httpx.Response(429, headers={"Retry-After": "1"}, json={"msg": "slow"})
            return httpx.Response(200, json={"ok": True})

        sleeps: list[float] = []
        limited_client = ReadOnlyHttpGetClient(
            base_url="https://fapi.binance.com",
            timeout_seconds=2.0,
            transport=httpx.MockTransport(limited),
            max_retries=1,
            max_backoff_seconds=30.0,
            progress_interval_seconds=0.05,
            sleeper=sleeps.append,
        )
        assert limited_client.get_json("/fapi/v1/aggTrades", {"symbol": "BTCUSDT"}) == {"ok": True}
        limited_client.close()
        assert calls["n"] == 2
        assert sleeps == [1.0]
        assert beats["during"] >= 1

        beats["during"] = 0

        def timed_out(_request: httpx.Request) -> httpx.Response:
            phase["in_get"] = True
            deadline = time.monotonic() + 2
            while beats["during"] < 1:
                if time.monotonic() > deadline:
                    raise AssertionError("timed out GET completed without a heartbeat")
                time.sleep(0.01)
            phase["in_get"] = False
            raise httpx.ReadTimeout("network timeout")

        timeout_client = ReadOnlyHttpGetClient(
            base_url="https://fapi.binance.com",
            timeout_seconds=2.0,
            transport=httpx.MockTransport(timed_out),
            max_retries=0,
            progress_interval_seconds=0.05,
            sleeper=lambda _seconds: (_ for _ in ()).throw(AssertionError("no retry sleep")),
        )
        with pytest.raises(RegionalProviderFailureError):
            timeout_client.get_json("/fapi/v1/time")
        timeout_client.close()
        assert beats["during"] >= 1
    finally:
        reset_market_request_progress(token)


def test_slow_get_keeps_the_lease_and_takeover_waits_until_heartbeats_stop() -> None:
    store = InMemoryWatcherStore()
    clock = FakeClock()
    org = uuid4()
    claimed, lease, _reason = store.claim_lease(
        organization_id=org,
        scan_scope="btc",
        owner_id="worker-a",
        ttl_seconds=5,
        now=clock.now(),
    )
    assert claimed is True
    phase = {"in_get": False, "renewed": 0}

    def hook() -> None:
        if not phase["in_get"]:
            return
        renewed = store.renew_lease(
            organization_id=org,
            scan_scope="btc",
            owner_id="worker-a",
            fencing_token=lease.fencing_token,
            ttl_seconds=30,
            now=clock.now(),
        )
        if renewed:
            phase["renewed"] += 1

    def handler(_request: httpx.Request) -> httpx.Response:
        phase["in_get"] = True
        deadline = time.monotonic() + 2
        while phase["renewed"] < 1:
            if time.monotonic() > deadline:
                raise AssertionError("lease heartbeat did not run during the GET")
            time.sleep(0.01)
        clock.advance(20)
        taken, _held, reason = store.claim_lease(
            organization_id=org,
            scan_scope="btc",
            owner_id="worker-b",
            ttl_seconds=30,
            now=clock.now(),
        )
        assert taken is False
        assert reason == "lease_held"
        return httpx.Response(200, json={"ok": True})

    token = bind_market_request_progress(hook)
    try:
        client = ReadOnlyHttpGetClient(
            base_url="https://fapi.binance.com",
            timeout_seconds=2.0,
            transport=httpx.MockTransport(handler),
            progress_interval_seconds=0.05,
        )
        assert client.get_json("/fapi/v1/ping") == {"ok": True}
        client.close()
    finally:
        reset_market_request_progress(token)
    clock.advance(31)
    taken, taken_lease, reason = store.claim_lease(
        organization_id=org,
        scan_scope="btc",
        owner_id="worker-b",
        ttl_seconds=30,
        now=clock.now(),
    )
    assert taken is True
    assert reason == "claimed"
    assert taken_lease.fencing_token == lease.fencing_token + 1


def test_get_without_heartbeat_lets_the_lease_be_taken() -> None:
    store = InMemoryWatcherStore()
    clock = FakeClock()
    org = uuid4()
    store.claim_lease(
        organization_id=org,
        scan_scope="btc",
        owner_id="worker-a",
        ttl_seconds=5,
        now=clock.now(),
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        clock.advance(20)
        taken, _lease, reason = store.claim_lease(
            organization_id=org,
            scan_scope="btc",
            owner_id="worker-b",
            ttl_seconds=30,
            now=clock.now(),
        )
        assert taken is True
        assert reason == "claimed"
        return httpx.Response(200, json={"ok": True})

    client = ReadOnlyHttpGetClient(
        base_url="https://fapi.binance.com",
        timeout_seconds=2.0,
        transport=httpx.MockTransport(handler),
    )
    assert client.get_json("/fapi/v1/ping") == {"ok": True}
    client.close()


def _row(
    *,
    heartbeat_at: datetime | None,
    activation_state: str = "running",
    worker_id: str = "watcher-a",
) -> SimpleNamespace:
    return SimpleNamespace(
        heartbeat_at=heartbeat_at,
        activation_state=activation_state,
        worker_id=worker_id,
        lease_owner="watcher-a",
        lease_epoch=1,
        lease_expires_at=None,
        fence_held=True,
        last_scan_at=None,
        last_scan_reason="",
        market_source="binance_usdm",
        freshness_seconds=None,
        telegram_runtime_state="absent",
        inbound_mode="off",
        outbox_pending=0,
        outbox_retryable=0,
        outbox_dead_letter=0,
        last_delivery_at=None,
        last_error_code="",
        kill_switch_active=False,
        request_count=0,
        request_weight=0,
        rate_limited_count=0,
        cache_hits=0,
    )


def test_worker_health_uses_heartbeat_age_not_row_presence() -> None:
    now = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)
    limit = 90
    fresh = project_worker_component(
        _row(heartbeat_at=now - timedelta(seconds=1)),
        now=now,
        stale_after_seconds=limit,
    )
    assert fresh.health_state == "RUNNING"
    assert fresh.available is True
    assert fresh.activation_state == "running"
    assert fresh.heartbeat_age_seconds == 1
    boundary = project_worker_component(
        _row(heartbeat_at=now - timedelta(seconds=90)),
        now=now,
        stale_after_seconds=limit,
    )
    assert boundary.health_state == "RUNNING"
    assert boundary.available is True
    assert boundary.heartbeat_age_seconds == 90
    stale = project_worker_component(
        _row(heartbeat_at=now - timedelta(seconds=90, microseconds=1)),
        now=now,
        stale_after_seconds=limit,
    )
    assert stale.health_state == "STALE"
    assert stale.available is False
    assert stale.activation_state == "STALE"
    assert stale.activation_state != "running"
    missing = project_worker_component(None, now=now, stale_after_seconds=limit)
    assert missing.health_state == "UNAVAILABLE"
    assert missing.available is False
    assert missing.heartbeat_at is None
    skewed = project_worker_component(
        _row(heartbeat_at=now + timedelta(seconds=5)),
        now=now,
        stale_after_seconds=limit,
    )
    assert skewed.health_state == "STALE"
    assert skewed.available is False
    assert skewed.heartbeat_age_seconds is not None
    assert skewed.heartbeat_age_seconds < 0
    assert skewed.activation_state == "STALE"
    naive = project_worker_component(
        _row(heartbeat_at=datetime(2026, 9, 23, 12, 0)),
        now=now,
        stale_after_seconds=limit,
    )
    assert naive.health_state == "STALE"
    assert naive.available is False
    disarmed = project_worker_component(
        _row(heartbeat_at=now - timedelta(seconds=1), activation_state="disarmed"),
        now=now,
        stale_after_seconds=limit,
    )
    assert disarmed.health_state == "RUNNING"
    assert disarmed.activation_state == "disarmed"


def test_render_worker_blueprint_constructs_disarmed_staging_settings() -> None:
    document = yaml.safe_load((ROOT / "render.yaml").read_text(encoding="utf-8"))
    services = {item["name"]: item for item in document["services"]}
    assert "TELEGRAM_BOT_TOKEN" not in (ROOT / "render.yaml").read_text(encoding="utf-8")
    for name, command in _WORKER_SERVICES:
        service = services[name]
        assert service["dockerCommand"] == command
        env = _blueprint_env(service["envVars"])
        for secret in _SECRET_PLACEHOLDERS:
            assert secret not in env
        assert "TELEGRAM_BOT_TOKEN" not in env
        merged = {**env, **_SECRET_PLACEHOLDERS}
        built = _settings_from_environment(merged)
        assert built["environment"] == "staging"
        assert built["execution_mode"] == "paper"
        assert built["real_trading_enabled"] is False
        assert built["enable_real_trading"] is False
        assert built["watcher_orchestration_enabled"] is False
        assert built["watcher_paper_staging_activation"] is False
        assert built["telegram_paper_activation_armed"] is False
        assert built["telegram_network_permitted"] is False
        assert built["telegram_inbound_mode"] == "off"
        assert built["telegram_bot_token"] == ""
        assert built["auth_refresh_cookie_enabled"] is True
        assert built["auth_cookie_secure"] is True
        assert built["auth_cookie_samesite"] == "none"
        assert built["cors_origins"]
        assert all(origin.startswith("https://") for origin in built["cors_origins"])


def _blueprint_env(items: list[dict[str, object]]) -> dict[str, str]:
    env: dict[str, str] = {}
    for item in items:
        key = str(item["key"])
        if "value" not in item:
            continue
        value = item["value"]
        if isinstance(value, bool):
            env[key] = "true" if value else "false"
        else:
            env[key] = str(value)
    return env


def _settings_from_environment(env: dict[str, str]) -> dict[str, object]:
    script = """
import json, os
from app.core.config import Settings
payload = json.loads(os.environ["BLUEPRINT_JSON"])
os.environ.clear()
os.environ["BLUEPRINT_JSON"] = json.dumps(payload)
os.environ.update(payload)
settings = Settings()
print(json.dumps({
    "environment": settings.environment.value,
    "execution_mode": settings.execution_mode.value,
    "real_trading_enabled": settings.real_trading_enabled,
    "enable_real_trading": settings.enable_real_trading,
    "watcher_orchestration_enabled": settings.watcher_orchestration_enabled,
    "watcher_paper_staging_activation": settings.watcher_paper_staging_activation,
    "telegram_paper_activation_armed": settings.telegram_paper_activation_armed,
    "telegram_network_permitted": settings.telegram_network_permitted,
    "telegram_inbound_mode": settings.telegram_inbound_mode.value,
    "telegram_bot_token": settings.telegram_bot_token,
    "auth_refresh_cookie_enabled": settings.auth_refresh_cookie_enabled,
    "auth_cookie_secure": settings.auth_cookie_secure,
    "auth_cookie_samesite": settings.auth_cookie_samesite,
    "cors_origins": settings.cors_origins,
}))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        cwd="/tmp",
        capture_output=True,
        text=True,
        env={
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(ROOT / "backend" / "src"),
            "BLUEPRINT_JSON": json.dumps(env),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
    )
    assert completed.returncode == 0, completed.stderr
    loaded = json.loads(completed.stdout)
    assert isinstance(loaded, dict)
    return loaded


@requires_postgres
def test_postgres_worker_health_freshness_restart_and_skew(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = persistence_session_factory()
    monkeypatch.setattr("app.db.session.get_session_factory", lambda: factory)
    now = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)
    publish_runtime_status(
        factory,
        RuntimeStatusWrite(
            component=WATCHER_COMPONENT,
            worker_id="watcher-old",
            heartbeat_at=now - timedelta(seconds=1),
            activation_state="running",
        ),
    )
    with factory() as session:
        row = load_runtime_rows(session)[WATCHER_COMPONENT]
    fresh = project_worker_component(row, now=now, stale_after_seconds=90)
    assert fresh.health_state == "RUNNING"
    assert fresh.available is True
    assert fresh.worker_id == "watcher-old"
    publish_runtime_status(
        factory,
        RuntimeStatusWrite(
            component=WATCHER_COMPONENT,
            worker_id="watcher-old",
            heartbeat_at=now - timedelta(seconds=90),
            activation_state="running",
        ),
    )
    with factory() as session:
        boundary_row = load_runtime_rows(session)[WATCHER_COMPONENT]
    boundary = project_worker_component(boundary_row, now=now, stale_after_seconds=90)
    assert boundary.health_state == "RUNNING"
    assert boundary.available is True
    publish_runtime_status(
        factory,
        RuntimeStatusWrite(
            component=WATCHER_COMPONENT,
            worker_id="watcher-old",
            heartbeat_at=now - timedelta(seconds=91),
            activation_state="running",
        ),
    )
    settings = _live_settings(watcher_heartbeat_stale_after_seconds=90)
    observed = _read_worker_runtime(settings, now=now)
    assert observed.available is True
    assert observed.watcher.health_state == "STALE"
    assert observed.watcher.available is False
    assert observed.watcher.activation_state == "STALE"
    assert observed.telegram.health_state == "UNAVAILABLE"
    assert observed.telegram.available is False
    with factory() as session:
        assert TELEGRAM_COMPONENT not in load_runtime_rows(session)
    publish_runtime_status(
        factory,
        RuntimeStatusWrite(
            component=WATCHER_COMPONENT,
            worker_id="watcher-old",
            heartbeat_at=now + timedelta(seconds=5),
            activation_state="running",
        ),
    )
    with factory() as session:
        skewed_row = load_runtime_rows(session)[WATCHER_COMPONENT]
    skewed = project_worker_component(skewed_row, now=now, stale_after_seconds=90)
    skewed_health = _read_worker_runtime(settings, now=now)
    assert skewed.health_state == "STALE"
    assert skewed.available is False
    assert skewed.heartbeat_age_seconds is not None
    assert skewed.heartbeat_age_seconds < 0
    assert skewed_health.watcher.health_state == "STALE"
    assert skewed_health.watcher.available is False
    assert skewed_health.watcher.activation_state == "STALE"
    publish_runtime_status(
        factory,
        RuntimeStatusWrite(
            component=WATCHER_COMPONENT,
            worker_id="watcher-new",
            heartbeat_at=now,
            activation_state="running",
        ),
    )
    with factory() as session:
        restarted = load_runtime_rows(session)[WATCHER_COMPONENT]
    live = project_worker_component(restarted, now=now, stale_after_seconds=90)
    restarted_health = _read_worker_runtime(settings, now=now)
    assert live.health_state == "RUNNING"
    assert live.available is True
    assert live.worker_id == "watcher-new"
    assert live.activation_state == "running"
    assert restarted_health.watcher.health_state == "RUNNING"
    assert restarted_health.watcher.available is True
    assert restarted_health.watcher.worker_id == "watcher-new"
    assert restarted_health.watcher.activation_state == "running"


@requires_postgres
def test_postgres_slow_get_heartbeat_blocks_lease_takeover() -> None:
    store = build_postgres_watcher_store(persistence_session_factory())
    clock = FakeClock()
    org = uuid4()
    claimed, lease, _reason = store.claim_lease(
        organization_id=org,
        scan_scope="btc",
        owner_id="worker-a",
        ttl_seconds=5,
        now=clock.now(),
    )
    assert claimed is True
    phase = {"in_get": False, "renewed": 0}

    def hook() -> None:
        if not phase["in_get"]:
            return
        renewed = store.renew_lease(
            organization_id=org,
            scan_scope="btc",
            owner_id="worker-a",
            fencing_token=lease.fencing_token,
            ttl_seconds=30,
            now=clock.now(),
        )
        if renewed:
            phase["renewed"] += 1

    def handler(_request: httpx.Request) -> httpx.Response:
        phase["in_get"] = True
        deadline = time.monotonic() + 2
        while phase["renewed"] < 1:
            if time.monotonic() > deadline:
                raise AssertionError("postgres lease was not renewed during the GET")
            time.sleep(0.01)
        clock.advance(20)
        taken, _held, reason = store.claim_lease(
            organization_id=org,
            scan_scope="btc",
            owner_id="worker-b",
            ttl_seconds=30,
            now=clock.now(),
        )
        assert taken is False
        assert reason == "lease_held"
        return httpx.Response(200, json={"ok": True})

    token = bind_market_request_progress(hook)
    try:
        client = ReadOnlyHttpGetClient(
            base_url="https://fapi.binance.com",
            timeout_seconds=2.0,
            transport=httpx.MockTransport(handler),
            progress_interval_seconds=0.05,
        )
        assert client.get_json("/fapi/v1/ping") == {"ok": True}
        client.close()
    finally:
        reset_market_request_progress(token)
    clock.advance(31)
    taken, taken_lease, reason = store.claim_lease(
        organization_id=org,
        scan_scope="btc",
        owner_id="worker-b",
        ttl_seconds=30,
        now=clock.now(),
    )
    assert taken is True
    assert reason == "claimed"
    assert taken_lease.fencing_token == lease.fencing_token + 1

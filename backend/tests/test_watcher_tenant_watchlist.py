"""PR152 integration regressions: tenant DB authority and real market composition."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.core.errors import ConflictError
from app.db.base import Base
from app.db.models import Organization
from app.db.session import get_session
from app.db.watcher_watchlist import WatcherSymbolStatusRow
from app.main import create_app
from app.market_contracts.errors import StaleEvidenceError, WrongInstrumentError
from app.market_contracts.provider_contracts import ContractBook
from app.repositories.watcher_watchlist import WatcherWatchlistRepository
from app.signal_fusion.lifecycle import CandidateLifecycleService
from app.signal_fusion.memory import InMemoryCandidateRepository
from app.watcher.fusion_evaluation import BoundEvaluationClock
from app.watcher.memory import InMemoryWatcherStore
from app.workers.watcher_market import ContractUnavailableError, SymbolMarketFactory
from app.workers.watcher_paper import build_watcher_paper_runtime
from app.workers.watcher_paper_targets import PaperScanTarget
from app.workers.watcher_watchlist import DEFAULT_WATCHLIST_SYMBOLS, SymbolStatusBook

ORG = UUID(int=101)
OTHER = UUID(int=102)


def settings(**kwargs):
    return Settings(
        _env_file=None,
        environment="local",
        execution_mode="paper",
        enable_real_trading=False,
        real_trading_enabled=False,
        database_url="sqlite+pysqlite:///:memory:",
        rate_limit_use_redis=False,
        access_token_denylist_use_redis=False,
        market_data_cache_use_redis=False,
        watcher_orchestration_enabled=False,
        perpetual_evidence_source=kwargs.pop("perpetual_evidence_source", "binance_usdm"),
        binance_request_max_retries=0,
        **kwargs,
    )


@pytest.fixture
def db(tmp_path):
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path / 'watchlist.sqlite'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as session:
        session.add_all([Organization(id=ORG, name="A"), Organization(id=OTHER, name="B")])
        session.commit()
    yield factory
    engine.dispose()


class PublicMarket:
    def __init__(self, *, unsupported=(), fail=(), failover=(), stale=False, wrong=False):
        self.calls = []
        self.unsupported, self.fail, self.failover = unsupported, fail, failover
        self.stale, self.wrong = stale, wrong
        self.transport = httpx.MockTransport(self.handle)

    def handle(self, request):
        path, symbol = request.url.path, request.url.params.get("symbol")
        self.calls.append((request.url.host, path, symbol))
        assert request.method == "GET"
        if path.endswith("exchangeInfo"):
            return httpx.Response(
                200,
                json={
                    "futuresType": "U_MARGINED",
                    "symbols": [
                        {
                            "symbol": s,
                            "baseAsset": s[:-4],
                            "quoteAsset": "USDT",
                            "contractType": "PERPETUAL",
                            "status": "TRADING",
                        }
                        for s in (*DEFAULT_WATCHLIST_SYMBOLS, "SOLUSDT")
                        if s not in self.unsupported
                    ],
                },
            )
        if path.endswith("instruments-info"):
            return httpx.Response(
                200,
                json={
                    "retCode": 0,
                    "result": {
                        "category": "linear",
                        "list": [
                            {
                                "symbol": symbol,
                                "baseCoin": symbol[:-4],
                                "quoteCoin": "USDT",
                                "contractType": "LinearPerpetual",
                                "status": "Trading",
                            }
                        ],
                    },
                },
            )
        if path in {"/fapi/v1/klines", "/v5/market/kline"}:
            if symbol in self.fail:
                return httpx.Response(503)
            if symbol in self.failover and path.startswith("/fapi"):
                return httpx.Response(451)
            assert int(request.url.params["limit"]) == 4
            now = datetime.now(UTC)
            end = now.replace(second=0, microsecond=0) - timedelta(minutes=now.minute % 15)
            if self.stale:
                end -= timedelta(minutes=15)
            starts = [end - timedelta(minutes=30), end - timedelta(minutes=15)]
            if path.startswith("/fapi"):
                rows = [
                    [
                        int(t.timestamp() * 1000),
                        "10",
                        "12",
                        "9",
                        "11",
                        "100",
                        int((t + timedelta(minutes=15)).timestamp() * 1000) - 1,
                        "1100",
                        10,
                        "50",
                        "550",
                        "0",
                    ]
                    for t in starts
                ]
                return httpx.Response(200, json=rows)
            rows = [
                [str(int(t.timestamp() * 1000)), "10", "12", "9", "11", "100", "1100"]
                for t in starts
            ]
            return httpx.Response(
                200,
                json={
                    "retCode": 0,
                    "result": {
                        "category": "linear",
                        "symbol": "BTCUSDT" if self.wrong else symbol,
                        "list": rows,
                    },
                },
            )
        raise AssertionError(f"Unexpected market request: {path}")


def runtime(db, market, *, enabled=True, source="binance_usdm", secondary="", target_loader=None):
    cfg = settings(perpetual_evidence_source=source, perpetual_evidence_secondary_source=secondary)
    factory = SymbolMarketFactory(cfg, transport=market.transport)
    candidates = InMemoryCandidateRepository()
    worker = build_watcher_paper_runtime(
        cfg,
        db,
        store=InMemoryWatcherStore(),
        lifecycle=CandidateLifecycleService(repository=candidates, clock=BoundEvaluationClock()),
        evidence_factory=factory,
        target_loader=target_loader,
        kill_switch_probe=lambda _org: False,
        enabled=enabled,
    )
    return worker, factory, candidates


def test_database_revision_restart_and_stale_worker_fence(db):
    with db() as session:
        repo = WatcherWatchlistRepository(session)
        original = repo.load(ORG)
        new = repo.replace(ORG, [("ETHUSDT", True), ("BTCUSDT", False)], expected_revision=0)
        session.commit()
    with db() as restarted:
        repo = WatcherWatchlistRepository(restarted)
        assert repo.load(ORG) == new
        assert repo.load(OTHER) == original
        with pytest.raises(ConflictError):
            repo.replace(ORG, [("SOLUSDT", True)], expected_revision=0)
        assert not repo.publish(ORG, original, (), observed_at=datetime.now(UTC))
        assert repo.load(ORG).revision == 1


@pytest.mark.parametrize("source", ["binance_usdm", "bybit_usdt_perpetual"])
def test_normal_production_composition_probes_all_five_without_candidates(db, source):
    market = PublicMarket()
    worker, factory, candidates = runtime(db, market, source=source)
    report = worker.run_cycle()
    assert report.reason_code == "completed" and report.candidates_created == 0
    assert not report.scans  # probes never become strategy/candidate scans
    assert candidates.list_for_organization(ORG) == ((), 0)
    with db() as session:
        config, rows = WatcherWatchlistRepository(session).status(
            ORG, source_mode=source, now=datetime.now(UTC), max_age_seconds=90
        )
        assert {r["symbol"] for r in rows} == set(DEFAULT_WATCHLIST_SYMBOLS)
        assert all(
            r["last_successful_scan"] and r["freshness"] == "fresh_closed_candle" for r in rows
        )
        assert all(r["configuration_revision"] == config.revision for r in rows)
        assert all(r["strategy_matches"] == [] and r["alert_state"] == "none" for r in rows)
        _, other = WatcherWatchlistRepository(session).status(
            OTHER, source_mode=source, now=datetime.now(UTC), max_age_seconds=90
        )
        assert all(r["last_successful_scan"] is None for r in other)
    assert len(factory._entries) == 5 and len(worker.history.completed) == 5
    assert worker.history.peak_in_flight == 1
    assert len([c for c in market.calls if c[1].endswith(("klines", "kline"))]) == 5


def test_worker_refreshes_same_database_and_replacement_evicts_state(db):
    market = PublicMarket()
    worker, factory, _ = runtime(db, market)
    worker.run_cycle()
    with db() as session:
        repo = WatcherWatchlistRepository(session)
        repo.replace(ORG, [("SOLUSDT", True), ("BTCUSDT", False)], expected_revision=0)
        session.commit()
    worker.run_cycle()  # other organization
    before = len(market.calls)
    worker.run_cycle()  # first organization, new revision
    assert {s for _, path, s in market.calls[before:] if path.endswith("klines")} == {"SOLUSDT"}
    assert set(factory._entries) == {"SOLUSDT"}
    with db() as session:
        rows = list(
            session.scalars(
                select(WatcherSymbolStatusRow).where(WatcherSymbolStatusRow.organization_id == ORG)
            )
        )
        assert {r.symbol for r in rows} == {"SOLUSDT", "BTCUSDT"}
        assert all(r.configuration_revision == 1 for r in rows)
    restarted, _, _ = runtime(db, market)
    restarted.run_cycle()
    assert restarted.snapshot().symbols == ("SOLUSDT",)


def test_explicit_unsupported_never_reaches_factory_or_evaluator(db, monkeypatch):
    from app.workers import watcher_paper

    market = PublicMarket(unsupported={"ETHUSDT"})
    target = PaperScanTarget(ORG, uuid4(), uuid4(), uuid4(), uuid4(), "a" * 64, "v1", "ETHUSDT")
    worker, factory, _ = runtime(db, market, target_loader=lambda _s: (target,))

    def forbidden(*args, **kwargs):
        pytest.fail("Unsupported symbol reached evaluator")

    monkeypatch.setattr(watcher_paper, "build_fusion_evaluation_service", forbidden)
    report = worker.run_cycle()
    assert report.scans[0].reason_code == "unsupported_contract"
    assert "ETHUSDT" not in factory._entries
    assert not any(s == "ETHUSDT" and p.endswith("klines") for _, p, s in market.calls)
    row = next(r for r in worker.symbol_status.snapshot() if r.symbol == "ETHUSDT")
    assert row.error_state == "unsupported_contract" and row.last_successful_scan is None


@pytest.mark.parametrize("enabled,refused", [(False, False), (True, True)])
def test_disabled_and_refused_never_advance_success(db, enabled, refused):
    market = PublicMarket()
    worker, _, _ = runtime(db, market, enabled=enabled)
    if refused:
        worker._activation_gate = lambda: "activation_refused"
    worker.run_cycle()
    assert not any(p.endswith(("klines", "kline")) for _, p, _ in market.calls)
    assert all(r.last_successful_scan is None for r in worker.symbol_status.snapshot())


def test_kill_switch_blocks_read_only_probes_without_mutation(db):
    market = PublicMarket()
    worker, _, _ = runtime(db, market)
    worker._kill_switch_probe = lambda _org: True
    worker.run_cycle()
    assert not any(p.endswith("klines") for _, p, _ in market.calls)
    assert all(
        r.error_state == "kill_switch_active" and r.last_successful_scan is None
        for r in worker.symbol_status.snapshot()
    )


def test_one_market_failure_does_not_block_other_symbols(db):
    market = PublicMarket(fail={"ETHUSDT"})
    worker, _, _ = runtime(db, market)
    worker.run_cycle()
    rows = {r.symbol: r for r in worker.symbol_status.snapshot()}
    assert rows["ETHUSDT"].error_state == "provider_unreachable"
    assert rows["ETHUSDT"].last_successful_scan is None
    assert all(rows[s].last_successful_scan for s in DEFAULT_WATCHLIST_SYMBOLS if s != "ETHUSDT")


def test_symbol_specific_failover_and_wrong_instrument(db):
    market = PublicMarket(failover={"ETHUSDT"})
    worker, factory, _ = runtime(db, market, secondary="bybit_usdt_perpetual")
    worker.run_cycle()
    eth, _, _, _ = factory.composition("ETHUSDT")
    btc, _, _, _ = factory.composition("BTCUSDT")
    assert eth.using_secondary and not btc.using_secondary
    assert eth.active_instrument().provider_symbol == "ETHUSDT"
    rows = {r.symbol: r for r in worker.symbol_status.snapshot()}
    assert rows["ETHUSDT"].market_source == "bybit-usdt-perpetual"
    assert rows["BTCUSDT"].market_source == "binance-usdm-perpetual"
    market.wrong = True
    with pytest.raises(WrongInstrumentError):
        factory.probe("ETHUSDT")


def test_stale_probe_cannot_report_success():
    market = PublicMarket(stale=True)
    factory = SymbolMarketFactory(settings(), transport=market.transport)
    factory.discovery(ContractBook(()), ["ETHUSDT"])
    with pytest.raises(StaleEvidenceError):
        factory.probe("ETHUSDT")


def test_discovery_unreachable_is_not_unsupported_and_retries():
    now = [0.0]
    market = PublicMarket()
    failed = [True]

    def handler(request):
        return httpx.Response(503) if failed[0] else market.handle(request)

    factory = SymbolMarketFactory(settings(), transport=httpx.MockTransport(handler))
    factory.discovery.clock = lambda: now[0]
    factory.discovery(ContractBook(()), ["ETHUSDT"])
    with pytest.raises(ContractUnavailableError, match="provider_unreachable"):
        factory.composition("ETHUSDT")
    failed[0], now[0] = False, 61.0
    factory.discovery(ContractBook(()), ["ETHUSDT"])
    assert factory.probe("ETHUSDT").symbol == "ETHUSDT"


def test_old_revision_and_stale_status_are_pending(db):
    now = datetime.now(UTC)
    with db() as session:
        repo = WatcherWatchlistRepository(session)
        cfg = repo.load(ORG)
        book = SymbolStatusBook()
        rows = book.project(cfg, source_mode="binance_usdm")
        repo.publish(ORG, cfg, rows, observed_at=now - timedelta(seconds=100))
        session.commit()
    with db() as session:
        repo = WatcherWatchlistRepository(session)
        _, rows = repo.status(ORG, source_mode="binance_usdm", now=now, max_age_seconds=90)
        assert all(row["observed_at"] is None for row in rows)
        repo.replace(ORG, [("BTCUSDT", True)], expected_revision=0)
        session.commit()
        _, rows = repo.status(ORG, source_mode="binance_usdm", now=now, max_age_seconds=1000)
        assert rows[0]["setup_state"] == "pending" and rows[0]["observed_at"] is None


def test_authenticated_api_enforces_organization_configuration_and_status(db):
    cfg = settings(perpetual_evidence_source="replay")
    app = create_app(settings=cfg)

    def session():
        with db() as value:
            yield value

    app.dependency_overrides[get_session] = session
    with TestClient(app) as client:
        assert client.get("/watcher/watchlist").status_code == 401
        accounts = []
        for name in ("tenant-one", "tenant-two"):
            registered = client.post(
                "/auth/register",
                json={
                    "email": f"{name}@test.example",
                    "password": "secure-password-1",
                    "organization_name": name,
                },
            )
            assert registered.status_code == 201, registered.text
            accounts.append(
                {"Authorization": "Bearer " + registered.json()["tokens"]["access_token"]}
            )
        a, b = accounts
        saved = client.put(
            "/watcher/watchlist",
            headers=a,
            json={"revision": 0, "slots": [{"symbol": "SOLUSDT", "enabled": True}]},
        )
        assert saved.status_code == 200, saved.text
        assert client.get("/watcher/watchlist", headers=a).json()["slots"][0]["symbol"] == "SOLUSDT"
        assert client.get("/watcher/watchlist", headers=b).json()["revision"] == 0
        assert (
            client.put(
                "/watcher/watchlist",
                headers=b,
                json={"revision": 0, "slots": [], "organization_id": str(ORG)},
            ).status_code
            == 422
        )
        with db() as session:
            org = session.scalar(select(Organization.id).where(Organization.name == "tenant-one"))
            repo = WatcherWatchlistRepository(session)
            config = repo.load(org)
            book = SymbolStatusBook()
            book.project(config, source_mode="binance_usdm")
            book.record_scan(
                symbol="SOLUSDT",
                succeeded=True,
                setup_state="candidate",
                freshness="fresh",
                strategy_matches=["private-tenant-a-strategy"],
                alert_state="paper_candidate",
                error_state=None,
                scanned_at=datetime.now(UTC),
            )
            repo.publish(
                org,
                config,
                book.snapshot(),
                observed_at=datetime.now(UTC),
                runtime={
                    "candidates_created": 7,
                    "scopes": [
                        {
                            "scan_scope": "private-tenant-a-strategy",
                            "symbol": "SOLUSDT",
                            "health_state": "succeeded",
                            "last_reason_code": "completed",
                            "candidate_ids": ["private-candidate-a"],
                        }
                    ],
                },
            )
            session.commit()
        assert (
            "private-tenant-a-strategy" in client.get("/watcher/watchlist/status", headers=a).text
        )
        other = client.get(
            "/watcher/watchlist/status", headers={**b, "X-Organization-ID": str(org)}
        )
        assert other.status_code == 200
        assert "private-tenant-a-strategy" not in other.text and "paper_candidate" not in other.text
        own_runtime = client.get("/watcher/paper-runtime/status", headers=a)
        other_runtime = client.get("/watcher/paper-runtime/status", headers=b)
        assert own_runtime.json()["candidates_created"] == 7
        assert own_runtime.json()["symbols"] == ["SOLUSDT"]
        assert other_runtime.json()["candidates_created"] == 0
        assert "SOLUSDT" not in other_runtime.json()["symbols"]
        assert "private-candidate-a" not in other_runtime.text
        assert "private-tenant-a-strategy" not in other_runtime.text
        assert (
            client.put(
                "/watcher/watchlist", headers=a, json={"revision": 0, "slots": []}
            ).status_code
            == 409
        )
    app.dependency_overrides.clear()


def test_runtime_summary_is_shared_tenant_scoped_and_freshness_fenced(db):
    worker, factory, _ = runtime(db, PublicMarket())
    for _ in range(6):
        worker.run_cycle()
    with db() as session:
        repo = WatcherWatchlistRepository(session)
        now = datetime.now(UTC)
        own = repo.runtime_status(ORG, now=now, max_age_seconds=90)
        other = repo.runtime_status(OTHER, now=now, max_age_seconds=90)
        assert own["cycles_completed"] == other["cycles_completed"] == 3
        assert own["candidates_created"] == other["candidates_created"] == 0
        assert repo.runtime_status(ORG, now=now + timedelta(seconds=91), max_age_seconds=90) is None
        repo.replace(ORG, [("BTCUSDT", True)], expected_revision=0)
        session.commit()
        assert repo.runtime_status(ORG, now=now, max_age_seconds=90) is None
        assert repo.runtime_status(OTHER, now=now, max_age_seconds=90) is not None
        assert len(list(session.scalars(select(WatcherSymbolStatusRow)))) == 6
    assert len(factory._entries) <= 5
    assert len(factory.discovery._cache) <= 10
    assert len(factory._reads) <= 5
    assert len(worker.history.completed) == 5 and worker.history.held_symbol is None
    assert worker.history.peak_in_flight == 1


def test_noop_without_probe_and_empty_config_cannot_advance_scan_success(db):
    market = PublicMarket()
    worker, _, _ = runtime(db, market)
    worker._symbol_probe = None
    assert worker.run_cycle().reason_code == "idle"
    assert all(row.last_successful_scan is None for row in worker.symbol_status.snapshot())
    with db() as session:
        WatcherWatchlistRepository(session).replace(ORG, [], expected_revision=0)
        session.commit()
    worker.run_cycle()
    assert worker.run_cycle().reason_code == "idle"
    assert worker.symbol_status.snapshot() == ()
    assert not any(p.endswith(("klines", "kline")) for _, p, _ in market.calls)


def test_unverified_secondary_never_reads_market():
    market = PublicMarket(failover={"ETHUSDT"})

    def handle(request):
        if request.url.path.endswith("instruments-info"):
            return httpx.Response(
                200, json={"retCode": 0, "result": {"category": "linear", "list": []}}
            )
        return market.handle(request)

    factory = SymbolMarketFactory(
        settings(perpetual_evidence_secondary_source="bybit_usdt_perpetual"),
        transport=httpx.MockTransport(handle),
    )
    factory.discovery(ContractBook(()), ["ETHUSDT"])
    with pytest.raises(ContractUnavailableError, match="unsupported_contract"):
        factory.probe("ETHUSDT")
    assert not any(path.endswith("/kline") for _, path, _ in market.calls)


def test_mixed_strategy_and_probe_work_follow_configured_order(db, monkeypatch):
    from app.workers.watcher_paper import WatcherPaperScanReport

    market = PublicMarket()
    target = PaperScanTarget(ORG, uuid4(), uuid4(), uuid4(), uuid4(), "a" * 64, "v1", "ETHUSDT")
    worker, factory, _ = runtime(db, market, target_loader=lambda _s: (target,))
    order = []
    original = factory.probe
    worker._symbol_probe = lambda symbol: (order.append(symbol), original(symbol))[1]

    def scan(session, selected):
        order.append(selected.symbol)
        return WatcherPaperScanReport(
            organization_id=ORG,
            scan_scope=selected.scan_scope,
            symbol=selected.symbol,
            status="skipped",
            reason_code="no_setup",
            replayed=False,
            published=False,
            candidate_ids=(),
            kill_switch_active=False,
        )

    monkeypatch.setattr(worker, "_scan_one", scan)
    worker.run_cycle()
    assert order == list(DEFAULT_WATCHLIST_SYMBOLS)
    assert (
        next(
            row for row in worker.symbol_status.snapshot() if row.symbol == "ETHUSDT"
        ).last_successful_scan
        is None
    )


@pytest.mark.parametrize("source", ["binance_usdm", "bybit_usdt_perpetual"])
def test_all_five_canonical_evidence_ports_have_their_own_monitor(source):
    market = PublicMarket()
    factory = SymbolMarketFactory(
        settings(perpetual_evidence_source=source), transport=market.transport
    )
    factory.discovery(ContractBook(()), DEFAULT_WATCHLIST_SYMBOLS)
    monitors = []
    for symbol in DEFAULT_WATCHLIST_SYMBOLS:
        evidence = factory(None, InMemoryWatcherStore(), symbol)
        monitor = evidence._monitor._monitor
        assert evidence._symbol == symbol
        assert monitor.enabled_symbols() == (symbol,)
        assert evidence._assembler._source is monitor._source
        monitors.append(monitor)
    assert len({id(monitor) for monitor in monitors}) == 5

"""Configurable Watcher watchlist. Extra symbols stay inactive unless enabled.

The simulated cycle uses BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, and DOGEUSDT.
It does not call Binance or Bybit and does not arm staging.
"""

from __future__ import annotations

import tracemalloc
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.market_contracts.adapters.aggtrade_cache import (
    ClosedAggTradeCache,
    closed_agg_trade_window_key,
)
from app.market_contracts.adapters.symbol_failover import PerSymbolFailoverSource
from app.market_contracts.catalog import catalog_for_symbols, default_perpetual_catalog
from app.market_contracts.enums import VenueId
from app.market_contracts.errors import EvidenceSourceSwitchRequiredError, RateLimitedError
from app.market_contracts.first_slice import first_slice_identity
from app.market_contracts.identity import binance_usdm_perpetual, bybit_usdt_perpetual
from app.providers.base import ProviderHealth, ProviderKind, ProviderStatus
from app.schemas.common import Timeframe
from app.watcher.contracts import EvaluationCommand
from app.watcher.fusion_evaluation import WatcherCanonicalScanEvidence
from app.watcher.ports import WatcherStore
from app.workers.watcher_paper_targets import (
    FIRST_SLICE_SYMBOL,
    PaperScanTarget,
    list_paper_scan_targets,
    strategy_version_covers_symbol,
)
from app.workers.watcher_watchlist import (
    WATCHLIST_SYMBOL_CAP,
    effective_watch_symbols,
    resolve_watchlist,
)
from tests.support.phase6_evaluator import make_world
from tests.test_watcher_paper_runtime import (
    ORG,
    ORG_B,
    _runtime,
    _seed_approved_compiled,
    _settings,
    _sqlite_factory,
    _world_factory,
)

SIMULATED_WATCHLIST = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT")
ROOT = Path(__file__).resolve().parents[2]
WINDOW_BYTES = 64 * 1024


@pytest.fixture
def session_factory() -> Iterator[sessionmaker[Session]]:
    from app.db.models import Membership, Organization, User
    from app.schemas.common import MembershipRole
    from tests.test_watcher_paper_runtime import USER, USER_B

    factory = _sqlite_factory()
    with factory() as db:
        db.add_all(
            [
                Organization(id=ORG, name="AT069 Org A"),
                Organization(id=ORG_B, name="AT069 Org B"),
                User(id=USER, email="at069-a@test.example", hashed_password="not-a-real-hash"),
                User(id=USER_B, email="at069-b@test.example", hashed_password="not-a-real-hash"),
            ]
        )
        db.flush()
        db.add_all(
            [
                Membership(organization_id=ORG, user_id=USER, role=MembershipRole.TRADER),
                Membership(organization_id=ORG_B, user_id=USER_B, role=MembershipRole.TRADER),
            ]
        )
        db.commit()
    yield factory


def test_multi_symbol_stays_inactive_until_explicitly_enabled() -> None:
    configured = ",".join(SIMULATED_WATCHLIST)
    inactive = _settings(watcher_paper_symbols=configured, watcher_multi_symbol_enabled=False)
    assert inactive.watcher_multi_symbol_enabled is False
    assert effective_watch_symbols(inactive) == (FIRST_SLICE_SYMBOL,)
    assert resolve_watchlist(inactive).activation == "btc_only"

    active = _settings(watcher_paper_symbols=configured, watcher_multi_symbol_enabled=True)
    assert effective_watch_symbols(active) == SIMULATED_WATCHLIST
    removed = _settings(
        watcher_paper_symbols="BTCUSDT,ETHUSDT,XRPUSDT,DOGEUSDT",
        watcher_multi_symbol_enabled=True,
    )
    assert "SOLUSDT" not in effective_watch_symbols(removed)
    assert effective_watch_symbols(removed)[0] == "BTCUSDT"


def test_invalid_symbols_do_not_block_the_valid_watchlist() -> None:
    settings = _settings(
        watcher_paper_symbols="BTCUSDT,ETH-USD,SOLUSDT",
        watcher_multi_symbol_enabled=True,
    )
    resolution = resolve_watchlist(settings)
    assert resolution.active == ("BTCUSDT", "SOLUSDT")
    assert "ETH-USD" in resolution.rejected


def test_watchlist_cap_bounds_active_symbols() -> None:
    extras = (
        "ETHUSDT",
        "SOLUSDT",
        "XRPUSDT",
        "DOGEUSDT",
        "ADAUSDT",
        "BNBUSDT",
        "LINKUSDT",
        "AVAXUSDT",
        "DOTUSDT",
        "LTCUSDT",
        "BCHUSDT",
    )
    settings = _settings(
        watcher_paper_symbols=list(extras),
        watcher_multi_symbol_enabled=True,
        watcher_paper_max_symbols=WATCHLIST_SYMBOL_CAP,
    )
    active = effective_watch_symbols(settings)
    assert len(active) == WATCHLIST_SYMBOL_CAP
    assert active[0] == "BTCUSDT"
    assert "BCHUSDT" not in active
    with pytest.raises(ValueError):
        Settings(
            environment="local",
            jwt_secret="x" * 32,
            database_url="sqlite+pysqlite:///:memory:",
            watcher_paper_max_symbols=11,
        )


def test_default_catalog_stays_btcusdt_while_a_copy_can_list_the_watchlist() -> None:
    assert default_perpetual_catalog().enabled_symbols() == ("BTCUSDT",)
    catalog = catalog_for_symbols(SIMULATED_WATCHLIST, venue=VenueId.BINANCE)
    assert catalog.enabled_symbols() == tuple(sorted(SIMULATED_WATCHLIST))
    bybit = catalog_for_symbols(("ETHUSDT",), venue=VenueId.BYBIT)
    assert bybit.require("ETHUSDT").venue is VenueId.BYBIT
    assert bybit_usdt_perpetual("ETHUSDT").provider_symbol == "ETHUSDT"


def test_render_does_not_activate_additional_symbols() -> None:
    render = (ROOT / "render.yaml").read_text(encoding="utf-8")
    staging = (ROOT / ".env.staging.example").read_text(encoding="utf-8")
    assert "WATCHER_MULTI_SYMBOL_ENABLED" not in render
    assert "ETHUSDT" not in render
    assert "\nWATCHER_MULTI_SYMBOL_ENABLED=false\n" in staging
    assert "ETHUSDT=" not in staging


def test_btc_strategy_does_not_load_other_symbols(
    session_factory: sessionmaker[Session],
) -> None:
    assert strategy_version_covers_symbol({"asset_universe": ["BTCUSDT"]}, "ETHUSDT") is False
    assert strategy_version_covers_symbol({"asset_universe": ["BTCUSDT"]}, "BTCUSDT") is True
    assert strategy_version_covers_symbol({}, "ETHUSDT") is True
    with session_factory() as session:
        _seed_approved_compiled(session)
        targets = list_paper_scan_targets(
            session,
            symbols=list(SIMULATED_WATCHLIST),
            organization_id=ORG,
            limit=20,
        )
    assert tuple(item.symbol for item in targets) == ("BTCUSDT",)
    loaded: list[str] = []

    def factory(_session: Session | None, _store: WatcherStore, symbol: str) -> _HoldingPort:
        loaded.append(symbol)
        return _HoldingPort(symbol, source="binance-usdm-perpetual", freshness="fresh")

    runtime, _clock, probe, _store = _runtime(
        session_factory,
        evidence_factory=factory,
        target_loader=lambda _session: targets,
        symbols=SIMULATED_WATCHLIST,
        bind_session=False,
        kill_switch_probe=lambda _org: False,
    )
    report = runtime.run_cycle()
    assert [item.symbol for item in report.scans] == ["BTCUSDT"]
    assert loaded == ["BTCUSDT"]
    assert runtime.history_budget.peak_in_flight == 1
    assert runtime.history_budget.completed == ["BTCUSDT"]
    statuses = {item.symbol: item for item in runtime.symbol_statuses_for(ORG)}
    assert statuses["ETHUSDT"].scan_status == "no_strategy"
    assert statuses["SOLUSDT"].strategy_candidate_ids == ()
    assert statuses["DOGEUSDT"].last_failure_reason is None
    assert probe.unused is True
    assert _HoldingPort.live == 0


def test_simulated_watchlist_isolates_failures_and_bounds_memory(
    session_factory: sessionmaker[Session],
) -> None:
    world_factory = _world_factory(make_world())
    with session_factory() as session:
        _seed_approved_compiled(session)
        seeded = list_paper_scan_targets(session, symbols=["BTCUSDT"], organization_id=ORG, limit=1)
    assert seeded
    base = seeded[0]
    targets = tuple(_retarget(base, symbol) for symbol in SIMULATED_WATCHLIST)
    _HoldingPort.reset()

    def factory(session: Session | None, store: WatcherStore, symbol: str) -> object:
        if symbol == "BTCUSDT":
            port = world_factory(session, store, symbol)
            return _Windowed(port, symbol, source="binance-usdm-perpetual", freshness="fresh")
        if symbol == "SOLUSDT":
            return _HoldingPort(
                symbol,
                source="binance-usdm-perpetual",
                freshness="unavailable",
                fail=True,
            )
        return _HoldingPort(symbol, source="binance-usdm-perpetual", freshness="stale")

    runtime, _clock, probe, _store = _runtime(
        session_factory,
        evidence_factory=factory,
        target_loader=lambda _session: targets,
        symbols=SIMULATED_WATCHLIST,
        kill_switch_probe=lambda _org: False,
    )
    tracemalloc.start()
    report = runtime.run_cycle()
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    by_symbol = {item.symbol: item for item in report.scans}
    assert tuple(by_symbol) == SIMULATED_WATCHLIST
    assert by_symbol["BTCUSDT"].status == "succeeded"
    assert len(by_symbol["BTCUSDT"].candidate_ids) == 1
    assert by_symbol["SOLUSDT"].status == "failed"
    assert by_symbol["SOLUSDT"].reason_code == "canonical_evidence_unavailable"
    assert by_symbol["ETHUSDT"].status == "failed"
    assert by_symbol["ETHUSDT"].reason_code == "missing_canonical_evidence"
    assert by_symbol["XRPUSDT"].reason_code == "missing_canonical_evidence"
    assert by_symbol["DOGEUSDT"].reason_code == "missing_canonical_evidence"
    assert runtime.history_budget.peak_in_flight == 1
    assert runtime.history_budget.rejected_overlaps == 0
    assert runtime.history_budget.completed == list(SIMULATED_WATCHLIST)
    assert _HoldingPort.peak == 1
    assert _HoldingPort.live == 0

    own = {item.symbol: item for item in runtime.symbol_statuses_for(ORG)}
    assert own["BTCUSDT"].source == "binance-usdm-perpetual"
    assert own["BTCUSDT"].freshness == "fresh"
    assert own["BTCUSDT"].last_successful_scan_at is not None
    assert own["BTCUSDT"].strategy_candidate_ids == (str(by_symbol["BTCUSDT"].candidate_ids[0]),)
    assert own["SOLUSDT"].scan_status == "failed"
    assert own["SOLUSDT"].freshness == "unavailable"
    assert own["SOLUSDT"].last_failure_reason == "canonical_evidence_unavailable"
    assert own["SOLUSDT"].strategy_candidate_ids == ()
    assert own["ETHUSDT"].freshness == "stale"
    assert own["ETHUSDT"].last_successful_scan_at is None
    foreign = runtime.symbol_statuses_for(ORG_B)
    assert all(item.scan_status == "not_scanned" for item in foreign)
    assert all(item.strategy_candidate_ids == () for item in foreign)
    assert probe.execution == []
    assert probe.unused is True
    # One 64KiB window at a time, plus the BTC evidence fixture. Five live windows
    # would be well above this ceiling.
    assert peak < 8 * 1024 * 1024, f"traced peak bytes={peak}"


def test_per_symbol_failover_leaves_healthy_symbols_on_binance() -> None:
    primary = _Primary()
    created: list[str] = []

    def secondary_factory(symbol: str) -> _Secondary:
        created.append(symbol)
        return _Secondary(symbol)

    router = PerSymbolFailoverSource(
        primary,
        symbols=SIMULATED_WATCHLIST,
        primary_instrument_for=lambda symbol: binance_usdm_perpetual(symbol),
        secondary_instrument_for=bybit_usdt_perpetual,
        secondary_factory=secondary_factory,
    )
    btc = binance_usdm_perpetual("BTCUSDT")
    eth = binance_usdm_perpetual("ETHUSDT")
    evaluated = datetime(2026, 1, 15, 16, 15, tzinfo=UTC)
    assert (
        router.fetch_closed_ohlcv(
            identity=_live_identity(btc),
            instrument=btc,
            timeframe=Timeframe.M15,
            min_final_bars=1,
            evaluated_at=evaluated,
        )
        == "BTCUSDT"
    )
    with pytest.raises(EvidenceSourceSwitchRequiredError) as switched:
        router.fetch_closed_ohlcv(
            identity=_live_identity(eth),
            instrument=eth,
            timeframe=Timeframe.M15,
            min_final_bars=1,
            evaluated_at=evaluated,
        )
    assert switched.value.instrument == bybit_usdt_perpetual("ETHUSDT")
    assert router.using_secondary("ETHUSDT") is True
    assert router.using_secondary("BTCUSDT") is False
    assert created == []
    eth_bybit = bybit_usdt_perpetual("ETHUSDT")
    assert (
        router.fetch_closed_ohlcv(
            identity=_live_identity(eth_bybit),
            instrument=eth_bybit,
            timeframe=Timeframe.M15,
            min_final_bars=1,
            evaluated_at=evaluated,
        )
        == "bybit:ETHUSDT"
    )
    assert created == ["ETHUSDT"]
    assert (
        router.fetch_closed_ohlcv(
            identity=_live_identity(btc),
            instrument=btc,
            timeframe=Timeframe.M15,
            min_final_bars=1,
            evaluated_at=evaluated,
        )
        == "BTCUSDT"
    )
    assert router.status().using_fallback is True
    assert "ETHUSDT" in (router.status().detail or "")
    assert "BTCUSDT" not in (router.status().detail or "")
    recovered = router.try_recover_primary("ETHUSDT")
    assert recovered is not None
    assert recovered.provider_symbol == "ETHUSDT"
    assert recovered.venue is VenueId.BINANCE
    assert router.using_secondary("ETHUSDT") is False


def test_shared_aggtrade_cache_evicts_oldest_symbol_windows() -> None:
    """Five symbols with two closed windows exceed the shared 8-entry cache.

    The cache key includes the symbol. Entries are not loaded together: this
    measures the existing bound the memory work has to reconcile with.
    """

    cache = ClosedAggTradeCache(max_entries=8, ttl_seconds=120, clock=lambda: 0.0)
    start = datetime(2026, 1, 15, 16, 0, tzinfo=UTC)
    first_end = datetime(2026, 1, 15, 16, 15, tzinfo=UTC)
    second_end = datetime(2026, 1, 15, 16, 30, tzinfo=UTC)
    row = ({"a": 1, "p": "1", "q": "1", "T": 1, "m": False},)
    for symbol in SIMULATED_WATCHLIST:
        cache.put(closed_agg_trade_window_key(symbol, start, first_end), row)
        cache.put(closed_agg_trade_window_key(symbol, start, second_end), row)
    assert len(cache) == 8
    assert cache.get(closed_agg_trade_window_key("BTCUSDT", start, first_end)) is None
    assert cache.get(closed_agg_trade_window_key("BTCUSDT", start, second_end)) is None
    assert cache.get(closed_agg_trade_window_key("ETHUSDT", start, first_end)) is not None
    assert cache.get(closed_agg_trade_window_key("DOGEUSDT", start, second_end)) is not None


def _retarget(base: PaperScanTarget, symbol: str) -> PaperScanTarget:
    return PaperScanTarget(
        organization_id=base.organization_id,
        user_id=base.user_id,
        strategy_id=base.strategy_id,
        strategy_version_id=base.strategy_version_id,
        compiled_setup_definition_id=base.compiled_setup_definition_id,
        compiled_content_hash=base.compiled_content_hash,
        fusion_policy_version=base.fusion_policy_version,
        symbol=symbol,
        timeframe=base.timeframe,
    )


def _live_identity(instrument: object) -> object:
    return first_slice_identity(
        timeframe=Timeframe.M15,
        replay=False,
        is_live=True,
        instrument=instrument,  # type: ignore[arg-type]
    )


class _HoldingPort:
    live = 0
    peak = 0

    def __init__(
        self,
        symbol: str,
        *,
        source: str,
        freshness: str,
        fail: bool = False,
    ) -> None:
        self.symbol = symbol
        self._source = source
        self._freshness = freshness
        self._fail = fail
        self._window: bytearray | None = bytearray(WINDOW_BYTES)
        type(self).live += 1
        type(self).peak = max(type(self).peak, type(self).live)

    @classmethod
    def reset(cls) -> None:
        cls.live = 0
        cls.peak = 0

    def load(self, _command: EvaluationCommand) -> WatcherCanonicalScanEvidence | None:
        if self._fail:
            raise RuntimeError(f"{self.symbol} simulated provider failure")
        return None

    def symbol_observation(self) -> tuple[str, str, float]:
        return (self._source, self._freshness, 4.0)

    def release_historical_window(self) -> None:
        if self._window is not None:
            self._window = None
            type(self).live -= 1


class _Windowed:
    """BTC evidence port plus one releasable historical window."""

    def __init__(self, inner: object, symbol: str, *, source: str, freshness: str) -> None:
        self._inner = inner
        self.symbol = symbol
        self._source = source
        self._freshness = freshness
        self._window: bytearray | None = bytearray(WINDOW_BYTES)
        _HoldingPort.live += 1
        _HoldingPort.peak = max(_HoldingPort.peak, _HoldingPort.live)

    def load(self, command: EvaluationCommand) -> WatcherCanonicalScanEvidence | None:
        return self._inner.load(command)  # type: ignore[no-any-return]

    def symbol_observation(self) -> tuple[str, str, float]:
        return (self._source, self._freshness, 1.0)

    def release_historical_window(self) -> None:
        if self._window is not None:
            self._window = None
            _HoldingPort.live -= 1
        release = getattr(self._inner, "release_historical_window", None)
        if callable(release):
            release()


class _Primary:
    name = "binance-usdm-perpetual"
    kind = ProviderKind.MARKET_DATA

    def __init__(self) -> None:
        self.calls: list[str] = []

    def fetch_closed_ohlcv(
        self,
        *,
        identity: object,
        instrument: object,
        timeframe: Timeframe,
        min_final_bars: int,
        evaluated_at: datetime,
    ) -> str:
        del identity, timeframe, min_final_bars, evaluated_at
        symbol = str(instrument.provider_symbol)
        self.calls.append(symbol)
        if symbol == "ETHUSDT":
            raise RateLimitedError("simulated ETH rate limit", retry_after_seconds=1)
        return symbol

    def fetch_ordered_trades(self, **_kwargs: object) -> str:
        raise AssertionError("trade history was not requested")

    def status(self) -> ProviderStatus:
        return ProviderStatus(
            name=self.name,
            kind=self.kind,
            health=ProviderHealth.HEALTHY,
            using_fallback=False,
            is_mock=False,
        )


class _Secondary:
    kind = ProviderKind.MARKET_DATA

    def __init__(self, symbol: str) -> None:
        self.name = "bybit-usdt-perpetual"
        self.symbol = symbol

    def fetch_closed_ohlcv(
        self,
        *,
        identity: object,
        instrument: object,
        timeframe: Timeframe,
        min_final_bars: int,
        evaluated_at: datetime,
    ) -> str:
        del identity, instrument, timeframe, min_final_bars, evaluated_at
        return f"bybit:{self.symbol}"

    def fetch_ordered_trades(self, **_kwargs: object) -> str:
        raise AssertionError("trade history was not requested")

    def status(self) -> ProviderStatus:
        return ProviderStatus(
            name=self.name,
            kind=self.kind,
            health=ProviderHealth.HEALTHY,
            using_fallback=False,
            is_mock=False,
        )

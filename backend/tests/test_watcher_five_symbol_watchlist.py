"""Configurable five-symbol paper Watcher watchlist."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.core.config import ExecutionMode, Settings
from app.market_contracts.adapters.aggtrade_cache import ClosedAggTradeCache
from app.market_contracts.adapters.bybit_usdt_perpetual import BybitUsdtPerpetualSource
from app.market_contracts.enums import VenueId
from app.market_contracts.errors import WrongInstrumentError
from app.market_contracts.first_slice import first_slice_identity
from app.market_contracts.identity import (
    binance_usdm_btcusdt,
    bybit_usdt_perpetual,
    bybit_usdt_perpetual_btcusdt,
    instrument_matches_requested_symbol,
)
from app.market_contracts.provider_contracts import (
    availability_for_symbol,
    contract_from_binance_exchange_info,
    contract_from_bybit_instruments,
    default_contract_book,
)
from app.schemas.common import Timeframe
from app.signal_fusion.assessment import SetupAssessmentState
from app.signal_fusion.evaluator import evaluate_setup
from app.signal_fusion.lifecycle import CandidateLifecycleService
from app.signal_fusion.memory import InMemoryCandidateRepository
from app.signal_fusion.symbol_strategy_match import (
    SymbolMarketEvidence,
    match_strategy_to_evidence,
)
from app.watcher.fusion_evaluation import BoundEvaluationClock
from app.watcher.memory import FakeClock, InMemoryWatcherStore
from app.workers.watcher_paper import WatcherPaperRuntime
from app.workers.watcher_paper_targets import (
    FIRST_SLICE_SYMBOL,
    PaperScanTarget,
    normalize_paper_symbols,
)
from app.workers.watcher_watchlist import (
    FileWatchlistStore,
    MemoryWatchlistStore,
    SymbolHistoryBudget,
    SymbolScanOutcome,
    WatchlistValidationError,
    default_watchlist,
    reorder_slots,
    replace_symbol,
    replace_watchlist,
    scan_symbols_sequentially,
    set_enabled,
)
from tests.support.phase6_evaluator import make_world
from tests.support.phase6_fusion import eth_evidence_identity

ORG = uuid4()
USER = uuid4()
NOW = datetime(2026, 9, 30, tzinfo=UTC)


def test_default_slots_and_reorder_replace_disable() -> None:
    config = default_watchlist(now=NOW)
    assert tuple(slot.symbol for slot in config.slots) == (
        "BTCUSDT",
        "ZECUSDT",
        "ETHUSDT",
        "TAOUSDT",
        "HYPEUSDT",
    )
    replaced = replace_symbol(config, 2, "solusdt", now=NOW)
    assert replaced.slots[1].symbol == "SOLUSDT"
    assert replaced.slots[0].symbol == "BTCUSDT"
    disabled = set_enabled(replaced, 3, False, now=NOW)
    assert disabled.slots[2].enabled is False
    assert disabled.enabled_symbols() == ("BTCUSDT", "SOLUSDT", "TAOUSDT", "HYPEUSDT")
    ordered = reorder_slots(disabled, (3, 1, 2, 5, 4), now=NOW)
    assert tuple(slot.symbol for slot in ordered.slots) == (
        "ETHUSDT",
        "BTCUSDT",
        "SOLUSDT",
        "HYPEUSDT",
        "TAOUSDT",
    )
    assert ordered.slots[0].enabled is False


def test_maximum_five_slots_and_duplicate_rejection() -> None:
    with pytest.raises(WatchlistValidationError, match="exactly five"):
        replace_watchlist(
            [("BTCUSDT", True), ("ETHUSDT", True)],
            now=NOW,
        )
    with pytest.raises(WatchlistValidationError, match="exactly five"):
        replace_watchlist(
            [
                ("BTCUSDT", True),
                ("ETHUSDT", True),
                ("ZECUSDT", True),
                ("TAOUSDT", True),
                ("HYPEUSDT", True),
                ("SOLUSDT", True),
            ],
            now=NOW,
        )
    with pytest.raises(WatchlistValidationError, match="Duplicate"):
        replace_watchlist(
            [
                ("BTCUSDT", True),
                ("ETHUSDT", True),
                ("btcusdt", True),
                ("TAOUSDT", True),
                ("HYPEUSDT", True),
            ],
            now=NOW,
        )


def test_invalid_symbol_format_is_rejected() -> None:
    config = default_watchlist(now=NOW)
    with pytest.raises(WatchlistValidationError):
        replace_symbol(config, 1, "BTC-USD", now=NOW)
    with pytest.raises(WatchlistValidationError):
        replace_symbol(config, 1, "ETH", now=NOW)


def test_watchlist_persists_without_a_database(tmp_path: object) -> None:
    from pathlib import Path

    path = Path(str(tmp_path)) / "watchlist.json"
    store = FileWatchlistStore(path)
    saved = store.save(replace_symbol(default_watchlist(now=NOW), 5, "SOLUSDT", now=NOW))
    loaded = FileWatchlistStore(path).load()
    assert loaded.slots[4].symbol == "SOLUSDT"
    assert loaded.revision == saved.revision
    memory = MemoryWatchlistStore()
    memory.save(set_enabled(memory.load(), 1, False, now=NOW))
    assert memory.load().slots[0].enabled is False


def test_unsupported_symbol_fails_closed_without_substitution() -> None:
    book = default_contract_book()
    source, error = availability_for_symbol("ETHUSDT", source_mode="binance_usdm", book=book)
    assert source == "unavailable"
    assert error == "contract_unverified"
    btc_source, btc_error = availability_for_symbol(
        "BTCUSDT", source_mode="binance_usdm", book=book
    )
    assert btc_source == "binance_usdm"
    assert btc_error is None
    bybit_source, bybit_error = availability_for_symbol(
        "BTCUSDT", source_mode="bybit_usdt_perpetual", book=book
    )
    assert bybit_source == "bybit_usdt_perpetual"
    assert bybit_error is None
    # A Bybit contract must not satisfy a Binance request for another symbol.
    swapped, swapped_error = availability_for_symbol("ETHUSDT", source_mode="replay", book=book)
    assert swapped == "unavailable"
    assert swapped_error == "contract_unverified"


def test_binance_and_bybit_payloads_keep_provenance_and_reject_substitution() -> None:
    eth = contract_from_binance_exchange_info(
        {
            "symbols": [
                {
                    "symbol": "ETHUSDT",
                    "contractType": "PERPETUAL",
                    "quoteAsset": "USDT",
                    "status": "TRADING",
                    "baseAsset": "ETH",
                }
            ]
        },
        requested_symbol="ETHUSDT",
    )
    assert eth.venue is VenueId.BINANCE
    assert eth.symbol == "ETHUSDT"
    assert eth.source == "binance_usdm"
    with pytest.raises(WrongInstrumentError, match="does not match"):
        contract_from_binance_exchange_info(
            {
                "symbols": [
                    {
                        "symbol": "BTCUSDT",
                        "contractType": "PERPETUAL",
                        "quoteAsset": "USDT",
                        "status": "TRADING",
                    }
                ]
            },
            requested_symbol="ETHUSDT",
        )
    bybit = contract_from_bybit_instruments(
        {
            "retCode": 0,
            "result": {
                "category": "linear",
                "list": [
                    {
                        "symbol": "ETHUSDT",
                        "contractType": "LinearPerpetual",
                        "quoteCoin": "USDT",
                        "status": "Trading",
                    }
                ],
            },
        },
        requested_symbol="ethusdt",
    )
    assert bybit.venue is VenueId.BYBIT
    assert bybit.source == "bybit_usdt_perpetual"
    book = default_contract_book().with_contract(eth).with_contract(bybit)
    source, error = availability_for_symbol("ETHUSDT", source_mode="binance_usdm", book=book)
    assert source == "binance_usdm"
    assert error is None
    bybit_only, bybit_only_error = availability_for_symbol(
        "ETHUSDT", source_mode="bybit_usdt_perpetual", book=book
    )
    assert bybit_only == "bybit_usdt_perpetual"
    assert bybit_only_error is None


def test_bybit_instance_does_not_serve_a_different_symbol() -> None:
    default = BybitUsdtPerpetualSource()
    assert default.active_instrument().instrument_id == bybit_usdt_perpetual_btcusdt().instrument_id
    eth = BybitUsdtPerpetualSource(instrument=bybit_usdt_perpetual("ETHUSDT"))
    assert eth.active_instrument().provider_symbol == "ETHUSDT"
    with pytest.raises(WrongInstrumentError, match="BTCUSDT"):
        default._assert_request(
            _identity_for(bybit_usdt_perpetual("ETHUSDT")),
            bybit_usdt_perpetual("ETHUSDT"),
        )


def test_market_identity_follows_the_requested_symbol_and_btc_stays_btc() -> None:
    btc = _identity_for(binance_usdm_btcusdt())
    eth = eth_evidence_identity()
    bybit_btc = _identity_for(bybit_usdt_perpetual_btcusdt())
    assert instrument_matches_requested_symbol(btc, "BTCUSDT") is True
    assert instrument_matches_requested_symbol(eth, "BTCUSDT") is False
    assert instrument_matches_requested_symbol(eth, "ETHUSDT") is True
    assert instrument_matches_requested_symbol(bybit_btc, "BTCUSDT") is True
    assert instrument_matches_requested_symbol(bybit_btc, "ETHUSDT") is False
    assert instrument_matches_requested_symbol(btc, "BTCUSDT") is True
    world = make_world()
    assessment = evaluate_setup(
        policy=world.policy,
        command=world.command.model_copy(update={"evidence_identity": eth}),
        evidence=world.evidence,
        evaluated_at=world.evaluated_at,
    )
    assert assessment.state is not SetupAssessmentState.CONFIRMED_SETUP
    fresh = evaluate_setup(
        policy=world.policy,
        command=world.command,
        evidence=world.evidence,
        evaluated_at=world.evaluated_at,
    )
    assert fresh.state is SetupAssessmentState.CONFIRMED_SETUP


def test_stale_evidence_does_not_confirm_a_setup() -> None:
    world = make_world(stale_command=True)
    assessment = evaluate_setup(
        policy=world.policy,
        command=world.command,
        evidence=world.evidence,
        evaluated_at=world.evaluated_at + timedelta(seconds=30),
    )
    assert assessment.state is SetupAssessmentState.NO_SETUP
    assert assessment.state is not SetupAssessmentState.CONFIRMED_SETUP


def test_one_symbol_failure_does_not_stop_the_others() -> None:
    seen: list[str] = []

    def evaluate(symbol: str) -> SymbolScanOutcome:
        seen.append(symbol)
        if symbol == "ZECUSDT":
            raise RuntimeError("symbol failed")
        return SymbolScanOutcome(symbol=symbol, status="ok")

    budget = SymbolHistoryBudget()
    outcomes = scan_symbols_sequentially(
        ("BTCUSDT", "ZECUSDT", "ETHUSDT", "TAOUSDT", "HYPEUSDT"),
        evaluate,
        budget,
    )
    assert [item.symbol for item in outcomes] == [
        "BTCUSDT",
        "ZECUSDT",
        "ETHUSDT",
        "TAOUSDT",
        "HYPEUSDT",
    ]
    assert outcomes[1].error == "evaluation_exception"
    assert outcomes[2].status == "ok"
    assert budget.held_symbol is None
    assert budget.peak_in_flight == 1
    assert seen == ["BTCUSDT", "ZECUSDT", "ETHUSDT", "TAOUSDT", "HYPEUSDT"]


def test_runtime_isolates_symbol_failures_and_releases_windows() -> None:
    config = reorder_slots(default_watchlist(now=NOW), (3, 2, 1, 4, 5), now=NOW)
    symbols = config.enabled_symbols()
    called: list[str] = []

    def factory(_session: object, _store: object, symbol: str) -> object:
        called.append(symbol)
        raise RuntimeError(symbol)

    runtime = WatcherPaperRuntime(
        store=InMemoryWatcherStore(),
        lifecycle=CandidateLifecycleService(
            repository=InMemoryCandidateRepository(),
            clock=BoundEvaluationClock(),
        ),
        clock=FakeClock(NOW),
        enabled=True,
        symbols=symbols,
        watchlist_mode=True,
        watchlist=config,
        watchlist_store=MemoryWatchlistStore(config),
        target_loader=lambda _session: tuple(_target(symbol) for symbol in symbols),
        evidence_factory=factory,  # type: ignore[arg-type]
        kill_switch_probe=lambda _org: False,
        settings=Settings(),
    )
    report = runtime.run_cycle()
    assert [scan.symbol for scan in report.scans] == list(symbols)
    assert all(scan.status == "failed" for scan in report.scans)
    assert called == list(symbols)
    assert runtime.history.held_symbol is None
    assert runtime.history.peak_in_flight == 1
    assert runtime.snapshot().symbols[0] == "ETHUSDT"


def test_trade_windows_stay_bounded_across_repeated_cycles() -> None:
    cache = ClosedAggTradeCache(max_entries=8, ttl_seconds=60)
    budget = SymbolHistoryBudget()
    symbols = ("BTCUSDT", "ZECUSDT", "ETHUSDT", "TAOUSDT", "HYPEUSDT")
    start = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
    end = start + timedelta(minutes=15)

    def evaluate(symbol: str) -> SymbolScanOutcome:
        key = ("policy", symbol, start.isoformat(), end.isoformat())
        cache.put(key, tuple({"id": index} for index in range(50)))
        assert cache.get(key) is not None
        cache.drop_symbol(symbol)
        assert cache.get(key) is None
        return SymbolScanOutcome(symbol=symbol, status="ok")

    for _cycle in range(5):
        scan_symbols_sequentially(symbols, evaluate, budget)
    assert len(cache) == 0
    assert budget.held_symbol is None
    assert budget.peak_in_flight == 1
    assert budget.rejected_overlaps == 0


def test_strategy_match_follows_symbol_and_rejects_stale_evidence() -> None:
    btc = first_slice_identity(timeframe=Timeframe.M15, replay=True, is_live=False)
    aligned = match_strategy_to_evidence(
        strategy_symbol="BTCUSDT",
        evidence=SymbolMarketEvidence(
            symbol="BTCUSDT",
            identity=btc,
            source="replay",
            freshness="fresh",
        ),
    )
    assert aligned.matched is True
    assert aligned.reason == "symbol_aligned"
    mismatched = match_strategy_to_evidence(
        strategy_symbol="BTCUSDT",
        evidence=SymbolMarketEvidence(
            symbol="ETHUSDT",
            identity=btc,
            source="replay",
            freshness="fresh",
        ),
    )
    assert mismatched.matched is False
    assert mismatched.reason == "symbol_mismatch"
    stale = match_strategy_to_evidence(
        strategy_symbol="BTCUSDT",
        evidence=SymbolMarketEvidence(
            symbol="BTCUSDT",
            identity=btc,
            source="replay",
            freshness="stale",
        ),
    )
    assert stale.matched is False
    assert stale.reason == "stale_evidence"


def test_legacy_btc_symbol_order_helper_is_unchanged() -> None:
    assert normalize_paper_symbols([]) == (FIRST_SLICE_SYMBOL,)
    assert normalize_paper_symbols(["ethusdt", "BTCUSDT"]) == ("BTCUSDT", "ETHUSDT")
    assert normalize_paper_symbols(["ETHUSDT"])[0] == "BTCUSDT"


def test_paper_only_and_real_trading_stays_disabled() -> None:
    settings = Settings()
    assert settings.execution_mode is ExecutionMode.PAPER
    assert settings.enable_real_trading is False
    assert settings.real_trading_enabled is False
    store = MemoryWatchlistStore(default_watchlist(now=NOW))
    store.save(set_enabled(store.load(), 1, False, now=NOW))
    assert settings.real_trading_enabled is False
    assert settings.enable_real_trading is False


def _target(symbol: str) -> PaperScanTarget:
    return PaperScanTarget(
        organization_id=ORG,
        user_id=USER,
        strategy_id=uuid4(),
        strategy_version_id=uuid4(),
        compiled_setup_definition_id=uuid4(),
        compiled_content_hash="ab" * 32,
        fusion_policy_version="fusion-policy/v1",
        symbol=symbol,
    )


def _identity_for(instrument: object) -> object:
    from app.market_contracts.first_slice import first_slice_identity
    from app.schemas.common import Timeframe

    venue = getattr(instrument, "venue", None)
    if instrument == binance_usdm_btcusdt() or venue is VenueId.BINANCE:
        return first_slice_identity(
            timeframe=Timeframe.M15,
            replay=True,
            is_live=False,
            instrument=instrument,  # type: ignore[arg-type]
        )
    from app.market_contracts.enums import SourceFamily
    from app.market_contracts.identity import (
        BYBIT_ADAPTER_VERSION,
        BYBIT_AGGRESSOR_CONVENTION,
        EvidenceMarketIdentity,
        ProviderProvenance,
        SourceIdentity,
    )

    source = SourceIdentity(
        family=SourceFamily.BYBIT_USDT_PERPETUAL_PUBLIC,
        provider_name="bybit-usdt-perpetual",
        adapter_version=BYBIT_ADAPTER_VERSION,
        aggressor_convention=BYBIT_AGGRESSOR_CONVENTION,
    )
    return EvidenceMarketIdentity(
        venue=VenueId.BYBIT,
        market_type=instrument.market_type,  # type: ignore[attr-defined]
        instrument=instrument,  # type: ignore[arg-type]
        timeframe=Timeframe.M15,
        source=source,
        provenance=ProviderProvenance(
            provider_name=source.provider_name,
            source_family=source.family,
            adapter_version=source.adapter_version,
            is_live=True,
            fallback_used=False,
            is_mock=False,
            detail="Bybit test identity.",
        ),
    )

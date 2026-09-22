"""Live/replay evidence mode mismatch fails closed. Missing monitors do not mint."""

from __future__ import annotations

import pytest

from app.evidence_pipeline.assembler import FirstSliceEvidenceAssembler
from app.evidence_pipeline.watcher_port import AssemblingWatcherScanEvidence
from app.market_contracts.adapters.binance_usdm import BinanceUsdmPerpetualSource
from app.market_contracts.adapters.replay import ReplayPerpetualSource
from app.market_contracts.enums import SourceFamily
from app.market_contracts.first_slice import CANONICAL_EVALUATED_AT
from app.market_monitor.backoff import BackoffPolicy
from app.market_monitor.monitor import PerpetualMarketMonitor
from app.market_monitor.types import MarketMode
from app.watcher.errors import WatcherEvidenceUnavailableError
from app.watcher.memory import InMemoryWatcherStore
from tests.support.phase6_fusion import ORG_ID
from tests.test_live_evidence_pipeline import (
    _evaluation_command,
    _fixture_usdm_handler,
    _non_placeholder_executable,
)
from tests.test_watcher_stack_integration import _SpyAssembler


def _backoff() -> BackoffPolicy:
    return BackoffPolicy(initial_seconds=0.25, max_seconds=4.0)


def _replay_monitor() -> PerpetualMarketMonitor:
    return PerpetualMarketMonitor(
        ReplayPerpetualSource(),
        replay=True,
        backoff=_backoff(),
        poll_seconds=0.01,
    )


def _live_source() -> BinanceUsdmPerpetualSource:
    return BinanceUsdmPerpetualSource(
        base_url="https://fapi.binance.com",
        transport=_fixture_usdm_handler(),
    )


def _live_monitor() -> PerpetualMarketMonitor:
    return PerpetualMarketMonitor(
        _live_source(),
        replay=False,
        backoff=_backoff(),
        poll_seconds=0.01,
        clock=lambda: CANONICAL_EVALUATED_AT,
    )


def _port(
    assembler: FirstSliceEvidenceAssembler,
    monitor: object | None,
    *,
    production: bool = False,
) -> AssemblingWatcherScanEvidence:
    return AssemblingWatcherScanEvidence(
        assembler,
        executable_resolver=lambda _command: _non_placeholder_executable(ORG_ID),
        session=object() if production else None,  # type: ignore[arg-type]
        watcher_store=InMemoryWatcherStore() if production else None,
        monitor=monitor,  # type: ignore[arg-type]
    )


def test_live_monitor_plus_replay_assembler_is_wrong_source() -> None:
    port = _port(
        FirstSliceEvidenceAssembler(ReplayPerpetualSource(), replay=True),
        _live_monitor(),
    )
    with pytest.raises(WatcherEvidenceUnavailableError) as exc:
        port.load(_evaluation_command(ORG_ID))
    assert exc.value.reason_code == "wrong_source"


def test_replay_monitor_plus_live_assembler_is_wrong_source() -> None:
    port = _port(
        FirstSliceEvidenceAssembler(_live_source(), replay=False),
        _replay_monitor(),
    )
    with pytest.raises(WatcherEvidenceUnavailableError) as exc:
        port.load(_evaluation_command(ORG_ID))
    assert exc.value.reason_code == "wrong_source"


def test_missing_monitor_does_not_bypass_production_authority() -> None:
    spy = _SpyAssembler()
    port = AssemblingWatcherScanEvidence(
        spy,
        executable_resolver=lambda _command: _non_placeholder_executable(ORG_ID),
        session=object(),  # type: ignore[arg-type]
        watcher_store=InMemoryWatcherStore(),
        monitor=None,
    )
    with pytest.raises(WatcherEvidenceUnavailableError) as exc:
        port.load(_evaluation_command(ORG_ID))
    assert exc.value.reason_code == "missing_monitor"
    assert spy.called is False


def test_replay_mode_with_live_source_family_is_wrong_source() -> None:
    monitor = _replay_monitor()
    snapshot = monitor.tick("BTCUSDT")
    mismatched = snapshot.model_copy(
        update={"source_family": SourceFamily.BINANCE_USDM_FUTURES_PUBLIC}
    )
    assert mismatched.mode is MarketMode.REPLAY

    class _Fixed:
        def latest(self, _symbol: str) -> object:
            return mismatched

    port = _port(FirstSliceEvidenceAssembler(ReplayPerpetualSource(), replay=True), _Fixed())
    with pytest.raises(WatcherEvidenceUnavailableError) as exc:
        port.load(_evaluation_command(ORG_ID))
    assert exc.value.reason_code == "wrong_source"


def test_correct_replay_assembles() -> None:
    port = _port(
        FirstSliceEvidenceAssembler(ReplayPerpetualSource(), replay=True),
        _replay_monitor(),
    )
    loaded = port.load(_evaluation_command(ORG_ID))
    assert loaded is not None
    assert loaded.organization_id == ORG_ID


def test_correct_live_assembles() -> None:
    port = _port(
        FirstSliceEvidenceAssembler(_live_source(), replay=False),
        _live_monitor(),
    )
    loaded = port.load(_evaluation_command(ORG_ID))
    assert loaded is not None
    assert loaded.organization_id == ORG_ID

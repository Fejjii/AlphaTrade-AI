"""AT-072 Watcher stack fail-closed checks.

Stale evidence, provider outage, wrong tenant, wrong lineage, and in-memory
policy cannot mint a Candidate. The PostgreSQL product proof lives in
``test_watcher_product_proof_postgres.py``. Watcher stays off by default.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Membership, Organization, User
from app.evidence_pipeline.assembler import FirstSliceEvidenceAssembler
from app.evidence_pipeline.watcher_port import AssemblingWatcherScanEvidence
from app.market_contracts.adapters.replay import ReplayPerpetualSource
from app.market_contracts.errors import RegionalProviderFailureError
from app.market_monitor.backoff import BackoffPolicy
from app.market_monitor.monitor import PerpetualMarketMonitor
from app.market_monitor.types import MarketAvailability, MonitorReason
from app.market_monitor.watcher_gate import watcher_evidence_error_for_monitor
from app.market_monitor.watcher_port import MarketMonitorWatcherPort
from app.schemas.common import MembershipRole
from app.schemas.watcher_monitoring import WatcherMonitoringRuntimeState
from app.services.canonical_strategy_evaluation import resolve_executable_strategy_policy
from app.services.watcher_monitoring_service import WatcherMonitoringService
from app.signal_fusion.enums import SetupAssessmentState
from app.signal_fusion.lifecycle import CandidateLifecycleService
from app.signal_fusion.memory import InMemoryCandidateRepository
from app.watcher.errors import WatcherEvidenceUnavailableError
from app.watcher.fusion_evaluation import (
    BoundEvaluationClock,
    ExecutablePolicyAuthority,
    WatcherCanonicalScanEvidence,
)
from app.workers.watcher_paper_targets import PaperScanTarget, list_paper_scan_targets
from tests.support.live_market_monitor import ScriptedPerpetualSource
from tests.support.phase5_market import consecutive_bars, trade
from tests.support.phase6_evaluator import EvaluatorWorld, make_world, subsequent_bars
from tests.test_live_evidence_pipeline import _evaluation_command, _non_placeholder_executable
from tests.test_watcher_paper_runtime import (
    ORG,
    ORG_B,
    USER,
    USER_B,
    _create_strategy,
    _runtime,
    _seed_approved_compiled,
    _settings,
    _snapshot_for_executable,
    _world_factory,
)

NOW = datetime(2026, 9, 21, 14, 0, tzinfo=UTC)


@pytest.fixture
def session_factory() -> Iterator[sessionmaker[Session]]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn: object, _record: object) -> None:
        cursor = dbapi_conn.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    from app.core.persistence_firewall import install_persistence_firewall

    install_persistence_firewall()
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        db.add_all(
            [
                Organization(id=ORG, name="AT072 Org"),
                Organization(id=ORG_B, name="AT072 Org B"),
                User(id=USER, email="at072@test.example", hashed_password="not-a-real-hash"),
                User(id=USER_B, email="at072-b@test.example", hashed_password="not-a-real-hash"),
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


class _SpyAssembler(FirstSliceEvidenceAssembler):
    def __init__(self) -> None:
        super().__init__(ReplayPerpetualSource(), replay=True)
        self.called = False

    def assemble(self, **kwargs: object) -> object:  # type: ignore[override]
        self.called = True
        return super().assemble(**kwargs)


def _replay_monitor() -> PerpetualMarketMonitor:
    return PerpetualMarketMonitor(
        ReplayPerpetualSource(),
        replay=True,
        backoff=BackoffPolicy(initial_seconds=0.25, max_seconds=4.0),
        poll_seconds=0.01,
    )


def _live_monitor(
    source: ScriptedPerpetualSource,
    *,
    clock: object | None = None,
) -> PerpetualMarketMonitor:
    return PerpetualMarketMonitor(
        source,
        replay=False,
        backoff=BackoffPolicy(initial_seconds=0.25, max_seconds=4.0),
        poll_seconds=0.01,
        clock=clock if callable(clock) else None,
    )


def _fresh_live_monitor() -> PerpetualMarketMonitor:
    bars = consecutive_bars(2, last_open=NOW - timedelta(minutes=15))
    source = ScriptedPerpetualSource(replay=False, bars_15m=bars)
    source.enqueue(
        [
            trade(
                sequence=10,
                price="101234.7",
                quantity="0.01",
                buyer_is_maker=False,
                event_time=NOW - timedelta(seconds=1),
                receive_at=NOW - timedelta(seconds=1),
            )
        ]
    )
    return _live_monitor(source)


def _stale_live_monitor() -> PerpetualMarketMonitor:
    now = {"t": NOW}

    def clock() -> datetime:
        return now["t"]

    source = ScriptedPerpetualSource(replay=False)
    source.enqueue(
        [
            trade(
                sequence=10,
                price="100000.5",
                quantity="0.01",
                buyer_is_maker=False,
                event_time=NOW - timedelta(seconds=1),
                receive_at=NOW - timedelta(seconds=1),
            )
        ]
    )
    monitor = _live_monitor(source, clock=clock)
    first = monitor.tick("BTCUSDT")
    assert first.current_price is not None
    now["t"] = NOW + timedelta(seconds=12)
    later = monitor.tick("BTCUSDT")
    assert later.availability is MarketAvailability.STALE
    assert later.reason is MonitorReason.STALE_STREAM
    return monitor


def test_defaults_keep_watcher_off() -> None:
    settings = _settings()
    assert settings.watcher_orchestration_enabled is False
    assert settings.market_watcher_enabled is False
    assert settings.execution_mode.value == "paper"
    assert settings.enable_real_trading is False
    assert settings.perpetual_evidence_source == "replay"


def test_replay_monitor_allows_canonical_assembly() -> None:
    monitor = _replay_monitor()
    snapshot = monitor.tick("BTCUSDT")
    assert watcher_evidence_error_for_monitor(snapshot) is None
    assert snapshot.availability is MarketAvailability.REPLAY
    assert (
        snapshot.current_price is None
        or snapshot.current_price.usable_as_current_market_price is False
    )
    port = AssemblingWatcherScanEvidence(
        FirstSliceEvidenceAssembler(ReplayPerpetualSource(), replay=True),
        executable_resolver=lambda _command: _non_placeholder_executable(ORG),
        monitor=MarketMonitorWatcherPort(monitor),
    )
    loaded = port.load(_evaluation_command(ORG))
    assert loaded is not None
    assert loaded.policy_authority is ExecutablePolicyAuthority.IN_MEMORY_TEST_HELPER


def test_fresh_live_monitor_allows_watcher_gate() -> None:
    monitor = _fresh_live_monitor()
    snapshot = monitor.tick("BTCUSDT", now=NOW)
    assert snapshot.availability is MarketAvailability.FRESH
    assert snapshot.current_price is not None
    assert snapshot.current_price.usable_as_current_market_price is True
    assert watcher_evidence_error_for_monitor(snapshot) is None


def test_stale_monitor_blocks_assembler() -> None:
    monitor = _stale_live_monitor()
    spy = _SpyAssembler()
    port = AssemblingWatcherScanEvidence(
        spy,
        executable_resolver=lambda _command: _non_placeholder_executable(ORG),
        monitor=monitor,
    )
    with pytest.raises(WatcherEvidenceUnavailableError) as exc:
        port.load(_evaluation_command(ORG))
    assert exc.value.reason_code == "stale_evidence"
    assert spy.called is False


def test_provider_outage_monitor_blocks_assembler() -> None:
    source = ScriptedPerpetualSource(replay=False)
    source.enqueue(RegionalProviderFailureError("connect timeout"))
    monitor = _live_monitor(source)
    snapshot = monitor.tick("BTCUSDT", now=NOW)
    assert snapshot.availability is MarketAvailability.UNAVAILABLE
    assert snapshot.reason is MonitorReason.PROVIDER_UNAVAILABLE
    spy = _SpyAssembler()
    port = AssemblingWatcherScanEvidence(
        spy,
        executable_resolver=lambda _command: _non_placeholder_executable(ORG),
        monitor=monitor,
    )
    with pytest.raises(WatcherEvidenceUnavailableError) as exc:
        port.load(_evaluation_command(ORG))
    assert exc.value.reason_code == "provider_outage"
    assert spy.called is False


def test_stale_monitor_cannot_mint_candidate(session_factory: sessionmaker[Session]) -> None:
    world = make_world()
    monitor = _stale_live_monitor()
    with session_factory() as session:
        _seed_approved_compiled(session)
    repo = InMemoryCandidateRepository()
    lifecycle = CandidateLifecycleService(repository=repo, clock=BoundEvaluationClock())
    runtime, _clock, probe, _store = _runtime(
        session_factory,
        world=world,
        lifecycle=lifecycle,
        evidence_factory=_gated_world_factory(world, monitor),
    )
    report = runtime.run_cycle()
    assert report.scans[0].candidate_ids == ()
    assert report.scans[0].reason_code == "stale_evidence"
    assert repo.list_for_organization(ORG)[1] == 0
    assert probe.execution == []


def test_provider_outage_cannot_mint_candidate(session_factory: sessionmaker[Session]) -> None:
    world = make_world()
    source = ScriptedPerpetualSource(replay=False)
    source.enqueue(RegionalProviderFailureError("connect timeout"))
    monitor = _live_monitor(source)
    monitor.tick("BTCUSDT", now=NOW)
    with session_factory() as session:
        _seed_approved_compiled(session)
    repo = InMemoryCandidateRepository()
    lifecycle = CandidateLifecycleService(repository=repo, clock=BoundEvaluationClock())
    runtime, _clock, probe, _store = _runtime(
        session_factory,
        world=world,
        lifecycle=lifecycle,
        evidence_factory=_gated_world_factory(world, monitor),
    )
    report = runtime.run_cycle()
    assert report.scans[0].candidate_ids == ()
    assert report.scans[0].reason_code == "provider_outage"
    assert probe.execution == []


def test_in_memory_policy_cannot_mint_candidate(session_factory: sessionmaker[Session]) -> None:
    world = make_world()
    with session_factory() as session:
        _strategy, version_id = _seed_approved_compiled(session)
        executable = resolve_executable_strategy_policy(
            session, organization_id=ORG, strategy_version_id=version_id
        )

    class _InMemoryPort:
        def load(self, command: object) -> WatcherCanonicalScanEvidence:
            del command
            snapshot = _snapshot_for_executable(world, executable)
            return snapshot.model_copy(
                update={"policy_authority": ExecutablePolicyAuthority.IN_MEMORY_TEST_HELPER}
            )

    def factory(_session: Session | None, _store: object, _symbol: str) -> _InMemoryPort:
        return _InMemoryPort()

    repo = InMemoryCandidateRepository()
    lifecycle = CandidateLifecycleService(repository=repo, clock=BoundEvaluationClock())
    runtime, _clock, probe, _store = _runtime(
        session_factory,
        world=world,
        lifecycle=lifecycle,
        evidence_factory=factory,
    )
    report = runtime.run_cycle()
    assert report.scans[0].candidate_ids == ()
    assert repo.list_for_organization(ORG)[1] == 0
    assert probe.execution == []


def test_wrong_tenant_cannot_mint_candidate(session_factory: sessionmaker[Session]) -> None:
    world = make_world()
    with session_factory() as session:
        _seed_approved_compiled(session)
        targets = list_paper_scan_targets(
            session, symbols=["BTCUSDT"], organization_id=ORG, limit=1
        )
        assert targets
        foreign = PaperScanTarget(
            organization_id=ORG_B,
            user_id=USER_B,
            strategy_id=targets[0].strategy_id,
            strategy_version_id=targets[0].strategy_version_id,
            compiled_setup_definition_id=targets[0].compiled_setup_definition_id,
            compiled_content_hash=targets[0].compiled_content_hash,
            fusion_policy_version=targets[0].fusion_policy_version,
            symbol=targets[0].symbol,
        )
    runtime, _clock, probe, _store = _runtime(
        session_factory,
        world=world,
        target_loader=lambda _session: (foreign,),
    )
    report = runtime.run_cycle()
    assert report.scans[0].candidate_ids == ()
    assert report.scans[0].reason_code in {
        "missing_canonical_evidence",
        "organization_mismatch",
        "strategy_not_approved",
    }
    assert probe.unused is True


def test_wrong_lineage_cannot_mint_candidate(session_factory: sessionmaker[Session]) -> None:
    world = make_world()
    with session_factory() as session:
        _seed_approved_compiled(session)
        draft = _create_strategy(session)
        session.commit()
        draft_id = draft.id

    def _draft_loader(_session: Session | None) -> tuple[PaperScanTarget, ...]:
        return (
            PaperScanTarget(
                organization_id=ORG,
                user_id=USER,
                strategy_id=draft_id,
                strategy_version_id=uuid4(),
                compiled_setup_definition_id=uuid4(),
                compiled_content_hash="ab" * 32,
                fusion_policy_version="first-slice-fusion/v1",
                symbol="BTCUSDT",
            ),
        )

    runtime, _clock, probe, _store = _runtime(
        session_factory, world=world, target_loader=_draft_loader
    )
    report = runtime.run_cycle()
    assert report.scans[0].candidate_ids == ()
    assert report.scans[0].reason_code in {
        "missing_canonical_evidence",
        "strategy_not_approved",
        "draft_not_executable",
    }
    assert probe.unused is True


def test_expired_setup_cannot_mint_candidate(session_factory: sessionmaker[Session]) -> None:
    base = make_world()
    later = subsequent_bars(base.trigger, count=2, high=base.trigger.high)
    world = EvaluatorWorld(
        policy=base.policy,
        command=base.command,
        evidence=base.evidence.model_copy(update={"subsequent_final_15m": tuple(later)}),
        evaluated_at=base.evaluated_at,
        bars_15m=base.bars_15m,
        bars_4h=base.bars_4h,
        snapshot=base.snapshot,
        trigger=base.trigger,
    )
    monitor = _replay_monitor()
    with session_factory() as session:
        _seed_approved_compiled(session)
    runtime, _clock, probe, _store = _runtime(
        session_factory,
        world=world,
        evidence_factory=_gated_world_factory(world, monitor),
    )
    report = runtime.run_cycle()
    assert report.scans[0].reason_code == SetupAssessmentState.EXPIRED.value
    assert report.scans[0].candidate_ids == ()
    assert probe.execution == []


def test_config_alone_never_shows_running(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        snapshot = WatcherMonitoringService(
            session,
            _settings(watcher_orchestration_enabled=True),
            now=NOW,
            monitor=_replay_monitor(),
        ).get_snapshot(organization_id=ORG, user_id=USER)
    assert snapshot.watcher_status is WatcherMonitoringRuntimeState.STALE
    assert snapshot.paper_posture.runtime_evidence is False


def _gated_world_factory(world: object, monitor: PerpetualMarketMonitor) -> object:
    inner = _world_factory(world)  # type: ignore[arg-type]

    def factory(session: Session | None, store: object, symbol: str) -> object:
        port = inner(session, store, symbol)

        class _Gated:
            def load(self, command: object) -> object:
                snapshot = monitor.latest(symbol)
                gated = watcher_evidence_error_for_monitor(snapshot)
                if gated is not None:
                    raise gated
                return port.load(command)

        return _Gated()

    return factory

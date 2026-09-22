"""PostgreSQL product proof: approved strategy through the real assembler to monitoring.

Does not insert CONFIRMED_SETUP, lease rows, heartbeats, or monitoring state.
Watcher, Telegram, and live trading stay disabled in deployment defaults.
"""

from __future__ import annotations

from uuid import uuid4

from app.core.config import Settings
from app.core.persistence_firewall import install_persistence_firewall
from app.db.models import ManualLevelRevision, Membership, Organization, User
from app.evidence_pipeline.assembler import FirstSliceEvidenceAssembler
from app.evidence_pipeline.setup_lifetime import SetupLifetimeStore
from app.evidence_pipeline.watcher_port import AssemblingWatcherScanEvidence
from app.market_contracts.adapters.replay import ReplayPerpetualSource
from app.market_monitor.backoff import BackoffPolicy
from app.market_monitor.monitor import PerpetualMarketMonitor
from app.market_monitor.watcher_port import MarketMonitorWatcherPort
from app.persistence.setup_lifetime import SqlAlchemySetupLifetimeStore
from app.schemas.common import ManualLevelType, MembershipRole
from app.schemas.watcher_monitoring import WatcherMonitoringRuntimeState
from app.services.manual_level_service import manual_level_revision_content_hash
from app.services.watcher_monitoring_service import WatcherMonitoringService
from app.signal_fusion.enums import SetupAssessmentState
from app.signal_fusion.memory import UtcClock
from app.workers.watcher_paper import build_watcher_paper_runtime
from tests.support.phase5_market import EVALUATED_AT
from tests.support.phase6_evaluator import (
    RESISTANCE_EFFECTIVE,
    SWING_HIGH,
    build_context_4h_bars,
    build_pattern_15m_bars,
    build_slice_trades,
)
from tests.support.postgres_persistence import phase7_plan_session_factory, requires_postgres
from tests.test_watcher_paper_runtime import ORG, USER, _seed_approved_compiled, _settings


def _confirming_source() -> ReplayPerpetualSource:
    bars_15m = build_pattern_15m_bars()
    return ReplayPerpetualSource(
        bars_15m=bars_15m,
        bars_4h=build_context_4h_bars(),
        trades=build_slice_trades(bars_15m),
        evaluated_at=EVALUATED_AT,
    )


def _persist_resistance(session: object) -> None:
    level_id = uuid4()
    revision_id = uuid4()
    content_hash = manual_level_revision_content_hash(
        level_id=level_id,
        revision_id=revision_id,
        revision_number=1,
        organization_id=ORG,
        actor_user_id=USER,
        instrument="BTCUSDT",
        exchange="binance",
        venue="binance",
        market_type="perpetual",
        price_unit="quote",
        timeframe="4h",
        level_type=ManualLevelType.RESISTANCE.value,
        value=SWING_HIGH,
        price_low=None,
        price_high=None,
        valid=True,
        effective_at=RESISTANCE_EFFECTIVE,
        created_at=RESISTANCE_EFFECTIVE,
        supersedes_revision_id=None,
    )
    session.add(  # type: ignore[attr-defined]
        ManualLevelRevision(
            id=revision_id,
            level_id=level_id,
            revision_number=1,
            organization_id=ORG,
            user_id=USER,
            instrument="BTCUSDT",
            exchange="binance",
            timeframe="4h",
            level_type=ManualLevelType.RESISTANCE,
            value=SWING_HIGH,
            valid=True,
            actor_user_id=USER,
            venue="binance",
            market_type="perpetual",
            price_unit="quote",
            content_hash=content_hash,
            effective_at=RESISTANCE_EFFECTIVE,
        )
    )
    session.commit()  # type: ignore[attr-defined]


@requires_postgres
def test_postgres_assembler_path_mints_confirmed_candidate_and_monitoring_reads_it() -> None:
    install_persistence_firewall()
    factory = phase7_plan_session_factory()
    with factory() as session:
        session.add_all(
            [
                Organization(id=ORG, name="Watcher product proof"),
                User(
                    id=USER,
                    email="watcher-proof@test.example",
                    hashed_password="not-a-real-hash",
                ),
            ]
        )
        session.flush()
        session.add(Membership(organization_id=ORG, user_id=USER, role=MembershipRole.TRADER))
        session.commit()
        _seed_approved_compiled(session)
        _persist_resistance(session)

    source = _confirming_source()
    monitor = PerpetualMarketMonitor(
        source,
        replay=True,
        backoff=BackoffPolicy(initial_seconds=0.25, max_seconds=4.0),
        poll_seconds=0.01,
    )
    settings = _settings(watcher_orchestration_enabled=True)
    assert settings.market_watcher_enabled is False
    assert settings.enable_real_trading is False
    assert settings.telegram_alerts_enabled is False
    assert Settings().watcher_orchestration_enabled is False
    assert Settings().market_watcher_enabled is False
    assert Settings().enable_real_trading is False

    def evidence_factory(db: object, store: object, symbol: str) -> AssemblingWatcherScanEvidence:
        lifetime = SqlAlchemySetupLifetimeStore(db) if db is not None else SetupLifetimeStore()
        return AssemblingWatcherScanEvidence(
            FirstSliceEvidenceAssembler(source, replay=True, lifetime=lifetime),
            session=db,  # type: ignore[arg-type]
            watcher_store=store,  # type: ignore[arg-type]
            symbol=symbol,
            monitor=MarketMonitorWatcherPort(monitor),
        )

    runtime = build_watcher_paper_runtime(
        settings,
        factory,
        evidence_factory=evidence_factory,  # type: ignore[arg-type]
        clock=UtcClock(),
    )
    report = runtime.run_cycle()
    assert report.scans, "approved strategy did not become a scan target"
    scan = report.scans[0]
    assert scan.reason_code == SetupAssessmentState.CONFIRMED_SETUP.value, scan.reason_code
    assert len(scan.candidate_ids) == 1
    candidate_id = scan.candidate_ids[0]
    assert runtime.side_effects.execution == []  # type: ignore[attr-defined]
    assert runtime.side_effects.telegram == []  # type: ignore[attr-defined]

    from app.runtime.canonical import build_production_canonical_runtime

    canonical = build_production_canonical_runtime(factory, settings=settings)
    with factory() as session:
        snapshot = WatcherMonitoringService(
            session,
            settings,
            monitor=monitor,
            paper_runtime=runtime,
            canonical_runtime=canonical,
        ).get_snapshot(organization_id=ORG, user_id=USER)

    assert any(item.candidate_id == candidate_id for item in snapshot.canonical_candidates)
    assert snapshot.setup_assessments
    assert snapshot.setup_assessments[0].state is SetupAssessmentState.CONFIRMED_SETUP
    assert snapshot.setup_assessments[0].projection == "candidate_mint_invariant"
    assert snapshot.leases
    assert snapshot.leases[0].owner_id == runtime.snapshot().worker_id
    assert snapshot.leases[0].fenced is True
    assert snapshot.leases[0].heartbeat_fresh is True
    assert snapshot.paper_posture.real_trading_enabled is False
    assert snapshot.paper_posture.telegram_enabled is False
    assert snapshot.watcher_status is WatcherMonitoringRuntimeState.RUNNING
    stored, total = canonical.candidate_repository.list_for_organization(ORG)
    assert total == 1
    assert stored[0].candidate_id == candidate_id

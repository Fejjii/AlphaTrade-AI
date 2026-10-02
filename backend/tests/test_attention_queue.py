"""Deterministic reduction and real authenticated SELECT adapter regressions."""

from datetime import datetime, timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.attention.contracts import AttentionCategory as Category
from app.attention.contracts import AttentionSignal
from app.attention.reader import MARKET_TTL, AttentionQueueService
from app.attention.service import build_queue
from app.daily_review.contracts import ReviewSource
from app.db.models import (
    BacktestRun,
    DailyRiskState,
    JournalTrade,
    KillSwitchState,
    LessonCandidate,
    Membership,
    PaperValidationAlert,
    PaperValidationRun,
    RiskEvent,
    StrategyConversationProposal,
    UserRiskSettings,
)
from app.db.strategy_brain import BrainSetupRow
from app.db.telegram_security import TelegramOutboxRow
from app.db.watcher_orchestration import WatcherHealthSnapshotRow
from app.db.watcher_watchlist import WatcherSymbolStatusRow, WatcherWatchlistRow
from app.paper_evaluation.contracts import DataQualityClass, PaperEvaluationStage
from app.persistence.paper_evaluation_postgres import PostgresPaperEvaluationStore
from app.schemas.common import (
    AlertDeliveryChannel,
    AlertDeliveryStatus,
    BacktestRunStatus,
    JournalTradeSource,
    JournalTradeStatus,
    PaperAlertType,
    PaperValidationStatus,
    RiskAction,
    RiskRuleId,
    RiskSeverity,
    StrategyProposalStatus,
)
from app.telegram_security.contracts import OutboxState
from tests.support.paper_evaluation import make_observation
from tests.test_daily_review_api import AT, ORG, OTHER_ORG, OUTSIDER, PEER, USER, headers

pytest_plugins = ("tests.test_daily_review_api",)
NOW = AT + timedelta(minutes=5)
STRATEGY, VERSION = UUID(int=700), UUID(int=701)


def signal(**overrides):
    return AttentionSignal.model_validate(
        {
            "organization_id": ORG,
            "user_id": USER,
            "semantic_key": "same-problem",
            "category": Category.CONFIRMED,
            "severity": "medium",
            "title": "Recorded setup",
            "reason": "Confirmed in source",
            "recommended_next_action": "Review the evidence.",
            "expires_at": NOW + timedelta(minutes=1),
            "sources": (ReviewSource(record_type="setups", record_id="one", occurred_at=AT),),
            **overrides,
        }
    )


def reduce(*signals, now=NOW):
    return build_queue(tuple(signals), organization_id=ORG, user_id=USER, now=now)


def test_semantic_duplicates_merge_sources_and_keep_identity_across_clock_and_order():
    a = signal()
    b = signal(
        reason="Newer recorded state",
        sources=(
            ReviewSource(
                record_type="setups", record_id="two", occurred_at=AT + timedelta(minutes=1)
            ),
        ),
    )
    first = reduce(a, b, a)
    second = reduce(b, a, now=NOW + timedelta(seconds=1))
    assert first.items == second.items
    assert len(first.items) == 1
    assert first.items[0].reason == "Newer recorded state"
    assert {s.record_id for s in first.items[0].sources} == {"one", "two"}
    assert reduce(b).items[0].item_id == first.items[0].item_id


def test_equal_timestamp_ties_are_deterministic():
    a, b = signal(), signal(reason="Different same-time recorded state")
    assert reduce(a, b) == reduce(b, a)


def test_expiry_boundary_future_and_naive_clock():
    fact = signal(expires_at=NOW)
    assert len(reduce(fact, now=NOW - timedelta(microseconds=1)).items) == 1
    assert reduce(fact).items == ()
    assert (
        reduce(
            signal(
                sources=(
                    ReviewSource(
                        record_type="setups",
                        record_id="future",
                        occurred_at=NOW + timedelta(seconds=1),
                    ),
                )
            )
        ).items
        == ()
    )
    with pytest.raises(ValidationError):
        reduce(signal(), now=NOW.replace(tzinfo=None))


def test_reducer_scope_no_action_and_risk_priority():
    queue = reduce(signal(organization_id=OTHER_ORG), signal(user_id=PEER))
    assert queue.items == () and queue.recommended_next_action is None
    assert reduce(signal(recommended_next_action=None)).recommended_next_action is None
    queue = reduce(
        signal(category=Category.CONFIRMED, severity="critical"),
        signal(category=Category.RISK_BLOCK, severity="high"),
        signal(category=Category.PROVIDER_OUTAGE, severity="critical"),
    )
    assert queue.items[0].category == Category.RISK_BLOCK
    assert not queue.executes_trades and not queue.approves_strategies
    assert not queue.bypasses_risk and not queue.telegram_delivery


@pytest.fixture
def attention_api(review_api, monkeypatch):
    from app.api.routes import dashboard

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW

    monkeypatch.setattr(dashboard, "datetime", Clock)
    return review_api


def setup(id=710, **overrides):
    return BrainSetupRow(
        id=UUID(int=id),
        organization_id=ORG,
        strategy_id=STRATEGY,
        strategy_version_id=VERSION,
        symbol="BTCUSDT",
        state="FORMING",
        observed_at=AT,
        expires_at=AT + timedelta(hours=1),
        payload={
            "timeframe": "15m",
            "evidence": {
                "closed_ohlcv": "AVAILABLE",
                "volume": "AVAILABLE",
                "moving_average": "MISSING",
                "higher_timeframe": "MISSING",
            },
        },
        **overrides,
    )


def read(engine, user=USER, org=ORG, now=NOW):
    with Session(engine) as session:
        return AttentionQueueService(session).queue(organization_id=org, user_id=user, now=now)


def test_missing_required_evidence_optional_evidence_and_stale_expiry(attention_api):
    _, engine = attention_api
    with Session(engine) as session:
        row = setup()
        row.payload = {**row.payload, "required_evidence": "MISSING"}
        session.add_all([row, setup(711)])
        session.commit()
    queue = read(engine)
    missing = [i for i in queue.items if i.category == Category.MISSING_EVIDENCE]
    assert len(missing) == 1
    assert missing[0].symbol == "BTCUSDT" and missing[0].strategy_version_id == VERSION
    assert missing[0].sources[0].record_id == str(UUID(int=710))
    assert len([i for i in queue.items if i.category == Category.FORMING]) == 2
    stale = read(engine, now=AT + timedelta(minutes=15))
    assert len([i for i in stale.items if i.category == Category.STALE_EVIDENCE]) == 2
    expired = read(engine, now=AT + timedelta(hours=1))
    assert not any(
        i.category in {Category.FORMING, Category.MISSING_EVIDENCE, Category.STALE_EVIDENCE}
        for i in expired.items
    )


def test_confirmed_setup_is_suppressed_after_terminal_state(attention_api):
    _, engine = attention_api
    with Session(engine) as session:
        row = setup()
        row.state = "CONFIRMED"
        session.add(row)
        session.commit()
    assert any(i.category == Category.CONFIRMED for i in read(engine).items)
    with Session(engine) as session:
        session.get(BrainSetupRow, UUID(int=710)).state = "INVALIDATED"
        session.commit()
    assert not any(i.category == Category.CONFIRMED for i in read(engine).items)


def test_risk_events_deduplicate_prioritize_and_expire(attention_api):
    _, engine = attention_api
    with Session(engine) as session:
        session.add(setup())
        for index in range(2):
            session.add(
                RiskEvent(
                    id=UUID(int=720 + index),
                    organization_id=ORG,
                    user_id=USER,
                    rule_triggered=RiskRuleId.MAX_LEVERAGE,
                    severity=RiskSeverity.CRITICAL,
                    action_taken=RiskAction.BLOCK,
                    details={"symbol": "BTCUSDT"},
                    event_at=AT + timedelta(seconds=index),
                )
            )
        session.commit()
    item = read(engine).items[0]
    assert item.category == Category.RISK_BLOCK and item.severity == "critical"
    assert len(item.sources) == 2
    assert not any(
        i.category == Category.RISK_BLOCK
        for i in read(engine, now=AT + timedelta(days=1, seconds=1)).items
    )


def test_persistent_tenant_kill_switch_outlives_event_ttl_and_cannot_leak(attention_api):
    _, engine = attention_api
    with Session(engine) as session:
        session.add(
            KillSwitchState(id=UUID(int=793), organization_id=ORG, active=True, updated_at=AT)
        )
        session.add(KillSwitchState(organization_id=OTHER_ORG, active=True, updated_at=AT))
        session.commit()
    blocks = [
        i
        for i in read(engine, now=AT + timedelta(days=2)).items
        if i.category == Category.RISK_BLOCK
    ]
    assert len(blocks) == 1 and blocks[0].severity == "critical" and blocks[0].expires_at is None
    with Session(engine) as session:
        session.get(KillSwitchState, UUID(int=793)).active = False
        session.commit()
    assert not any(i.category == Category.RISK_BLOCK for i in read(engine).items)


def test_daily_lock_respects_recorded_user_timezone_and_expires_at_midnight(attention_api):
    _, engine = attention_api
    with Session(engine) as session:
        session.add(UserRiskSettings(organization_id=ORG, user_id=USER, timezone="Europe/Berlin"))
        session.add(
            DailyRiskState(
                organization_id=ORG, user_id=USER, day=AT.date(), locked=True, updated_at=AT
            )
        )
        session.commit()
    before = AT.replace(hour=21, minute=59)
    block = next(i for i in read(engine, now=before).items if i.category == Category.RISK_BLOCK)
    assert block.expires_at == AT.replace(hour=22)
    assert not any(
        i.category == Category.RISK_BLOCK for i in read(engine, now=AT.replace(hour=22)).items
    )


def record_scan(session, id, when, **overrides):
    PostgresPaperEvaluationStore(session).put(
        make_observation(
            **{
                "organization_id": ORG,
                "observation_id": UUID(int=id),
                "source_event_id": f"scan-{id}",
                "occurred_at": when,
                "stage": PaperEvaluationStage.WATCHER_SCAN,
                "scan_status": "failed",
                "reason_code": "provider_outage",
                "data_quality": DataQualityClass.UNAVAILABLE,
                **overrides,
            }
        )
    )


def test_provider_outage_recovery_expiry_and_no_provider_calls(attention_api):
    _, engine = attention_api
    with Session(engine) as session:
        record_scan(session, 730, AT)
        session.commit()
    item = next(i for i in read(engine).items if i.category == Category.PROVIDER_OUTAGE)
    assert "provider_outage" in item.reason and item.expires_at == AT + MARKET_TTL
    assert not any(
        i.category == Category.PROVIDER_OUTAGE for i in read(engine, now=AT + MARKET_TTL).items
    )
    with Session(engine) as session:
        record_scan(
            session,
            731,
            AT + timedelta(minutes=1),
            scan_status="succeeded",
            reason_code="no_setup",
            data_quality=DataQualityClass.FRESH,
        )
        session.commit()
    assert not any(i.category == Category.PROVIDER_OUTAGE for i in read(engine).items)


def test_strategy_proposal_pending_and_semantic_dedup(attention_api):
    _, engine = attention_api
    with Session(engine) as session:
        for index in range(2):
            session.add(
                StrategyConversationProposal(
                    id=UUID(int=740 + index),
                    organization_id=ORG,
                    user_id=USER,
                    conversation_id=UUID(int=799),
                    target_strategy_id=STRATEGY,
                    parent_version_id=VERSION,
                    status=StrategyProposalStatus.DRAFT,
                    content_hash="a" * 64,
                    created_at=AT,
                )
            )
        session.commit()
    pending = [i for i in read(engine).items if i.category == Category.PROPOSAL]
    assert len(pending) == 1 and len(pending[0].sources) == 2
    with Session(engine) as session:
        for row in session.query(StrategyConversationProposal):
            row.status = StrategyProposalStatus.CONFIRMED
        session.commit()
    assert not any(i.category == Category.PROPOSAL for i in read(engine).items)


def test_daily_review_lesson_and_pending_lesson_merge(attention_api):
    _, engine = attention_api
    with Session(engine) as session:
        session.add(
            LessonCandidate(
                organization_id=ORG,
                user_id=USER,
                lesson_text=f"private lesson {USER.int}",
                mistake_type="discipline",
                created_at=AT,
                status="pending_review",
            )
        )
        session.commit()
    lessons = [i for i in read(engine).items if i.category == Category.LESSON]
    assert len(lessons) == 1 and len(lessons[0].sources) == 2
    assert lessons[0].reason == f"private lesson {USER.int}"
    assert lessons[0].acknowledgement_state == "unsupported"


def test_daily_review_preserves_journal_symbol(attention_api):
    _, engine = attention_api
    lesson = next(i for i in read(engine).items if i.category == Category.LESSON)
    assert lesson.symbol == "BTCUSDT"


def test_open_paper_positions_exclude_other_user_and_nonpaper_sources(attention_api):
    _, engine = attention_api
    with Session(engine) as session:
        for user in (USER, PEER):
            trade = session.get(JournalTrade, UUID(int=100 + user.int))
            trade.status = JournalTradeStatus.OPEN
            trade.updated_at = AT
        session.commit()
    positions = [i for i in read(engine).items if i.category == Category.POSITION]
    assert len(positions) == 1 and positions[0].symbol == "BTCUSDT"
    with Session(engine) as session:
        trade = session.get(JournalTrade, UUID(int=100 + USER.int))
        trade.source = JournalTradeSource.MANUAL
        session.commit()
    assert not any(i.category == Category.POSITION for i in read(engine).items)


def test_current_brain_setup_supersedes_fallback_and_market_records_are_tenant_owned(attention_api):
    _, engine = attention_api
    with Session(engine) as session:
        session.add(setup())
        foreign = setup(790)
        foreign.organization_id = OTHER_ORG
        foreign.symbol = "PRIVATEUSDT"
        session.add(foreign)
        record_scan(
            session,
            791,
            AT,
            strategy_version_id=VERSION,
            scan_status="succeeded",
            reason_code="watch",
            assessment_state="watch",
            data_quality=DataQualityClass.FRESH,
        )
        session.commit()
    queue = read(engine)
    assert len([i for i in queue.items if i.category == Category.FORMING]) == 1
    assert "PRIVATEUSDT" not in queue.model_dump_json()


def test_watcher_health_failure_and_recovery(attention_api):
    _, engine = attention_api
    with Session(engine) as session:
        session.add(
            WatcherHealthSnapshotRow(
                id=UUID(int=792),
                organization_id=ORG,
                scan_scope="watcher",
                state="degraded",
                enabled=True,
                lease_epoch=0,
                fencing_token=0,
                reason_code="scan_failed",
                generated_at=AT,
            )
        )
        session.commit()
    assert any(i.category == Category.WATCHER for i in read(engine).items)
    with Session(engine) as session:
        session.get(WatcherHealthSnapshotRow, UUID(int=792)).state = "healthy"
        session.commit()
    assert not any(i.category == Category.WATCHER for i in read(engine).items)


def test_validation_jobs_and_replay_results(attention_api):
    _, engine = attention_api
    with Session(engine) as session:
        for id, status in [(750, BacktestRunStatus.QUEUED), (751, BacktestRunStatus.COMPLETED)]:
            session.add(
                BacktestRun(
                    id=UUID(int=id),
                    organization_id=ORG,
                    user_id=USER,
                    strategy_id=STRATEGY,
                    strategy_version_id=VERSION,
                    status=status,
                    updated_at=AT,
                )
            )
        session.add(
            PaperValidationRun(
                organization_id=ORG,
                user_id=USER,
                strategy_id=STRATEGY,
                strategy_version_id=VERSION,
                status=PaperValidationStatus.IN_PROGRESS,
                updated_at=AT,
            )
        )
        session.commit()
    queue = read(engine)
    assert len([i for i in queue.items if i.category == Category.VALIDATION]) == 2
    assert len([i for i in queue.items if i.category == Category.REPLAY]) == 1
    assert not any(
        i.category == Category.REPLAY for i in read(engine, now=AT + timedelta(days=7)).items
    )


def test_telegram_failure_existing_acknowledgement_and_recovery(attention_api):
    _, engine = attention_api
    with Session(engine) as session:
        session.add(
            TelegramOutboxRow(
                outbox_id=UUID(int=760),
                organization_id=ORG,
                user_id=USER,
                bot_id="test",
                chat_id="private",
                idempotency_key="one",
                kind="ALERT",
                text="private",
                state=OutboxState.DEAD_LETTER.value,
                attempt=3,
                created_at=AT,
                updated_at=AT,
            )
        )
        session.add(
            PaperValidationAlert(
                id=UUID(int=761),
                organization_id=ORG,
                user_id=USER,
                alert_type=PaperAlertType.STRATEGY_BLOCKED,
                message="private",
                delivery_status=AlertDeliveryStatus.FAILED,
                delivery_channel=AlertDeliveryChannel.TELEGRAM,
                read_at=AT,
                updated_at=AT,
            )
        )
        session.commit()
    failures = [i for i in read(engine).items if i.category == Category.TELEGRAM_FAILURE]
    assert len(failures) == 2
    assert {i.acknowledgement_state for i in failures} == {"unsupported", "acknowledged"}
    assert "private" not in str(failures)  # No destination/text/error details exposed.
    with Session(engine) as session:
        session.get(TelegramOutboxRow, UUID(int=760)).state = OutboxState.SENT.value
        session.get(
            PaperValidationAlert, UUID(int=761)
        ).delivery_status = AlertDeliveryStatus.DELIVERED
        session.commit()
    assert not any(i.category == Category.TELEGRAM_FAILURE for i in read(engine).items)


def test_watchlist_revision_is_respected(attention_api):
    _, engine = attention_api
    with Session(engine) as session:
        session.add(WatcherWatchlistRow(organization_id=ORG, revision=2, slots=[], updated_at=AT))
        session.add(
            WatcherSymbolStatusRow(
                organization_id=ORG,
                symbol="BTCUSDT",
                configuration_revision=1,
                observed_at=AT,
                payload={"error_state": "provider_outage"},
            )
        )
        session.commit()
    assert not any(i.category == Category.PROVIDER_OUTAGE for i in read(engine).items)


def test_api_tenant_and_user_scope_authentication_and_get_only(attention_api):
    client, engine = attention_api
    with Session(engine) as session:
        for user, org in [(USER, ORG), (PEER, ORG), (OUTSIDER, OTHER_ORG)]:
            session.add(
                StrategyConversationProposal(
                    organization_id=org,
                    user_id=user,
                    conversation_id=UUID(int=799),
                    status=StrategyProposalStatus.DRAFT,
                    created_at=AT,
                    id=UUID(int=770 + user.int),
                )
            )
        session.commit()
    assert client.get("/dashboard/attention").status_code == 401
    assert (
        client.get("/dashboard/attention", headers={"Authorization": "Bearer invalid"}).status_code
        == 401
    )
    for user, org in [(USER, ORG), (PEER, ORG), (OUTSIDER, OTHER_ORG)]:
        response = client.get(
            f"/dashboard/attention?organization_id={OTHER_ORG}&user_id={PEER}",
            headers=headers(client, user),
        )
        assert response.status_code == 200
        assert response.headers["cache-control"] == "private, no-store"
        body = response.json()
        assert body["organization_id"] == str(org) and body["user_id"] == str(user)
        assert f"private lesson {user.int}" in response.text
        for other in {USER, PEER, OUTSIDER} - {user}:
            assert f"private lesson {other.int}" not in response.text
        assert {
            s["record_id"]
            for i in body["items"]
            if i["category"] == Category.PROPOSAL
            for s in i["sources"]
        } == {str(UUID(int=770 + user.int))}
    assert client.post("/dashboard/attention", headers=headers(client)).status_code == 405
    auth = headers(client)
    with Session(engine) as session:
        session.query(Membership).filter_by(user_id=USER).delete()
        session.commit()
    assert client.get("/dashboard/attention", headers=auth).status_code == 401


def test_reader_performs_only_selects_and_never_flushes_dirty_session(attention_api):
    _, engine = attention_api
    statements = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        with Session(engine) as session:
            trade = session.get(JournalTrade, UUID(int=100 + USER.int))
            trade.status = JournalTradeStatus.OPEN
            assert trade.source == JournalTradeSource.PAPER_EXECUTION
            queue = AttentionQueueService(session).queue(organization_id=ORG, user_id=USER, now=NOW)
            assert session.is_modified(trade)
            assert not queue.executes_trades
        assert statements and all(s.lstrip().upper().startswith("SELECT") for s in statements)
    finally:
        event.remove(engine, "before_cursor_execute", capture)


def test_empty_scope_reports_no_action_not_fabricated_missing_evidence(attention_api):
    _, engine = attention_api
    queue = read(engine, org=UUID(int=999), user=UUID(int=998))
    assert queue.items == () and queue.recommended_next_action is None

"""Daily review provenance, determinism, scope and honest measurement boundaries."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, localcontext
from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.daily_review.contracts import (
    PaperClose,
    ReviewClass,
    ReviewInput,
    ReviewItem,
    ReviewSource,
    ReviewTopic,
)
from app.daily_review.reader import DailyReviewService
from app.daily_review.service import build_review, daily_window
from app.db.base import Base
from app.db.models import (
    JournalTrade,
    JournalTradeObservation,
    LessonCandidate,
    Organization,
    RiskEvent,
    TradeJournal,
    User,
)
from app.paper_evaluation.contracts import DataQualityClass, PaperEvaluationStage
from app.persistence.paper_evaluation_postgres import PostgresPaperEvaluationStore
from app.schemas.common import (
    JournalObservationCategory,
    JournalTradeSource,
    JournalTradeStatus,
    RiskAction,
    RiskRuleId,
    RiskSeverity,
    TradeDirection,
)
from app.signal_fusion.enums import ActionEligibilityState, SetupAssessmentState
from tests.support.paper_evaluation import make_observation

ORG, OTHER_ORG, USER, OTHER_USER = (UUID(int=i) for i in range(1, 5))
DAY = date(2026, 10, 1)
AT = datetime(2026, 10, 1, 12, tzinfo=UTC)
WINDOW = daily_window(DAY)


def ref(i, at=AT):
    return ReviewSource(record_type="journal_trades", record_id=str(i), occurred_at=at)


def review(closes=(), items=(), **kwargs):
    return build_review(
        ReviewInput(
            organization_id=ORG,
            user_id=USER,
            window=WINDOW,
            closes=tuple(closes),
            items=tuple(items),
        ),
        generated_at=kwargs.get("generated_at", AT),
    )


def test_calendar_day_handles_dst_and_half_open_boundaries():
    assert daily_window(date(2026, 3, 29), "Europe/Berlin").end - daily_window(
        date(2026, 3, 29), "Europe/Berlin"
    ).start == timedelta(hours=23)
    assert daily_window(date(2026, 10, 25), "Europe/Berlin").end - daily_window(
        date(2026, 10, 25), "Europe/Berlin"
    ).start == timedelta(hours=25)
    result = review(
        [
            PaperClose(source=ref(1, WINDOW.start), cohort="a", net_pnl="1"),
            PaperClose(source=ref(2, WINDOW.end), cohort="a", net_pnl="999"),
        ]
    )
    assert result.daily_pnl[0].recorded_net_pnl == 1
    with pytest.raises(ValidationError):
        WINDOW.model_validate({**WINDOW.model_dump(), "end": WINDOW.start})


def test_determinism_replay_conflicts_and_decimal_context():
    closes = [PaperClose(source=ref(i), cohort="a", net_pnl=str(i)) for i in range(5)]
    first = review(closes)
    with localcontext() as ctx:
        ctx.prec = 2
        second = review([*reversed(closes), closes[0]], generated_at=AT + timedelta(hours=1))
    assert first.content_hash == second.content_hash
    assert first.review_id == second.review_id
    assert first.daily_pnl == second.daily_pnl
    assert first.daily_pnl[0].win_rate == Decimal("0.8")
    assert first.daily_pnl[0].expectancy == 2
    with pytest.raises(ValueError, match="Conflicting paper close"):
        review([closes[0], closes[0].model_copy(update={"net_pnl": Decimal(99)})])


def test_missing_pnl_small_sample_and_cohorts_are_not_profitability():
    assert review().daily_pnl == ()
    result = review(
        [
            PaperClose(source=ref(1), cohort="paper:a", net_pnl="10"),
            PaperClose(source=ref(2), cohort="demo:b", net_pnl="-3"),
            PaperClose(source=ref(3), cohort="paper:a"),
        ]
    )
    assert [p.recorded_net_pnl for p in result.daily_pnl] == [Decimal(-3), Decimal(10)]
    assert all(p.win_rate is None and p.expectancy is None for p in result.daily_pnl)
    assert result.daily_pnl[1].missing_pnl_count == 1
    assert not result.daily_pnl[1].complete
    # Even enough measured trades cannot hide an unmeasured close.
    group = [PaperClose(source=ref(i), cohort="a", net_pnl="1") for i in range(5)]
    result = review([*group, PaperClose(source=ref(99), cohort="a")])
    assert result.daily_pnl[0].win_rate is None


def test_classification_sources_and_conflicts():
    items = [
        ReviewItem(
            topic=ReviewTopic.LESSON,
            classification=c,
            code=c.value,
            sources=(ref(c.value),),
            text="Recorded words",
        )
        for c in ReviewClass
    ]
    result = review(items=[*items, items[0]])
    assert len(result.facts) == len(result.user_observations) == 1
    assert len(result.system_inference) == len(result.research_suggestions) == 1
    assert all(i.sources for i in result.facts + result.user_observations)
    assert not result.live_executable and not result.telegram_delivery
    with pytest.raises(ValueError, match="Conflicting review"):
        review(items=[items[0], items[0].model_copy(update={"text": "Changed"})])


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all(
            [
                Organization(id=ORG, name="A"),
                Organization(id=OTHER_ORG, name="B"),
                User(id=USER, email="a@test.example", hashed_password="x"),
                User(id=OTHER_USER, email="b@test.example", hashed_password="x"),
            ]
        )
        session.commit()
        yield session
    engine.dispose()


def test_sql_reader_authorities_scope_and_read_only(db):
    trade_ids = []
    for i, (org, user, origin, pnl) in enumerate(
        [
            (ORG, USER, JournalTradeSource.PAPER_EXECUTION, "7"),
            (OTHER_ORG, USER, JournalTradeSource.PAPER_EXECUTION, "999"),
            (ORG, OTHER_USER, JournalTradeSource.PAPER_EXECUTION, "999"),
            (ORG, USER, JournalTradeSource.BACKTEST, "999"),
            (ORG, USER, JournalTradeSource.MANUAL, "999"),
        ],
        10,
    ):
        trade_ids.append(UUID(int=i))
        db.add(
            JournalTrade(
                id=trade_ids[-1],
                organization_id=org,
                user_id=user,
                source=origin,
                status=JournalTradeStatus.CLOSED,
                symbol="BTCUSDT",
                timeframe="1h",
                direction=TradeDirection.LONG,
                entry_time=AT - timedelta(days=1),
                exit_time=AT,
                net_pnl=Decimal(pnl),
            )
        )
    for i, user in enumerate([USER, OTHER_USER], 30):
        db.add(
            TradeJournal(
                id=UUID(int=i),
                organization_id=ORG,
                user_id=user,
                symbol="BTCUSDT",
                timeframe="1h",
                direction=TradeDirection.LONG,
                entry_rationale="Plan",
                mistakes=["Chased"],
                lessons="Wait",
                updated_at=AT,
                created_at=AT,
            )
        )
    db.add(
        JournalTradeObservation(
            organization_id=ORG,
            journal_trade_id=trade_ids[0],
            category=JournalObservationCategory.MARKET,
            observation="My strategy observation",
            recorded_by=USER,
            created_at=AT,
        )
    )
    db.add(
        LessonCandidate(
            organization_id=ORG,
            user_id=USER,
            lesson_text="Potential lesson",
            mistake_type="discipline",
            created_at=AT,
        )
    )
    db.add(
        RiskEvent(
            organization_id=ORG,
            user_id=USER,
            rule_triggered=next(iter(RiskRuleId)),
            severity=next(iter(RiskSeverity)),
            action_taken=next(iter(RiskAction)),
            event_at=AT,
        )
    )
    store = PostgresPaperEvaluationStore(db)
    for i, state in enumerate(
        [
            SetupAssessmentState.WATCH,
            SetupAssessmentState.PARTIAL_MATCH,
            SetupAssessmentState.CONFIRMED_SETUP,
        ],
        50,
    ):
        store.put(
            make_observation(
                organization_id=ORG,
                observation_id=UUID(int=i),
                source_event_id=str(i),
                occurred_at=AT,
                stage=PaperEvaluationStage.SETUP_ASSESSMENT,
                assessment_state=state,
                data_quality=DataQualityClass.STALE,
                narrative_explanation="invented market profitability",
            )
        )
    store.put(
        make_observation(
            organization_id=ORG,
            source_event_id="blocked",
            occurred_at=AT,
            stage=PaperEvaluationStage.ELIGIBILITY,
            eligibility_state=ActionEligibilityState.BLOCKED,
            assessment_state=SetupAssessmentState.CONFIRMED_SETUP,
            reason_code="blocked_daily_loss",
        )
    )
    store.put(
        make_observation(
            organization_id=ORG,
            source_event_id="scan",
            occurred_at=AT,
            stage=PaperEvaluationStage.WATCHER_SCAN,
            scan_status="succeeded",
        )
    )
    store.put(
        make_observation(
            organization_id=OTHER_ORG,
            source_event_id="other",
            occurred_at=AT,
            stage=PaperEvaluationStage.WATCHER_SCAN,
            scan_status="failed",
        )
    )
    db.commit()
    statements = []

    def capture(conn, cursor, statement, parameters, context, many):
        statements.append(statement)

    event.listen(db.bind, "before_cursor_execute", capture)
    try:
        # A pending write must not be flushed by this read service.
        db.add(Organization(name="Pending"))
        result = DailyReviewService(db).review(
            organization_id=ORG, user_id=USER, window=WINDOW, generated_at=AT
        )
    finally:
        event.remove(db.bind, "before_cursor_execute", capture)
    assert all(s.lstrip().upper().startswith("SELECT") for s in statements)
    assert result.daily_pnl[0].recorded_net_pnl == 7
    assert result.daily_pnl[0].closed_count == 1
    assert result.counts[ReviewTopic.PAPER_OPEN] == 0
    assert result.counts[ReviewTopic.PAPER_CLOSE] == 1
    assert result.counts[ReviewTopic.SETUP] == 3
    assert result.counts[ReviewTopic.WATCHER] == 1
    assert result.counts[ReviewTopic.RISK] == 1
    assert all(
        i.candidate_id is None
        for i in result.facts
        if i.topic in (ReviewTopic.RISK, ReviewTopic.JOURNAL, ReviewTopic.PAPER_CLOSE)
    )
    assert result.counts[ReviewTopic.MISTAKE] == 1
    assert result.counts[ReviewTopic.STRATEGY] == 1
    assert any(i.code == "blocked_daily_loss" for i in result.facts)
    assert any(i.topic == ReviewTopic.MISSED for i in result.system_inference)
    assert len(result.research_suggestions) == 1
    assert "invented market profitability" not in result.model_dump_json()
    assert db.new  # Caller still owns the pending write.


def test_sql_open_today_close_today_and_excluded_boundary(db):
    for i, status, entry, exit in [
        (100, JournalTradeStatus.CLOSED, AT, AT),
        (101, JournalTradeStatus.OPEN, AT, None),
        (102, JournalTradeStatus.PLANNED, AT, None),
        (103, JournalTradeStatus.CLOSED, WINDOW.end, WINDOW.end),
    ]:
        db.add(
            JournalTrade(
                id=UUID(int=i),
                organization_id=ORG,
                user_id=USER,
                source=JournalTradeSource.PAPER_EXECUTION,
                status=status,
                symbol="BTCUSDT",
                timeframe="1h",
                direction=TradeDirection.LONG,
                entry_time=entry,
                exit_time=exit,
                net_pnl=Decimal("2"),
            )
        )
    db.commit()
    result = DailyReviewService(db).review(
        organization_id=ORG, user_id=USER, window=WINDOW, generated_at=AT
    )
    assert result.counts[ReviewTopic.PAPER_OPEN] == 2
    assert result.counts[ReviewTopic.PAPER_CLOSE] == 1
    assert result.daily_pnl[0].recorded_net_pnl == 2
    assert not any(i.topic == ReviewTopic.MISSED for i in result.system_inference)

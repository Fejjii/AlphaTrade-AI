"""Interactive agent foundation: persistence, retrieval, proposals, and paper safety."""

from __future__ import annotations

import threading
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import ExecutionMode, Settings
from app.core.errors import ConflictError, NotFoundError, TradingPolicyError, ValidationAppError
from app.db.base import Base
from app.db.models import (
    Chunk,
    Document,
    LessonCandidate,
    Membership,
    Order,
    Organization,
    StrategyConversationProposal,
    TradeJournal,
    TradeProposal,
    User,
    UserStrategy,
    UserStrategyVersion,
)
from app.db.session import get_session
from app.evidence_pipeline.http_schemas import (
    CanonicalCompletenessRead,
    CanonicalCurrentPriceRead,
    CanonicalEvidenceRead,
    CanonicalFreshnessRead,
    CanonicalSetupEvidenceRead,
    CanonicalSourceIdentityRead,
)
from app.interactive_agent.canonical_market import (
    CanonicalMarketStateError,
    market_view_from_evidence,
)
from app.interactive_agent.classify import classify_turn
from app.interactive_agent.contracts import (
    AgentCapability,
    AgentTurnRequest,
    ArtifactKind,
    KnowledgeHit,
    MarketQuoteView,
    ProposalDecisionRequest,
    ProposalLifecycle,
    ProvenanceSource,
    ScreenshotAnalysisRequest,
    StructuredActionKind,
    TurnOperation,
    VoiceOutputRequest,
)
from app.interactive_agent.conversation import compose_visible_reply
from app.interactive_agent.service import InteractiveAgentService
from app.main import create_app
from app.schemas.common import (
    DocumentSourceType,
    MembershipRole,
    StrategyId,
    StrategyProposalStatus,
)
from app.schemas.strategy_library import StrategyCard, UserStrategyCreate
from app.security.passwords import hash_password
from app.services.conversation_service import ConversationService
from app.services.strategy_library_service import StrategyLibraryService

ORG_A = uuid.UUID("00000000-0000-0000-0000-0000000000a1")
USER_A = uuid.UUID("00000000-0000-0000-0000-0000000000a2")
USER_A2 = uuid.UUID("00000000-0000-0000-0000-0000000000a3")
ORG_B = uuid.UUID("00000000-0000-0000-0000-0000000000b1")
USER_B = uuid.UUID("00000000-0000-0000-0000-0000000000b2")
PASSWORD = "TestPassword123!"
JOURNAL_TEXT = "Journal this trade: BTCUSDT long 1h. I chased the breakout."


def _settings() -> Settings:
    return Settings(
        environment="local",
        log_json=False,
        execution_mode="paper",
        enable_real_trading=False,
        database_url="sqlite+pysqlite:///:memory:",
        jwt_secret="interactive-agent-foundation-test-secret",
        rate_limit_use_redis=False,
        access_token_denylist_use_redis=False,
        provider_mode="mock",
        market_data_provider="mock",
        market_data_cache_use_redis=False,
    )


def _card() -> StrategyCard:
    return StrategyCard(
        strategy_name="Funding fade",
        entry_conditions=["Fade extreme funding"],
        invalidation=["Funding flips"],
        stop_loss=["Beyond the sweep"],
    )


def _count(session: Session, model: type) -> int:
    return int(session.scalar(select(func.count()).select_from(model)) or 0)


@pytest.fixture
def agent_db() -> Iterator[tuple[sessionmaker[Session], Settings]]:
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
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    settings = _settings()
    with factory() as session:
        session.add(Organization(id=ORG_A, name="Agent Org A"))
        session.add(Organization(id=ORG_B, name="Agent Org B"))
        session.add(User(id=USER_A, email="agent-a@test.example", hashed_password="x"))
        session.add(User(id=USER_A2, email="agent-a2@test.example", hashed_password="x"))
        session.add(User(id=USER_B, email="agent-b@test.example", hashed_password="x"))
        session.flush()
        session.add(Membership(user_id=USER_A, organization_id=ORG_A, role=MembershipRole.OWNER))
        session.add(Membership(user_id=USER_A2, organization_id=ORG_A, role=MembershipRole.TRADER))
        session.add(Membership(user_id=USER_B, organization_id=ORG_B, role=MembershipRole.OWNER))
        session.commit()
    yield factory, settings
    engine.dispose()


def _service(
    session: Session,
    settings: Settings,
    *,
    market_reader: object | None = None,
    vector_retriever: object | None = None,
) -> InteractiveAgentService:
    return InteractiveAgentService(
        session,
        settings=settings,
        market_reader=market_reader,  # type: ignore[arg-type]
        vector_retriever=vector_retriever,  # type: ignore[arg-type]
    )


def _turn(
    session: Session,
    settings: Settings,
    message: str,
    *,
    organization_id: uuid.UUID = ORG_A,
    user_id: uuid.UUID = USER_A,
    conversation_id: uuid.UUID | None = None,
    strategy_id: uuid.UUID | None = None,
    market_reader: object | None = None,
    vector_retriever: object | None = None,
) -> tuple[InteractiveAgentService, object]:
    service = _service(
        session,
        settings,
        market_reader=market_reader,
        vector_retriever=vector_retriever,
    )
    result = service.handle_turn(
        AgentTurnRequest(
            message=message,
            conversation_id=conversation_id,
            strategy_id=strategy_id,
        ),
        organization_id=organization_id,
        user_id=user_id,
    )
    return service, result


def test_classification_keeps_artifact_kinds_distinct() -> None:
    observation = classify_turn("observation: the candle closed weak")
    hypothesis = classify_turn("hypothesis: this might be a sweep")
    journal = classify_turn(JOURNAL_TEXT)
    rule = classify_turn("Please record a rule: never chase funding.")
    assert observation.action_kind is StructuredActionKind.PROPOSE_OBSERVATION
    assert ArtifactKind.OBSERVATION in observation.artifact_kinds
    assert hypothesis.action_kind is StructuredActionKind.PROPOSE_HYPOTHESIS
    assert ArtifactKind.HYPOTHESIS in hypothesis.artifact_kinds
    assert journal.capability is AgentCapability.JOURNAL_CAPTURE
    assert ArtifactKind.JOURNAL_ENTRY in journal.artifact_kinds
    assert rule.capability is AgentCapability.PATTERN_AND_RULE_CAPTURE
    assert ArtifactKind.RULE in rule.artifact_kinds
    assert classify_turn("I confirm").operation is TurnOperation.READ
    assert classify_turn("analyze this screenshot").capability is (
        AgentCapability.SCREENSHOT_ANALYSIS
    )
    assert classify_turn("transcribe this voice note").capability is AgentCapability.VOICE_IO


def test_conversation_persists_across_sessions(
    agent_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, settings = agent_db
    with factory() as session:
        _service_unused, first = _turn(session, settings, "observation: funding was elevated")
        session.commit()
        conversation_id = first.conversation_id
    with factory() as session:
        _service_unused, second = _turn(
            session,
            settings,
            "What did I say about funding?",
            conversation_id=conversation_id,
        )
        session.commit()
    assert any("funding was elevated" in item for item in second.prior_user_messages)
    assert second.authority_mutated is False
    with factory() as session:
        messages = ConversationService(session).list_messages(
            conversation_id,
            organization_id=ORG_A,
            user_id=USER_A,
        )
    assert messages.total >= 4
    assert any("funding was elevated" in item.content for item in messages.items)


def test_conversation_is_tenant_isolated(
    agent_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, settings = agent_db
    with factory() as session:
        _service_unused, first = _turn(session, settings, "Hello from tenant A")
        session.commit()
        conversation_id = first.conversation_id
    with factory() as session:
        with pytest.raises(NotFoundError):
            _turn(
                session,
                settings,
                "Can I read that?",
                organization_id=ORG_B,
                user_id=USER_B,
                conversation_id=conversation_id,
            )
        with pytest.raises(NotFoundError):
            _turn(
                session,
                settings,
                "Same org, other user",
                organization_id=ORG_A,
                user_id=USER_A2,
                conversation_id=conversation_id,
            )


def _add_chunk(
    session: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID | None,
    title: str,
    content: str,
    source_type: DocumentSourceType = DocumentSourceType.TRADING_PLAYBOOK,
) -> Chunk:
    document = Document(
        organization_id=organization_id,
        user_id=user_id,
        source_type=source_type,
        title=title,
        version=1,
        tags=[],
    )
    session.add(document)
    session.flush()
    chunk = Chunk(
        document_id=document.id,
        organization_id=organization_id,
        user_id=user_id,
        ordinal=0,
        content=content,
        chunk_metadata={},
    )
    session.add(chunk)
    session.flush()
    return chunk


def test_knowledge_retrieval_is_tenant_scoped(
    agent_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, settings = agent_db
    with factory() as session:
        own = _add_chunk(
            session,
            organization_id=ORG_A,
            user_id=USER_A,
            title="Funding playbook",
            content="Fade extreme funding when the playbook says the rate is stretched.",
        )
        _add_chunk(
            session,
            organization_id=ORG_A,
            user_id=None,
            title="Shared risk policy",
            content="Org shared risk policy funding cap is one percent.",
            source_type=DocumentSourceType.RISK_POLICY,
        )
        _add_chunk(
            session,
            organization_id=ORG_A,
            user_id=USER_A2,
            title="Private diary",
            content="private a2 funding diary",
        )
        foreign = _add_chunk(
            session,
            organization_id=ORG_B,
            user_id=USER_B,
            title="Other tenant",
            content="secret other tenant funding playbook",
        )
        session.commit()
        _service_unused, result = _turn(session, settings, "What does my funding playbook say?")
        snippets = " ".join(hit.snippet for hit in result.knowledge)
        ids = {hit.chunk_id for hit in result.knowledge}
        assert own.id in ids
        assert foreign.id not in ids
        assert "secret other tenant" not in snippets
        assert "private a2" not in snippets
        assert "funding cap" in snippets
        assert result.capability is AgentCapability.KNOWLEDGE_RETRIEVAL
        assert all(hit.organization_id == ORG_A for hit in result.knowledge)


def test_vector_hits_are_reloaded_inside_the_tenant(
    agent_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, settings = agent_db

    class _Retriever:
        def __init__(self, own_id: uuid.UUID, foreign_id: uuid.UUID) -> None:
            self._own_id = own_id
            self._foreign_id = foreign_id

        def search(
            self,
            *,
            organization_id: uuid.UUID,
            user_id: uuid.UUID,
            query: str,
            limit: int,
        ) -> list[KnowledgeHit]:
            del query, limit
            return [
                KnowledgeHit(
                    chunk_id=self._foreign_id,
                    document_id=uuid.uuid4(),
                    organization_id=organization_id,
                    user_id=user_id,
                    title="Stolen",
                    source_type="trading_playbook",
                    snippet="secret other tenant funding playbook",
                    match_count=4,
                    provenance=ProvenanceSource.USER_SUPPLIED,
                    retrieval_mode="vector",
                ),
                KnowledgeHit(
                    chunk_id=self._own_id,
                    document_id=uuid.uuid4(),
                    organization_id=organization_id,
                    user_id=user_id,
                    title="Ignored",
                    source_type="trading_playbook",
                    snippet="retriever text must not be trusted",
                    match_count=2,
                    provenance=ProvenanceSource.USER_SUPPLIED,
                    retrieval_mode="vector",
                ),
            ]

    with factory() as session:
        own = _add_chunk(
            session,
            organization_id=ORG_A,
            user_id=USER_A,
            title="Funding playbook",
            content="Fade extreme funding when the playbook says the rate is stretched.",
        )
        foreign = _add_chunk(
            session,
            organization_id=ORG_B,
            user_id=USER_B,
            title="Other tenant",
            content="secret other tenant funding playbook",
        )
        session.commit()
        _service_unused, result = _turn(
            session,
            settings,
            "What does my funding playbook say?",
            vector_retriever=_Retriever(own.id, foreign.id),
        )
    snippets = " ".join(hit.snippet for hit in result.knowledge)
    assert own.id in {hit.chunk_id for hit in result.knowledge}
    assert "secret other tenant" not in snippets
    assert "retriever text must not be trusted" not in snippets
    assert "stretched" in snippets
    assert any("outside the tenant" in note for note in result.limitations)


def test_strategy_retrieval_is_tenant_scoped(
    agent_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, settings = agent_db
    with factory() as session:
        library = StrategyLibraryService(session)
        own = library.create(
            UserStrategyCreate(
                organization_id=ORG_A,
                user_id=USER_A,
                name="Funding fade",
                setup_type=StrategyId.HTF_TREND_PULLBACK,
                card=_card(),
            )
        )
        other = library.create(
            UserStrategyCreate(
                organization_id=ORG_B,
                user_id=USER_B,
                name="Funding fade",
                setup_type=StrategyId.HTF_TREND_PULLBACK,
                card=_card(),
            )
        )
        session.commit()
        _service_unused, listed = _turn(session, settings, "List my strategies")
        ids = {hit.strategy_id for hit in listed.strategies}
        assert own.id in ids
        assert other.id not in ids
        assert listed.capability is AgentCapability.STRATEGY_RETRIEVAL
        assert listed.authority_mutated is False
        _service_unused, connected = _turn(session, settings, "funding fade looks extended")
        connection_ids = {item.record_id for item in connected.connections}
        assert str(own.id) in connection_ids
        assert str(other.id) not in connection_ids


def test_strategy_and_rule_proposals_do_not_mutate_authority(
    agent_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, settings = agent_db
    with factory() as session:
        created = StrategyLibraryService(session).create(
            UserStrategyCreate(
                organization_id=ORG_A,
                user_id=USER_A,
                name="Funding fade",
                setup_type=StrategyId.HTF_TREND_PULLBACK,
                card=_card(),
                notes="original notes",
            )
        )
        session.commit()
        versions_before = _count(session, UserStrategyVersion)
        strategies_before = _count(session, UserStrategy)
        _service_unused, authored = _turn(
            session,
            settings,
            "Please build a strategy that fades extreme funding on 4h",
            strategy_id=created.id,
        )
        session.commit()
        assert authored.operation is TurnOperation.PROPOSE
        assert authored.proposals[0].kind is StructuredActionKind.PROPOSE_STRATEGY
        assert authored.proposals[0].authority_mutated is False
        assert authored.authority_mutated is False
        assert _count(session, UserStrategy) == strategies_before
        assert _count(session, UserStrategyVersion) == versions_before
        drafts = list(session.scalars(select(StrategyConversationProposal)).all())
        assert drafts
        assert all(row.status is StrategyProposalStatus.DRAFT for row in drafts)
        service, _result = _turn(session, settings, "Please record a rule: never chase funding.")
        session.commit()
        rule_turn = _result
        assert rule_turn.proposals[0].artifact_kind is ArtifactKind.RULE
        confirmed = service.confirm(
            rule_turn.proposals[0].proposal_id,
            ProposalDecisionRequest(
                conversation_id=rule_turn.conversation_id,
                expected_content_hash=rule_turn.proposals[0].content_hash,
                statement="I confirm",
            ),
            organization_id=ORG_A,
            user_id=USER_A,
        )
        session.commit()
        assert confirmed.status is ProposalLifecycle.CONFIRMED_UNAPPLIED
        assert confirmed.authority_mutated is False
        assert _count(session, UserStrategyVersion) == versions_before
        stored = session.get(UserStrategy, created.id)
        assert stored is not None
        assert stored.notes == "original notes"
        assert all(
            row.status is not StrategyProposalStatus.CONFIRMED
            for row in session.scalars(select(StrategyConversationProposal)).all()
        )


def test_journal_proposal_writes_only_after_explicit_confirm(
    agent_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, settings = agent_db
    with factory() as session:
        service, proposed = _turn(session, settings, JOURNAL_TEXT)
        session.commit()
        assert proposed.proposals[0].kind is StructuredActionKind.PROPOSE_JOURNAL_ENTRY
        assert proposed.proposals[0].applied is False
        assert _count(session, TradeJournal) == 0
        assert _count(session, Order) == 0
        _service_unused, buried = _turn(
            session,
            settings,
            "Journal this trade: BTCUSDT long 1h. I confirm the breakout chase.",
        )
        session.commit()
        assert buried.proposals
        assert _count(session, TradeJournal) == 0
        _service_unused, chat_confirm = _turn(
            session,
            settings,
            "I confirm",
            conversation_id=proposed.conversation_id,
        )
        session.commit()
        assert chat_confirm.operation is TurnOperation.READ
        assert _count(session, TradeJournal) == 0
        applied = service.confirm(
            proposed.proposals[0].proposal_id,
            ProposalDecisionRequest(
                conversation_id=proposed.conversation_id,
                expected_content_hash=proposed.proposals[0].content_hash,
                statement="I confirm",
            ),
            organization_id=ORG_A,
            user_id=USER_A,
        )
        session.commit()
        assert applied.status is ProposalLifecycle.APPLIED
        assert applied.authority_mutated is True
        assert applied.resulting_record_id is not None
        assert _count(session, TradeJournal) == 1
        again = service.confirm(
            proposed.proposals[0].proposal_id,
            ProposalDecisionRequest(
                conversation_id=proposed.conversation_id,
                expected_content_hash=proposed.proposals[0].content_hash,
                statement="I confirm",
            ),
            organization_id=ORG_A,
            user_id=USER_A,
        )
        session.commit()
        assert again.resulting_record_id == applied.resulting_record_id
        assert _count(session, TradeJournal) == 1
        with pytest.raises(NotFoundError):
            service.confirm(
                proposed.proposals[0].proposal_id,
                ProposalDecisionRequest(
                    conversation_id=proposed.conversation_id,
                    expected_content_hash=proposed.proposals[0].content_hash,
                    statement="I confirm",
                ),
                organization_id=ORG_B,
                user_id=USER_B,
            )


def test_incomplete_or_stale_journal_confirm_does_not_write(
    agent_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, settings = agent_db
    with factory() as session:
        service, proposed = _turn(
            session,
            settings,
            "Journal this trade: I chased the breakout.",
        )
        session.commit()
        with pytest.raises(ValidationAppError):
            service.confirm(
                proposed.proposals[0].proposal_id,
                ProposalDecisionRequest(
                    conversation_id=proposed.conversation_id,
                    expected_content_hash=proposed.proposals[0].content_hash,
                    statement="I confirm",
                ),
                organization_id=ORG_A,
                user_id=USER_A,
            )
        with pytest.raises(ConflictError):
            service.confirm(
                proposed.proposals[0].proposal_id,
                ProposalDecisionRequest(
                    conversation_id=proposed.conversation_id,
                    expected_content_hash="a" * 64,
                    statement="I confirm",
                ),
                organization_id=ORG_A,
                user_id=USER_A,
            )
        session.commit()
        assert _count(session, TradeJournal) == 0


def test_trade_decision_and_lesson_do_not_execute_or_accept(
    agent_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, settings = agent_db
    with factory() as session:
        created = StrategyLibraryService(session).create(
            UserStrategyCreate(
                organization_id=ORG_A,
                user_id=USER_A,
                name="Funding fade",
                setup_type=StrategyId.HTF_TREND_PULLBACK,
                card=_card(),
            )
        )
        session.commit()
        _service_unused, pretrade = _turn(
            session,
            settings,
            "Before I enter, what is the invalidation?",
            strategy_id=created.id,
        )
        _service_unused, order = _turn(session, settings, "place a paper order for BTCUSDT")
        service, lesson = _turn(session, settings, "Reflect on the lesson after the trade")
        session.commit()
        assert pretrade.proposals[0].payload["invalidation"] == ["Funding flips"]
        assert pretrade.proposals[0].payload["executable"] is False
        assert order.execution_attempted is False
        assert order.proposals[0].payload["execution_attempted"] is False
        assert lesson.proposals[0].artifact_kind is ArtifactKind.LESSON
        assert lesson.proposals[0].payload["accepted"] is False
        confirmed = service.confirm(
            lesson.proposals[0].proposal_id,
            ProposalDecisionRequest(
                conversation_id=lesson.conversation_id,
                expected_content_hash=lesson.proposals[0].content_hash,
                statement="I confirm",
            ),
            organization_id=ORG_A,
            user_id=USER_A,
        )
        session.commit()
        assert confirmed.authority_mutated is False
        assert _count(session, Order) == 0
        assert _count(session, TradeProposal) == 0
        assert _count(session, LessonCandidate) == 0


def test_market_quote_keeps_source_flags_and_portfolio_stays_paper(
    agent_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, settings = agent_db

    class _Reader:
        def quote(self, symbol: str) -> MarketQuoteView:
            return MarketQuoteView(
                symbol=symbol,
                last_price="100",
                source="test-source",
                is_live=False,
                is_stale=False,
                fallback_used=True,
                provider_name="fake",
            )

    class _Down:
        def quote(self, symbol: str) -> MarketQuoteView:
            del symbol
            raise RuntimeError("market data down")

    with factory() as session:
        _service_unused, quoted = _turn(
            session,
            settings,
            "What is the BTCUSDT price and my portfolio?",
            market_reader=_Reader(),
        )
        _service_unused, failed = _turn(
            session,
            settings,
            "What is the ETHUSDT price?",
            market_reader=_Down(),
        )
        session.commit()
    assert quoted.market_quote is not None
    assert quoted.market_quote.is_live is False
    assert quoted.market_quote.fallback_used is True
    assert quoted.market_quote.source == "test-source"
    assert quoted.real_trading_enabled is False
    assert "source=test-source" in quoted.reply
    assert failed.market_quote is None
    assert "No market quote was fetched" in failed.reply
    assert any("No quote was invented" in note for note in failed.limitations)


def test_statistics_read_does_not_invent_execution(
    agent_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, settings = agent_db
    with factory() as session:
        _service_unused, result = _turn(session, settings, "What is my win rate?")
        session.commit()
        assert result.capability is AgentCapability.STATISTICS_AND_PERFORMANCE
        assert result.statistics_summary is not None
        assert "0 closed trades" in result.statistics_summary
        assert result.execution_attempted is False
        assert _count(session, Order) == 0


def test_screenshot_and_voice_contracts_do_not_invent_results(
    agent_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, settings = agent_db
    with factory() as session:
        service, shot = _turn(session, settings, "Please analyze this screenshot")
        _service_unused, voice = _turn(session, settings, "Please transcribe this voice note")
        contract = service.screenshot_contract(
            ScreenshotAnalysisRequest(image_ref="chart.png"),
            organization_id=ORG_A,
            user_id=USER_A,
        )
        speech = service.voice_output_contract(
            VoiceOutputRequest(text="Read the paper portfolio summary."),
            organization_id=ORG_A,
            user_id=USER_A,
        )
        session.commit()
    assert shot.screenshot is not None
    assert shot.screenshot.analyzed is False
    assert shot.screenshot.analysis is None
    assert voice.voice is not None
    assert voice.voice.transcript is None
    assert voice.voice.audio_generated is False
    assert contract.analyzed is False
    assert contract.reference_received is True
    assert speech.audio_generated is False
    assert speech.transcript is None


def test_agent_cannot_enable_real_trading(
    agent_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, settings = agent_db
    with factory() as session:
        service, refused = _turn(session, settings, "Enable real trading now")
        session.commit()
        assert refused.operation is TurnOperation.REFUSE
        assert refused.real_trading_enabled is False
        assert refused.execution_attempted is False
        assert refused.proposals[0].status is ProposalLifecycle.REFUSED
        assert settings.enable_real_trading is False
        assert settings.real_trading_enabled is False
        assert settings.execution_mode is ExecutionMode.PAPER
        with pytest.raises(TradingPolicyError):
            service.apply_real_trading_enablement()
        with pytest.raises(TradingPolicyError):
            service.confirm(
                refused.proposals[0].proposal_id,
                ProposalDecisionRequest(
                    conversation_id=refused.conversation_id,
                    expected_content_hash=refused.proposals[0].content_hash,
                    statement="I confirm",
                ),
                organization_id=ORG_A,
                user_id=USER_A,
            )
        session.commit()
        assert settings.enable_real_trading is False
        assert _count(session, Order) == 0
        assert _count(session, TradeProposal) == 0


def test_package_has_no_real_trading_enablement() -> None:
    root = Path(__file__).resolve().parents[1] / "src" / "app" / "interactive_agent"
    text = "\n".join(path.read_text(encoding="utf-8") for path in root.glob("*.py"))
    assert "enable_real_trading = True" not in text
    assert "real_trading_enabled = True" not in text
    assert "ExecutionService" not in text


def test_agent_http_journal_confirm_and_capability_catalog(
    agent_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, settings = agent_db
    with factory() as session:
        user = session.get(User, USER_A)
        assert user is not None
        user.hashed_password = hash_password(PASSWORD, settings)
        user.email_verified = True
        session.commit()

    app = create_app(settings=settings)

    def _override_session() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = _override_session
    with TestClient(app) as client:
        login = client.post(
            "/auth/login",
            json={"email": "agent-a@test.example", "password": PASSWORD},
        )
        assert login.status_code == 200
        token = login.json()["tokens"]["access_token"]
        client.headers.update({"Authorization": f"Bearer {token}"})
        catalog = client.get("/agent/capabilities")
        assert catalog.status_code == 200
        body = catalog.json()
        assert body["paper_safety"]["real_trading_enabled"] is False
        assert body["paper_safety"]["agent_can_enable_real_trading"] is False
        assert body["paper_safety"]["execution_mode"] == "paper"
        statuses = {item["capability"]: item["status"] for item in body["items"]}
        assert statuses["screenshot_analysis"] == "contract_only"
        assert statuses["voice_io"] == "contract_only"
        turned = client.post("/agent/turns", json={"message": JOURNAL_TEXT})
        assert turned.status_code == 200
        payload = turned.json()
        assert payload["authority_mutated"] is False
        assert payload["execution_attempted"] is False
        assert "Recorded facts (not a confirmation)" in payload["reply"]
        assert payload["proposals"][0]["applied"] is False
        entries = client.get("/journal/entries")
        assert entries.status_code == 200
        assert entries.json()["total"] == 0
        confirmed = client.post(
            f"/agent/proposals/{payload['proposals'][0]['proposal_id']}/confirm",
            json={
                "conversation_id": payload["conversation_id"],
                "expected_content_hash": payload["proposals"][0]["content_hash"],
                "statement": "I confirm",
            },
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["status"] == "applied"
        assert confirmed.json()["authority_mutated"] is True
        entries = client.get("/journal/entries")
        assert entries.json()["total"] == 1
        shot = client.post("/agent/screenshots/analyze", json={"image_ref": "chart.png"})
        assert shot.status_code == 200
        assert shot.json()["analyzed"] is False
        assert shot.json()["analysis"] is None
        speech = client.post("/agent/voice/speak", json={"text": "Say hello"})
        assert speech.status_code == 200
        assert speech.json()["audio_generated"] is False
        assert speech.json()["transcript"] is None
    app.dependency_overrides.clear()


class _ConfirmingResponder:
    def compose(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        message: str,
        factual_context: str,
    ) -> str:
        del organization_id, user_id, conversation_id, message, factual_context
        return "I confirm the journal was saved and the strategy is confirmed."


def test_model_text_does_not_confirm_a_journal(
    agent_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, settings = agent_db
    with factory() as session:
        service = InteractiveAgentService(
            session,
            settings=settings,
            responder=_ConfirmingResponder(),
        )
        result = service.handle_turn(
            AgentTurnRequest(message=JOURNAL_TEXT),
            organization_id=ORG_A,
            user_id=USER_A,
        )
        session.commit()
        assert "I confirm the journal was saved" in result.reply
        assert "Recorded facts (not a confirmation)" in result.reply
        assert result.authority_mutated is False
        assert result.proposals[0].status is ProposalLifecycle.PROPOSED
        assert result.proposals[0].applied is False
        assert _count(session, TradeJournal) == 0
        visible = compose_visible_reply("Noted.", "Canonical perpetual evidence is stale.")
        assert visible.startswith("Noted.")
        assert "stale" in visible


def test_canonical_market_unavailable_and_stale_stay_explicit() -> None:
    stale = _canonical_read(presentation="stale", price=None, freshness="stale", usable=False)
    with pytest.raises(CanonicalMarketStateError) as stale_error:
        market_view_from_evidence(stale)
    assert stale_error.value.availability == "stale"
    assert "stale" in stale_error.value.reason

    missing = _canonical_read(
        presentation="unavailable",
        price=None,
        freshness="unknown",
        usable=False,
    )
    with pytest.raises(CanonicalMarketStateError) as missing_error:
        market_view_from_evidence(missing)
    assert missing_error.value.availability == "unavailable"
    assert "unavailable" in missing_error.value.reason

    fresh = market_view_from_evidence(
        _canonical_read(
            presentation="live_mark",
            price="64000",
            freshness="fresh",
            usable=True,
            is_live=True,
        )
    )
    assert fresh.is_live is True
    assert fresh.is_stale is False
    assert fresh.fallback_used is False
    assert fresh.last_price == "64000"
    assert fresh.source.startswith("canonical:")

    replay = market_view_from_evidence(
        _canonical_read(
            presentation="replay_fixture",
            price="1",
            freshness="fresh",
            usable=True,
            is_live=False,
        )
    )
    assert replay.is_live is False
    assert replay.is_stale is False

    labeled = market_view_from_evidence(
        _canonical_read(
            presentation="stale",
            price="64000",
            freshness="stale",
            usable=False,
        )
    )
    assert labeled.is_stale is True
    assert labeled.is_live is False


def _file_sqlite_factory(path: Path) -> sessionmaker[Session]:
    """Separate connections. BEGIN IMMEDIATE waits instead of interleaving writes.

    The default agent fixture uses one shared connection, so two threads cannot
    take a real row lock there.
    """
    engine = create_engine(
        f"sqlite+pysqlite:///{path}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )

    @event.listens_for(engine, "connect")
    def _connect(dbapi_conn: object, _record: object) -> None:
        dbapi_conn.isolation_level = None  # type: ignore[attr-defined]
        cursor = dbapi_conn.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

    @event.listens_for(engine, "begin")
    def _begin(conn: object) -> None:
        conn.exec_driver_sql("BEGIN IMMEDIATE")  # type: ignore[attr-defined]

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        session.add(Organization(id=ORG_A, name="Agent Org A"))
        session.add(User(id=USER_A, email="agent-a@test.example", hashed_password="x"))
        session.flush()
        session.add(Membership(user_id=USER_A, organization_id=ORG_A, role=MembershipRole.OWNER))
        session.commit()
    return factory


def test_repeated_and_concurrent_journal_confirms_write_one_row(tmp_path: Path) -> None:
    factory = _file_sqlite_factory(tmp_path / "agent-confirm.db")
    settings = _settings()
    with factory() as session:
        _service_unused, proposed = _turn(session, settings, JOURNAL_TEXT)
        session.commit()
        proposal = proposed.proposals[0]
        conversation_id = proposed.conversation_id
        digest = proposal.content_hash
        proposal_id = proposal.proposal_id

    barrier = threading.Barrier(2)
    results: list[uuid.UUID | None] = []
    errors: list[BaseException] = []
    lock = threading.Lock()

    def _confirm() -> None:
        barrier.wait(timeout=10)
        try:
            with factory() as session:
                confirmed = InteractiveAgentService(session, settings=settings).confirm(
                    proposal_id,
                    ProposalDecisionRequest(
                        conversation_id=conversation_id,
                        expected_content_hash=digest,
                        statement="I confirm",
                    ),
                    organization_id=ORG_A,
                    user_id=USER_A,
                )
                session.commit()
            with lock:
                results.append(confirmed.resulting_record_id)
        except BaseException as exc:
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=_confirm) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert all(not thread.is_alive() for thread in threads)

    with factory() as session:
        assert _count(session, TradeJournal) == 1
        again = InteractiveAgentService(session, settings=settings).confirm(
            proposal_id,
            ProposalDecisionRequest(
                conversation_id=conversation_id,
                expected_content_hash=digest,
                statement="I confirm",
            ),
            organization_id=ORG_A,
            user_id=USER_A,
        )
        session.commit()
        assert _count(session, TradeJournal) == 1
        assert again.resulting_record_id is not None
    written = {item for item in results if item is not None}
    assert not errors
    assert written == {again.resulting_record_id}


def _canonical_read(
    *,
    presentation: str,
    price: str | None,
    freshness: str,
    usable: bool,
    is_live: bool = False,
) -> CanonicalEvidenceRead:
    now = datetime.now(UTC)
    return CanonicalEvidenceRead(
        organization_id=str(ORG_A),
        symbol="BTCUSDT",
        source=CanonicalSourceIdentityRead(
            venue="binance",
            market_type="usd_m_perpetual",
            instrument_id="BTCUSDT",
            provider_symbol="BTCUSDT",
            provider_name="binance_usdm",
            source_family="binance_usdm",
            adapter_version="test",
            is_live=is_live,
            is_mock=not is_live,
        ),
        current_price=CanonicalCurrentPriceRead(
            usable_as_current_market_price=usable,
            presentation=presentation,
            price=price,
            source_time=now if price else None,
            venue_trade_id="trade-1" if price else None,
            is_live=is_live,
            is_mock=not is_live,
            freshness=CanonicalFreshnessRead(
                policy_version="freshness/v1",
                state=freshness,
                evaluated_at=now,
            ),
        ),
        setup_evidence=CanonicalSetupEvidenceRead(
            available=False,
            completeness=CanonicalCompletenessRead(
                ohlcv_15m="unknown",
                ohlcv_4h="unknown",
                cvd="unknown",
                signed_flow="unknown",
            ),
            reason="not_used",
        ),
        timestamps={"evaluated_at": now},
        unavailable_reason=None if usable else presentation,
    )

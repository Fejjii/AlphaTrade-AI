"""Controlled fixture proof for the intelligence integration loop.

This is not deployed or live validation. Watcher and Telegram stay disabled.
Paper / replay only. Confirmation stores a draft; strategy approval is separate.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.errors import ValidationAppError
from app.core.persistence_firewall import install_persistence_firewall
from app.db.base import Base
from app.db.models import Membership, Organization, User, UserStrategy, UserStrategyVersion
from app.evidence_pipeline.assembler import FirstSliceEvidenceAssembler
from app.market_contracts.adapters.replay import ReplayPerpetualSource
from app.schemas.common import (
    ConversationMessageRole,
    MembershipRole,
    StrategyId,
    StrategyLifecycleState,
)
from app.schemas.conversation import ConversationCreate
from app.schemas.strategy_library import StrategyCard, UserStrategyCreate
from app.schemas.strategy_pattern_spec import canonical_first_slice_authored_spec
from app.schemas.structured_rules import StructureFromTextRequest
from app.services.canonical_strategy_evaluation import resolve_executable_strategy_policy
from app.services.compiled_setup_service import CompiledSetupService
from app.services.conversation_service import ConversationService
from app.services.strategy_library_service import StrategyLibraryService
from app.services.strategy_proposal_service import StrategyProposalService
from app.services.strategy_versioning import StrategyVersioningService
from app.services.structure_from_text_service import StructureFromTextService
from app.signal_fusion.errors import StrategyEvaluationPolicyError
from app.signal_fusion.strategy_evaluation_policy import evaluate_canonical_strategy
from tests.support.first_slice_preview import (
    INCOMPLETE_FIRST_SLICE_TEXT,
    UNSUPPORTED_STRATEGY_TEXT,
    complete_first_slice_preview_text,
)

ORG = uuid.UUID("00000000-0000-0000-0000-000000000063")
USER = uuid.UUID("00000000-0000-0000-0000-000000000163")


def _engine() -> sessionmaker[Session]:
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
    install_persistence_firewall()
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def session() -> Iterator[Session]:
    factory = _engine()
    with factory() as db:
        db.add_all(
            [
                Organization(id=ORG, name="AT063 Org"),
                User(id=USER, email="at063@test.example", hashed_password="not-a-real-hash"),
            ]
        )
        db.flush()
        db.add(Membership(organization_id=ORG, user_id=USER, role=MembershipRole.TRADER))
        db.commit()
        yield db


def _card() -> StrategyCard:
    spec = canonical_first_slice_authored_spec()
    return StrategyCard.model_validate(
        {
            "strategy_name": spec.name,
            "market_type": "crypto_perp",
            "asset_universe": ["BTCUSDT"],
            "timeframes": ["15m", "4h"],
            "entry_conditions": ["Bearish liquidity sweep at 4h resistance"],
            "confirmation_conditions": ["CVD divergence"],
            "invalidation": ["Close back above sweep high"],
            "stop_loss": ["Above sweep high"],
            "take_profit_plan": ["TP1 at 1R"],
            "runner_plan": [],
            "position_sizing": ["1%"],
            "add_rules": [],
            "no_trade_rules": [],
            "backtest_rules": [],
            "success_criteria": [],
            "validation_status": "draft",
        }
    )


def test_unsupported_and_incomplete_inputs_remain_blocked() -> None:
    service = StructureFromTextService()
    incomplete = service.draft_preview(StructureFromTextRequest(text=INCOMPLETE_FIRST_SLICE_TEXT))
    assert incomplete.pattern_spec_draft is None
    assert incomplete.pattern_spec_errors
    assert incomplete.is_preview is True
    unsupported = service.draft_preview(StructureFromTextRequest(text=UNSUPPORTED_STRATEGY_TEXT))
    assert unsupported.pattern_spec_draft is None
    assert unsupported.is_preview is True
    assert unsupported.persists_strategy is False


def test_fixture_discussion_preview_confirm_approve_compile_evidence_assessment(
    session: Session,
) -> None:
    """Replay/paper fixture proof. Not a live or deployed validation."""

    created = StrategyLibraryService(session).create(
        UserStrategyCreate(
            organization_id=ORG,
            user_id=USER,
            name="AT063 Sweep",
            setup_type=StrategyId.LIQUIDITY_SWEEP_REVERSAL,
            card=_card(),
        )
    )
    conversations = ConversationService(session)
    conversation = conversations.create(
        ConversationCreate(title="First-slice discussion", strategy_id=created.id),
        organization_id=ORG,
        user_id=USER,
    )
    conversations.append_message(
        conversation=conversation,
        role=ConversationMessageRole.USER,
        content=complete_first_slice_preview_text(),
        request_id="at063-discussion",
    )
    listed = conversations.list_messages(conversation.id, organization_id=ORG, user_id=USER)
    assert listed.total >= 1

    proposals = StrategyProposalService(session)
    preview = proposals.create_draft_from_text(
        conversation,
        text=complete_first_slice_preview_text(),
        strategy_id=created.id,
    )
    assert preview.status.value == "draft"
    assert preview.is_preview is True
    assert preview.mutates_strategy_authority is False
    assert preview.proposed_pattern_spec is not None
    assert preview.proposed_pattern_spec["kind"] == canonical_first_slice_authored_spec().kind
    compiled_before = StrategyVersioningService(session).compiled_for_version(
        preview.parent_version_id or uuid.uuid4(), organization_id=ORG
    )
    assert compiled_before is None

    with pytest.raises(ValidationAppError, match=r"quoted|retrieved|Explicit confirmation"):
        proposals.confirm(
            preview.id,
            organization_id=ORG,
            user_id=USER,
            confirm_message="> I confirm",
            conversation_id=conversation.id,
        )

    confirmed = proposals.confirm(
        preview.id,
        organization_id=ORG,
        user_id=USER,
        confirm_message="I confirm",
        conversation_id=conversation.id,
        expected_content_hash=preview.content_hash,
        expected_parent_version_id=preview.parent_version_id,
        expected_target_strategy_id=preview.target_strategy_id,
    )
    assert confirmed.status.value == "confirmed"
    assert confirmed.resulting_version_id is not None
    version_id = confirmed.resulting_version_id
    version = session.get(UserStrategyVersion, version_id)
    assert version is not None
    assert version.pattern_spec is not None

    with pytest.raises(StrategyEvaluationPolicyError, match=r"Draft|approved"):
        resolve_executable_strategy_policy(
            session, organization_id=ORG, strategy_version_id=version_id
        )

    compiled = CompiledSetupService(session).compile_version(
        version_id, organization_id=ORG, user_id=USER
    )
    assert compiled.compiled is not None
    strategy = session.get(UserStrategy, created.id)
    assert strategy is not None
    StrategyVersioningService(session).append_lifecycle(
        organization_id=ORG,
        strategy_id=strategy.id,
        strategy_version_id=version_id,
        new_state=StrategyLifecycleState.APPROVED,
        actor_user_id=USER,
        reason="explicit strategy approval after conversation confirmation",
    )
    session.flush()

    executable = resolve_executable_strategy_policy(
        session, organization_id=ORG, strategy_version_id=version_id
    )
    assert executable.lifecycle_state is StrategyLifecycleState.APPROVED
    assembled = FirstSliceEvidenceAssembler(ReplayPerpetualSource(), replay=True).assemble(
        organization_id=ORG,
        policy=executable.fusion_policy,
    )
    first = evaluate_canonical_strategy(
        executable_policy=executable,
        command=assembled.assessment_command,
        evidence=assembled.bundle,
        evaluated_at=assembled.evaluated_at,
    )
    second = evaluate_canonical_strategy(
        executable_policy=executable,
        command=assembled.assessment_command,
        evidence=assembled.bundle,
        evaluated_at=assembled.evaluated_at,
    )
    assert first.evidence_window_hash == assembled.evidence_window_hash
    assert first.state is second.state
    assert first.evidence_window_hash == second.evidence_window_hash
    assert first.content_hash == second.content_hash

    versions = list(session.scalars(select(UserStrategyVersion)).all())
    confirmed_versions = [item for item in versions if item.id == version_id]
    assert len(confirmed_versions) == 1

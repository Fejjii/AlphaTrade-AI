"""Sticky payload.lineage on JournalLifecycleProjector without a second trade writer."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import JournalProjectionConflictError
from app.db.models import JournalTrade
from app.schemas.common import JournalLifecycleEventType
from app.services.audit_service import AuditService
from app.services.journal_lifecycle_projector import JournalLifecycleProjector
from tests.support.learning_attribution import (
    ACCOUNT_ID,
    ORG_ID,
    USER_ID,
    instrument_payload,
    lifecycle_event,
)
from tests.support.phase6_fusion import CANDIDATE_ID


def _projector(session: Session) -> JournalLifecycleProjector:
    return JournalLifecycleProjector(session, AuditService(session, strict_mode=True))


def test_sticky_lineage_conflict_fails_closed(
    attribution_sessions: sessionmaker[Session],
) -> None:
    lifecycle_id = uuid.uuid4()
    with attribution_sessions() as session:
        projector = _projector(session)
        projector.project(
            lifecycle_event(
                JournalLifecycleEventType.APPROVED_PLAN,
                source_event_id="plan-lineage",
                execution_lifecycle_id=lifecycle_id,
                payload={
                    **instrument_payload(),
                    "lineage": {"candidate_id": str(CANDIDATE_ID)},
                },
            ),
            organization_id=ORG_ID,
            user_id=USER_ID,
        )
        session.commit()
        with pytest.raises(JournalProjectionConflictError, match="lineage"):
            projector.project(
                lifecycle_event(
                    JournalLifecycleEventType.FILL,
                    source_event_id="fill-lineage",
                    execution_lifecycle_id=lifecycle_id,
                    payload={
                        **instrument_payload(entry_price="64000"),
                        "lineage": {"candidate_id": str(uuid.uuid4())},
                    },
                ),
                organization_id=ORG_ID,
                user_id=USER_ID,
            )
        assert session.scalar(select(func.count()).select_from(JournalTrade)) == 1


def test_matching_lineage_converges(
    attribution_sessions: sessionmaker[Session],
) -> None:
    lifecycle_id = uuid.uuid4()
    with attribution_sessions() as session:
        projector = _projector(session)
        first = projector.project(
            lifecycle_event(
                JournalLifecycleEventType.APPROVED_PLAN,
                source_event_id="plan-ok",
                execution_lifecycle_id=lifecycle_id,
                payload={
                    **instrument_payload(),
                    "lineage": {"candidate_id": str(CANDIDATE_ID), "account_id": str(ACCOUNT_ID)},
                },
            ),
            organization_id=ORG_ID,
            user_id=USER_ID,
        )
        second = projector.project(
            lifecycle_event(
                JournalLifecycleEventType.FILL,
                source_event_id="fill-ok",
                execution_lifecycle_id=lifecycle_id,
                payload={
                    **instrument_payload(entry_price="64000"),
                    "lineage": {"candidate_id": str(CANDIDATE_ID)},
                },
            ),
            organization_id=ORG_ID,
            user_id=USER_ID,
        )
        session.commit()
        assert first.journal_trade_id == second.journal_trade_id
        assert session.scalar(select(func.count()).select_from(JournalTrade)) == 1
        trade = session.scalars(select(JournalTrade)).one()
        assert trade.candidate_id == CANDIDATE_ID


def test_events_without_lineage_remain_valid(
    attribution_sessions: sessionmaker[Session],
) -> None:
    lifecycle_id = uuid.uuid4()
    with attribution_sessions() as session:
        result = _projector(session).project(
            lifecycle_event(
                JournalLifecycleEventType.APPROVED_PLAN,
                source_event_id="plan-plain",
                execution_lifecycle_id=lifecycle_id,
                payload=instrument_payload(),
            ),
            organization_id=ORG_ID,
            user_id=USER_ID,
        )
        session.commit()
        assert result.created_journal_trade is True
        assert result.journal_trade_id is not None

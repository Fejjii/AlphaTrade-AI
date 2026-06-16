"""Lesson candidate storage for discipline events (Slice 36)."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.db.models import LessonCandidate as LessonCandidateModel
from app.schemas.common import LessonCandidateStatus


class LessonCandidateService:
    """Store discipline lessons for review — not auto-promoted to permanent rules."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_candidate(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        journal_entry_id: uuid.UUID | None,
        trade_id: uuid.UUID | None,
        category: str,
        summary: str,
        status: LessonCandidateStatus = LessonCandidateStatus.CANDIDATE,
    ) -> uuid.UUID:
        row = LessonCandidateModel(
            organization_id=organization_id,
            user_id=user_id,
            journal_entry_id=journal_entry_id,
            trade_id=trade_id,
            category=category,
            summary=summary,
            status=status,
        )
        self._session.add(row)
        self._session.flush()
        return row.id

    def list_for_journal(
        self,
        journal_entry_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> list[uuid.UUID]:
        from sqlalchemy import select

        stmt = select(LessonCandidateModel).where(
            LessonCandidateModel.journal_entry_id == journal_entry_id,
            LessonCandidateModel.organization_id == organization_id,
            LessonCandidateModel.user_id == user_id,
        )
        rows = self._session.scalars(stmt).all()
        return [row.id for row in rows]

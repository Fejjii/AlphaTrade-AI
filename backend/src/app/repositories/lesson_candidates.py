"""Lesson candidate persistence (Slice 37)."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import LessonCandidate as LessonCandidateModel
from app.schemas.common import LessonCandidateStatus


class LessonCandidateRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, row: LessonCandidateModel) -> LessonCandidateModel:
        self._session.add(row)
        self._session.flush()
        return row

    def get_scoped(
        self,
        lesson_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> LessonCandidateModel | None:
        stmt = select(LessonCandidateModel).where(
            LessonCandidateModel.id == lesson_id,
            LessonCandidateModel.organization_id == organization_id,
            LessonCandidateModel.user_id == user_id,
        )
        return self._session.scalar(stmt)

    def list_scoped(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        status: LessonCandidateStatus | None = None,
        mistake_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[LessonCandidateModel], int]:
        filters = [
            LessonCandidateModel.organization_id == organization_id,
            LessonCandidateModel.user_id == user_id,
        ]
        if status is not None:
            filters.append(LessonCandidateModel.status == status.value)
        if mistake_type is not None:
            filters.append(LessonCandidateModel.mistake_type == mistake_type)

        count_stmt = select(func.count()).select_from(LessonCandidateModel).where(*filters)
        total = int(self._session.scalar(count_stmt) or 0)

        stmt = (
            select(LessonCandidateModel)
            .where(*filters)
            .order_by(LessonCandidateModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = list(self._session.scalars(stmt).all())
        return rows, total

    def list_for_journal(
        self,
        journal_entry_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> list[LessonCandidateModel]:
        stmt = select(LessonCandidateModel).where(
            LessonCandidateModel.organization_id == organization_id,
            LessonCandidateModel.user_id == user_id,
            (
                (LessonCandidateModel.related_journal_entry_id == journal_entry_id)
                | (LessonCandidateModel.journal_entry_id == journal_entry_id)
            ),
        )
        return list(self._session.scalars(stmt).all())

    def list_for_strategy(
        self,
        strategy_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        status: LessonCandidateStatus | None = None,
        limit: int = 50,
    ) -> list[LessonCandidateModel]:
        filters = [
            LessonCandidateModel.organization_id == organization_id,
            LessonCandidateModel.user_id == user_id,
            LessonCandidateModel.related_strategy_id == strategy_id,
        ]
        if status is not None:
            filters.append(LessonCandidateModel.status == status.value)
        stmt = (
            select(LessonCandidateModel)
            .where(*filters)
            .order_by(LessonCandidateModel.created_at.desc())
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())

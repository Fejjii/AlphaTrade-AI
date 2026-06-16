"""User strategy library persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.db.models import UserStrategy, UserStrategyVersion
from app.repositories.base import SQLAlchemyRepository


class UserStrategyRepository(SQLAlchemyRepository[UserStrategy]):
    model = UserStrategy

    def list_scoped(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[UserStrategy], int]:
        filters = [UserStrategy.organization_id == organization_id]
        if user_id is not None:
            filters.append(UserStrategy.user_id == user_id)
        count_stmt = select(func.count()).select_from(UserStrategy).where(*filters)
        list_stmt = (
            select(UserStrategy)
            .where(*filters)
            .order_by(UserStrategy.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        total = int(self._session.scalar(count_stmt) or 0)
        return list(self._session.scalars(list_stmt).all()), total

    def get_scoped(
        self,
        strategy_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> UserStrategy | None:
        stmt = select(UserStrategy).where(
            UserStrategy.id == strategy_id,
            UserStrategy.organization_id == organization_id,
        )
        if user_id is not None:
            stmt = stmt.where(UserStrategy.user_id == user_id)
        return self._session.scalar(stmt)


class UserStrategyVersionRepository(SQLAlchemyRepository[UserStrategyVersion]):
    model = UserStrategyVersion

    def list_for_strategy(
        self,
        strategy_id: uuid.UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[UserStrategyVersion], int]:
        filters = [UserStrategyVersion.strategy_id == strategy_id]
        count_stmt = select(func.count()).select_from(UserStrategyVersion).where(*filters)
        list_stmt = (
            select(UserStrategyVersion)
            .where(*filters)
            .order_by(UserStrategyVersion.version.desc())
            .limit(limit)
            .offset(offset)
        )
        total = int(self._session.scalar(count_stmt) or 0)
        return list(self._session.scalars(list_stmt).all()), total

    def get_version(
        self,
        strategy_id: uuid.UUID,
        version: int,
    ) -> UserStrategyVersion | None:
        stmt = select(UserStrategyVersion).where(
            UserStrategyVersion.strategy_id == strategy_id,
            UserStrategyVersion.version == version,
        )
        return self._session.scalar(stmt)

    def latest(self, strategy_id: uuid.UUID) -> UserStrategyVersion | None:
        stmt = (
            select(UserStrategyVersion)
            .where(UserStrategyVersion.strategy_id == strategy_id)
            .order_by(UserStrategyVersion.version.desc())
            .limit(1)
        )
        return self._session.scalar(stmt)

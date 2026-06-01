"""Generic SQLAlchemy repository establishing the persistence boundary.

Provides typed CRUD primitives shared by concrete repositories. Business logic
lives in services, not here.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import Base


class SQLAlchemyRepository[ModelT: Base]:
    """Base repository for a single ORM model."""

    model: type[ModelT]

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, entity: ModelT) -> ModelT:
        self._session.add(entity)
        self._session.flush()
        return entity

    def get(self, entity_id: uuid.UUID) -> ModelT | None:
        return self._session.get(self.model, entity_id)

    def list(self, *, limit: int = 100, offset: int = 0) -> list[ModelT]:
        stmt = select(self.model).limit(limit).offset(offset)
        return list(self._session.scalars(stmt).all())

    def delete(self, entity: ModelT) -> None:
        self._session.delete(entity)
        self._session.flush()

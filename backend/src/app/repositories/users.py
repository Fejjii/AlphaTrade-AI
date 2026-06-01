"""User repository: persistence boundary for :class:`app.db.models.User`."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import User
from app.repositories.base import SQLAlchemyRepository


class UserRepository(SQLAlchemyRepository[User]):
    model = User

    def __init__(self, session: Session) -> None:
        super().__init__(session)

    def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        return self._session.scalars(stmt).one_or_none()

"""Password reset token repository."""

from __future__ import annotations

from sqlalchemy import select

from app.db.models import PasswordResetToken
from app.repositories.base import SQLAlchemyRepository


class PasswordResetTokenRepository(SQLAlchemyRepository[PasswordResetToken]):
    model = PasswordResetToken

    def get_by_hash(self, token_hash: str) -> PasswordResetToken | None:
        stmt = select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
        return self._session.scalars(stmt).one_or_none()

    def invalidate_active_for_user(self, user_id) -> int:
        from datetime import UTC, datetime

        stmt = select(PasswordResetToken).where(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.consumed_at.is_(None),
        )
        rows = list(self._session.scalars(stmt).all())
        now = datetime.now(UTC)
        for row in rows:
            row.consumed_at = now
        if rows:
            self._session.flush()
        return len(rows)

"""Refresh token persistence."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.db.models import RefreshToken
from app.repositories.base import SQLAlchemyRepository


class RefreshTokenRepository(SQLAlchemyRepository[RefreshToken]):
    model = RefreshToken

    def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        return self._session.scalars(stmt).one_or_none()

    def revoke(self, token: RefreshToken, *, replaced_by_id: uuid.UUID | None = None) -> None:
        token.revoked_at = datetime.now(UTC)
        token.replaced_by_id = replaced_by_id
        self._session.flush()

    def revoke_all_active_for_user(self, user_id: uuid.UUID) -> int:
        """Revoke every non-revoked refresh token for a user (reuse detection)."""
        stmt = select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        rows = list(self._session.scalars(stmt).all())
        for row in rows:
            row.revoked_at = datetime.now(UTC)
        if rows:
            self._session.flush()
        return len(rows)

"""Durable setup-lifetime pins. No Candidate mint, no Watcher start."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SetupLifetimePin(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Tenant-scoped original trigger pin for one compiled setup lifetime."""

    __tablename__ = "setup_lifetime_pins"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "symbol",
            "timeframe",
            "strategy_version_id",
            "compiled_setup_definition_id",
            "compiled_content_hash",
            name="uq_setup_lifetime_semantic_key",
        ),
        CheckConstraint(
            "length(compiled_content_hash) = 64",
            name="setup_lifetime_compiled_hash_len",
        ),
        CheckConstraint(
            "length(trigger_bar_hash) = 64",
            name="setup_lifetime_trigger_hash_len",
        ),
        CheckConstraint(
            "length(required_lineage_hash) = 64",
            name="setup_lifetime_lineage_hash_len",
        ),
        Index(
            "ix_setup_lifetime_pins_org_symbol_timeframe",
            "organization_id",
            "symbol",
            "timeframe",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(16), nullable=False)
    strategy_version_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    compiled_setup_definition_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    compiled_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    trigger_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    trigger_bar_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expired: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    required_lineage_hash: Mapped[str] = mapped_column(String(64), nullable=False)


__all__ = ["SetupLifetimePin"]

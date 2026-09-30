"""Organization-owned Watcher configuration and bounded latest observations."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WatcherWatchlistRow(Base):
    __tablename__ = "watcher_watchlists"
    __table_args__ = (CheckConstraint("revision >= 0", name="watchlist_revision"),)

    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id"), primary_key=True
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    slots: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    runtime_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class WatcherSymbolStatusRow(Base):
    __tablename__ = "watcher_symbol_status"

    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("watcher_watchlists.organization_id", ondelete="CASCADE"), primary_key=True
    )
    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    configuration_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)

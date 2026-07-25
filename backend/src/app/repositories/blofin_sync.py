"""BloFin demo sync snapshot repository (AT-037)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import BloFinDemoSyncSnapshot as SnapshotModel


class BloFinSyncRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, row: SnapshotModel) -> SnapshotModel:
        self._session.add(row)
        self._session.flush()
        return row

    def latest_for_org(self, organization_id: uuid.UUID) -> SnapshotModel | None:
        stmt = (
            select(SnapshotModel)
            .where(SnapshotModel.organization_id == organization_id)
            .order_by(SnapshotModel.synced_at.desc())
            .limit(1)
        )
        return self._session.scalars(stmt).first()

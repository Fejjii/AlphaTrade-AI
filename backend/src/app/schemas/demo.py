"""Demo seed API schemas (Slice 50)."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from app.schemas.common import StrictModel


class DemoSeedResponse(StrictModel):
    organization_id: UUID
    user_id: UUID
    email: str
    strategies_seeded: int
    paper_runs_seeded: int
    alerts_seeded: int
    lessons_seeded: int
    journals_seeded: int
    paper_only: bool = True
    synthetic: bool = True
    message: str = Field(
        default="Synthetic paper-only demo data seeded. Real trading remains disabled.",
    )

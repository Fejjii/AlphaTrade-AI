"""Demo seed API schemas (Slice 50)."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from app.schemas.common import StrictModel


class DemoSeedRequest(StrictModel):
    """Optional body for staging API seed when server env lacks DEMO_SEED_PASSWORD."""

    password: str | None = Field(
        default=None,
        min_length=1,
        description=(
            "Demo account password. Used when DEMO_SEED_PASSWORD is unset on the server "
            "(e.g. Render staging without shell). Never logged."
        ),
    )


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

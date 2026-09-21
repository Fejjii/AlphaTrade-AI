"""Deterministic paper-evaluation identity. Not a Candidate or JournalTrade authority."""

from __future__ import annotations

from uuid import UUID, uuid5

PAPER_EVALUATION_NAMESPACE = UUID("c3a91e70-4d2b-4f8e-9a11-6d0e8b7c4f21")
PAPER_EVALUATION_SUMMARY_NAMESPACE = UUID("d4b02f81-5e3c-4a9f-8b22-7e1f9c8d5a32")


def observation_id_for(
    *,
    organization_id: UUID,
    source_system: str,
    source_event_id: str,
    source_event_version: int,
) -> UUID:
    """Stable observation id: one row per org-owned source identity."""

    return uuid5(
        PAPER_EVALUATION_NAMESPACE,
        ":".join(
            (
                str(organization_id),
                source_system,
                source_event_id,
                str(source_event_version),
            )
        ),
    )


def summary_id_for(*, organization_id: UUID, facts_hash: str) -> UUID:
    """Stable summary id for a given org facts snapshot. Not a strategy version."""

    return uuid5(PAPER_EVALUATION_SUMMARY_NAMESPACE, f"{organization_id}:{facts_hash}")

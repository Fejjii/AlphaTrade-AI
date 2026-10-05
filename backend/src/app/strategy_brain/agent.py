"""Grounded read tool for the existing interactive Agent. No market acquisition."""

import re
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.interactive_agent.contracts import ArtifactKind, ConnectionRef, ProvenanceSource
from app.interactive_agent.parsing import extract_symbol
from app.strategy_brain.service import details, overview


def read_brain(
    session: Session,
    *,
    organization_id: UUID,
    message: str,
    symbol: str | None = None,
) -> tuple[str, list[ConnectionRef], list[str]]:
    data = overview(
        session, organization_id=organization_id, symbol=extract_symbol(message) or symbol
    )
    selected = re.search(r"\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b", message, re.I)
    if selected:
        try:
            data["setups"] = [
                details(session, organization_id=organization_id, setup_id=UUID(selected.group()))
            ]
        except NotFoundError:
            data["setups"] = []
    lines = [
        "Watcher configuration: "
        + (", ".join(data["watched_symbols"]) or "no enabled symbols")
        + f" (revision {data['watchlist_revision']})."
    ]
    refs = []
    if not data["setups"]:
        lines.append(
            (
                "No stored SFP setup exists for this query. "
                if re.search(r"\bsfp\b|swing failure", message, re.I)
                else "No stored Nested Continuation setup exists for this query. "
            )
            + "Current market conditions are unknown."
        )
    for setup in data["setups"][:8]:
        lines.append(
            f"Setup {setup['setup_id']} on {setup.get('instrument')}: {setup['state']}, "
            f"{setup.get('condition', setup.get('stage'))}, {setup.get('direction')}; "
            f"strategy version {setup['strategy_version_id']}; "
            f"observed {setup['observed_at']}; expires {setup['expires_at']}; "
            f"freshness {setup['freshness']}. "
            f"Reasons: {', '.join(setup.get('reason_codes', []))}; "
            f"risk {setup.get('risk_state', 'not_evaluated')}. "
            f"Evidence {setup.get('evidence_reference')}; missing/unsupported: "
            + ", ".join(
                f"{name}={state}"
                for name, state in setup.get("evidence", {}).items()
                if state != "AVAILABLE"
            )
            + f". Candidate {setup['candidate_id'] or 'none'}; "
            + f"journal {setup['journal'] or 'none'}; decision {setup['decision_id'] or 'none'}. "
            "These are stored observations, not current market claims."
        )
        if setup.get("family") == "sfp":
            level = setup["sweep"]["reference_level"]
            lines.append(
                f"Swept {level['kind']} {level['price']}; level {level['level_id']}; "
                f"evidence time {setup['evidence_at']}; "
                f"reclaim {setup.get('reclaim_observation_id')}; "
                "quality components "
                + ", ".join(
                    f"{name}={component['availability']}:{component['value']} {component['unit']}"
                    for name, component in setup["quality"].items()
                )
                + "; "
                "target space is advisory, not an executable target."
            )
        refs.append(
            ConnectionRef(
                artifact_kind=ArtifactKind.OBSERVATION,
                record_id=setup["setup_id"],
                title=(
                    f"{setup.get('family', 'Nested')} "
                    f"{setup.get('condition', setup.get('stage'))} {setup['state']}"
                ),
                relation="stored setup and history",
                provenance=ProvenanceSource.WATCHER_OBSERVED,
            )
        )
    lines.append("Insufficient history for win rate or expectancy; no rule was changed.")
    return "\n".join(lines)[:4000], refs, data["limitations"]

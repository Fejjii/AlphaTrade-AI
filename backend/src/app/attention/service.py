"""Pure attention reduction: explicit clock, stable identity, deterministic order."""

from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import AwareDatetime, TypeAdapter

from app.attention.contracts import (
    AttentionCategory,
    AttentionItem,
    AttentionQueue,
    AttentionSignal,
)
from app.services.canonical_serialization import canonical_sha256

_SEVERITY = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
_PRIORITY = {category: index for index, category in enumerate(AttentionCategory)}


def build_queue(
    signals: tuple[AttentionSignal, ...],
    *,
    organization_id: UUID,
    user_id: UUID,
    now: datetime,
    limitations: tuple[str, ...] = (),
) -> AttentionQueue:
    """Risk precedes market opportunity. Expiry is half-open: now < expires_at.

    Repeated semantic notices share identity and merge provenance. The newest
    recorded notice supplies the wording/expiry; canonical hash breaks time ties.
    Missing records never generate a fabricated problem or an executable action.
    """
    now = TypeAdapter(AwareDatetime).validate_python(now)
    groups: dict[tuple[AttentionCategory, str], list[AttentionSignal]] = {}
    for signal in signals:
        if signal.organization_id != organization_id or signal.user_id not in (None, user_id):
            continue
        if any(source.occurred_at > now for source in signal.sources):
            continue
        if signal.expires_at is not None and now >= signal.expires_at:
            continue
        groups.setdefault((signal.category, signal.semantic_key), []).append(signal)
    items = []
    for (category, semantic_key), group in groups.items():
        latest = max(
            group,
            key=lambda s: (max(ref.occurred_at for ref in s.sources), canonical_sha256(s)),
        )
        sources = {canonical_sha256(ref): ref for s in group for ref in s.sources}
        identity = canonical_sha256(
            {
                "scope": [str(organization_id), str(user_id)],
                "category": category.value,
                "semantic_key": semantic_key,
            }
        )
        items.append(
            AttentionItem(
                item_id=uuid5(NAMESPACE_URL, f"alphatrade:attention:v1:{identity}"),
                **latest.model_dump(
                    exclude={"organization_id", "user_id", "semantic_key", "sources"}
                ),
                sources=tuple(sources[key] for key in sorted(sources)),
            )
        )
    ordered = tuple(
        sorted(items, key=lambda i: (_PRIORITY[i.category], _SEVERITY[i.severity], str(i.item_id)))
    )
    return AttentionQueue(
        organization_id=organization_id,
        user_id=user_id,
        generated_at=now,
        items=ordered,
        recommended_next_action=next(
            (i.recommended_next_action for i in ordered if i.recommended_next_action), None
        ),
        limitations=tuple(
            sorted(
                {
                    *limitations,
                    "Only stored records are projected; absent records do not prove inactivity.",
                    "Recommendations require human review and confer no trading authority.",
                }
            )
        ),
    )

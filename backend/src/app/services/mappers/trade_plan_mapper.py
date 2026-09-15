"""ORM mapping for immutable trade-plan revisions."""

from __future__ import annotations

from app.db.models import TradePlanRevision as TradePlanRevisionModel
from app.schemas.trade_plan import TradePlanRevision, TradePlanRevisionSemantic


def trade_plan_revision_to_schema(row: TradePlanRevisionModel) -> TradePlanRevision:
    semantic = TradePlanRevisionSemantic.model_validate(row.semantic_payload)
    return TradePlanRevision(
        **semantic.model_dump(mode="python"),
        content_hash=row.content_hash,
        created_at=row.created_at,
        presentation_metadata=row.presentation_metadata,
    )

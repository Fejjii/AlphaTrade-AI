"""Read-only preview of explicit provisional Nested subscriptions; no provider IO."""

from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationAppError
from app.db.models import UserStrategy, UserStrategyVersion
from app.schemas.common import Timeframe, TradeDirection
from app.schemas.nested_continuation import NestedContinuationSpec
from app.services.canonical_serialization import canonical_sha256
from app.services.canonical_strategy_evaluation import resolve_executable_strategy_policy
from app.services.strategy_versioning import StrategyVersioningService
from app.signal_fusion.errors import StrategyEvaluationPolicyError
from app.strategy_brain.service import template_name

NESTED_DEMO_MARKETS = ("BTCUSDT", "ETHUSDT", "ZECUSDT", "TAOUSDT", "HYPEUSDT")


def preview_nested_subscriptions(
    session: Session, *, organization_id: UUID, user_id: UUID, baseline_version_id: UUID
) -> dict[str, Any]:
    source = session.scalar(
        select(UserStrategyVersion)
        .join(UserStrategy, UserStrategy.id == UserStrategyVersion.strategy_id)
        .where(
            UserStrategyVersion.id == baseline_version_id,
            UserStrategy.organization_id == organization_id,
            UserStrategy.user_id == user_id,
        )
    )
    if source is None:
        raise NotFoundError("Nested baseline version not found.")
    try:
        spec = NestedContinuationSpec.model_validate(source.pattern_spec)
    except ValidationError as exc:
        raise ValidationAppError("A valid provisional Nested baseline is required.") from exc
    if spec.trigger_timeframe is not Timeframe.M15:
        raise ValidationAppError("The five-market preview requires a 15m baseline.")
    proposals = [
        spec.model_copy(update={"symbol": symbol, "direction": direction})
        for symbol in NESTED_DEMO_MARKETS
        for direction in (TradeDirection.LONG, TradeDirection.SHORT)
    ]
    names = [template_name(proposal) for proposal in proposals]
    existing = {
        strategy.name: strategy
        for strategy in session.scalars(
            select(UserStrategy).where(
                UserStrategy.organization_id == organization_id,
                UserStrategy.user_id == user_id,
                UserStrategy.name.in_(names),
            )
        )
    }
    versioning = StrategyVersioningService(session)
    additions = []
    for proposal, name in zip(proposals, names, strict=True):
        payload = proposal.model_dump(mode="json")
        strategy = existing.get(name)
        version = versioning.selected_version(strategy) if strategy is not None else None
        matches = version is not None and version.pattern_spec == payload
        approved = False
        if matches and version is not None:
            try:
                resolve_executable_strategy_policy(
                    session, organization_id=organization_id, strategy_version_id=version.id
                )
                approved = True
            except StrategyEvaluationPolicyError:
                pass
        latest = (
            versioning.latest_lifecycle_event_for_version(version.id)
            if matches and version is not None
            else None
        )
        additions.append(
            {
                "name": name,
                "spec": payload,
                "content_hash": canonical_sha256(payload),
                "action": "reuse_existing"
                if matches
                else ("name_conflict" if strategy else "propose_new"),
                "existing_strategy_id": str(strategy.id) if strategy else None,
                "existing_version_id": str(version.id) if matches and version is not None else None,
                "existing_lifecycle": latest.new_state.value
                if latest
                else ("draft" if matches else None),
                "existing_version_approved": approved,
                "requires_explicit_approval": not approved,
                "instrument_availability": "unverified",
            }
        )
    baseline = {
        "strategy_id": str(source.strategy_id),
        "version_id": str(source.id),
        "version": source.version,
        "content_hash": canonical_sha256(source.pattern_spec or {}),
        "provisional": True,
    }
    return {
        "preview_hash": canonical_sha256(
            {"baseline": baseline, "specs": [p.model_dump(mode="json") for p in proposals]}
        ),
        "baseline": baseline,
        "additions": additions,
        "subscription_count": len(additions),
        "changes_active_rules": False,
        "execution_authorized": False,
        "next_step": (
            "Explicitly propose new templates, compile and review each exact version; "
            "separately enable verified watchlist slots."
        ),
    }

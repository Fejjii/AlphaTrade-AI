"""Persist actual model-call telemetry without creating a second usage system.

Each actual LLM call records one :class:`ModelCallAttempt` and, when a usage
service is available, one :class:`UsageEvent` with the same tokens and cost.
Cost is never fabricated: unknown prices are recorded as ``unavailable``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import structlog

from app.schemas.common import CostSource
from app.schemas.model_routing import ModelCallAttempt
from app.schemas.usage import UsageEventCreate
from app.services.cost_estimator import estimate_placeholder_cost
from app.services.usage_cost import build_provider_metadata

logger = structlog.get_logger(__name__)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.services.usage_service import UsageService

# Models with published placeholder rates in cost_estimator. Anything else is
# recorded as unavailable rather than a silent default rate.
_KNOWN_RATE_MODELS = frozenset({"gpt-4o-mini", "gpt-4o"})


@dataclass(frozen=True)
class ResolvedModelCallCost:
    estimated_cost: Decimal
    cost_source: CostSource


def resolve_model_call_cost(
    *,
    model: str | None,
    input_tokens: int,
    output_tokens: int,
) -> ResolvedModelCallCost:
    """Return labelled cost. Never invent a provider-reported price."""
    name = (model or "").strip()
    if name not in _KNOWN_RATE_MODELS:
        return ResolvedModelCallCost(Decimal("0"), CostSource.UNAVAILABLE)
    if input_tokens <= 0 and output_tokens <= 0:
        return ResolvedModelCallCost(Decimal("0"), CostSource.UNAVAILABLE)
    estimated = estimate_placeholder_cost(
        model=name,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    return ResolvedModelCallCost(estimated, CostSource.STATIC_ESTIMATED)


class ModelCallTelemetryService:
    """Record ModelCallAttempt rows and matching UsageEvent rows."""

    def __init__(
        self,
        session: Session | None = None,
        usage_service: UsageService | None = None,
    ) -> None:
        self._session = session
        self._usage = usage_service

    def record(self, attempt: ModelCallAttempt, *, feature: str) -> ModelCallAttempt:
        usage_event_id = None
        if self._usage is not None:
            meta = build_provider_metadata(
                input_tokens=attempt.input_tokens,
                output_tokens=attempt.output_tokens,
                cost_source=attempt.cost_source,
                fallback_used=attempt.fallback_used,
                routing_purpose=attempt.purpose.value,
                routing_tier=attempt.tier.value,
                requested_model=attempt.requested_model,
                resolved_model=attempt.resolved_model,
                correlation_id=attempt.correlation_id,
                failure_category=attempt.failure_category.value,
            )
            event = self._usage.record(
                UsageEventCreate(
                    request_id=attempt.correlation_id,
                    feature=feature,
                    user_id=attempt.user_id,
                    organization_id=attempt.organization_id,
                    provider=attempt.provider,
                    model=attempt.resolved_model,
                    input_tokens=attempt.input_tokens,
                    output_tokens=attempt.output_tokens,
                    fallback_used=attempt.fallback_used,
                    latency_ms=attempt.latency_ms,
                    status=attempt.status,
                    timestamp=attempt.completed_at,
                    provider_metadata=meta,
                )
            )
            if (
                self._session is not None
                and getattr(self._usage, "_session", None) is self._session
            ):
                usage_event_id = event.usage_event_id

        stored = attempt.model_copy(update={"usage_event_id": usage_event_id})
        if self._session is None:
            return stored

        from app.db.models import ModelCallAttempt as ModelCallAttemptRow

        row = ModelCallAttemptRow(
            id=stored.attempt_id,
            organization_id=stored.organization_id,
            user_id=stored.user_id,
            account_id=stored.account_id,
            correlation_id=stored.correlation_id,
            usage_event_id=usage_event_id,
            purpose=stored.purpose,
            tier=stored.tier,
            provider=stored.provider,
            requested_model=stored.requested_model,
            resolved_model=stored.resolved_model,
            policy_version=stored.policy_version,
            fallback_policy=stored.fallback_policy,
            fallback_used=stored.fallback_used,
            input_tokens=stored.input_tokens,
            output_tokens=stored.output_tokens,
            latency_ms=stored.latency_ms,
            success=stored.success,
            failure_category=stored.failure_category,
            status=stored.status,
            estimated_cost=stored.estimated_cost,
            cost_source=stored.cost_source,
            resource_type=stored.resource_type,
            resource_id=stored.resource_id,
            retention_category=stored.retention_category,
            mutation_allowed=False,
            started_at=stored.started_at,
            completed_at=stored.completed_at,
            event_at=stored.completed_at or datetime.now(UTC),
        )
        from app.core.persistence_firewall import (
            assert_entity_write_allowed,
            install_persistence_firewall,
        )

        try:
            install_persistence_firewall()
            assert_entity_write_allowed(row)
            self._session.add(row)
            self._session.flush()
        except Exception as exc:
            logger.warning("model_call_attempt_persist_failed", error_type=type(exc).__name__)
            return stored
        return stored

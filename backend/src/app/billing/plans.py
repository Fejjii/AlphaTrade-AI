"""Subscription plan catalog mapped to organization quotas."""

from __future__ import annotations

from decimal import Decimal

from app.schemas.billing import SubscriptionPlanView
from app.schemas.usage import OrganizationQuotaUpdate

PLAN_FREE = "free"
PLAN_PRO = "pro"
PLAN_TEAM = "team"

SUBSCRIPTION_PLANS: dict[str, SubscriptionPlanView] = {
    PLAN_FREE: SubscriptionPlanView(
        plan_id=PLAN_FREE,
        name="Free",
        description="Paper trading copilot with conservative usage limits.",
        monthly_token_limit=500_000,
        monthly_cost_limit=Decimal("25.00"),
        daily_request_limit=2_000,
        limit_agent_chat=500,
        limit_rag_ingest=100,
        limit_market_analyze=300,
        limit_agent_narrative=500,
        limit_paper_execution=50,
        seat_limit=3,
        price_display="$0 / month",
    ),
    PLAN_PRO: SubscriptionPlanView(
        plan_id=PLAN_PRO,
        name="Pro",
        description="Higher limits for active traders and small teams.",
        monthly_token_limit=2_000_000,
        monthly_cost_limit=Decimal("100.00"),
        daily_request_limit=5_000,
        limit_agent_chat=2_000,
        limit_rag_ingest=500,
        limit_market_analyze=1_000,
        limit_agent_narrative=2_000,
        limit_paper_execution=200,
        seat_limit=10,
        price_display="$49 / month (placeholder)",
        stripe_price_id=None,
    ),
    PLAN_TEAM: SubscriptionPlanView(
        plan_id=PLAN_TEAM,
        name="Team",
        description="Expanded limits for organizations with multiple seats.",
        monthly_token_limit=10_000_000,
        monthly_cost_limit=Decimal("500.00"),
        daily_request_limit=20_000,
        limit_agent_chat=10_000,
        limit_rag_ingest=2_000,
        limit_market_analyze=5_000,
        limit_agent_narrative=10_000,
        limit_paper_execution=1_000,
        seat_limit=50,
        price_display="$199 / month (placeholder)",
        stripe_price_id=None,
    ),
}


def get_plan(plan_id: str) -> SubscriptionPlanView | None:
    return SUBSCRIPTION_PLANS.get(plan_id)


def list_plans() -> list[SubscriptionPlanView]:
    return list(SUBSCRIPTION_PLANS.values())


def plan_to_quota_update(plan: SubscriptionPlanView) -> OrganizationQuotaUpdate:
    """Map a subscription plan to organization quota fields."""
    return OrganizationQuotaUpdate(
        monthly_token_limit=plan.monthly_token_limit,
        monthly_cost_limit=plan.monthly_cost_limit,
        daily_request_limit=plan.daily_request_limit,
        limit_agent_chat=plan.limit_agent_chat,
        limit_rag_ingest=plan.limit_rag_ingest,
        limit_market_analyze=plan.limit_market_analyze,
        limit_agent_narrative=plan.limit_agent_narrative,
        limit_paper_execution=plan.limit_paper_execution,
    )

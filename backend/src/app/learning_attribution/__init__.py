"""Phase 7 learning attribution: lineage from canonical lifecycle to learning facts.

Not a trading authority. JournalLifecycleProjector remains the only JournalTrade
writer. REJECT/SKIP never create executed trade outcomes.
"""

from app.learning_attribution.adapters import (
    AttributionAnalyticsSnapshot,
    as_human_vs_system_suggestions,
    lesson_suggestions,
    render_learning_evidence_text,
    rollup_organization,
)
from app.learning_attribution.contracts import (
    ATTRIBUTION_SCHEMA,
    NARRATIVE_NOT_FACT_BANNER,
    AttributionCommand,
    AttributionFacts,
    AttributionRecord,
    AttributionResult,
    DecisionActor,
    DurableAttributionIntegrationRequirement,
    ExecutionQuality,
    LineageSnapshot,
    PlannedSetupQuality,
    TradePlanLineageRef,
    TraderBehavior,
)
from app.learning_attribution.errors import (
    CrossTenantAttributionError,
    ExecutedOutcomeForbiddenError,
    LearningAttributionConflictError,
    MarketTruthMutationError,
    NarrativeCannotRewriteFactsError,
)
from app.learning_attribution.identity import attribution_id_for
from app.learning_attribution.memory import InMemoryAttributionStore
from app.learning_attribution.persistence import AGENT_1_ATTRIBUTION_INTEGRATION
from app.learning_attribution.service import LearningAttributionService

__all__ = [
    "AGENT_1_ATTRIBUTION_INTEGRATION",
    "ATTRIBUTION_SCHEMA",
    "NARRATIVE_NOT_FACT_BANNER",
    "AttributionAnalyticsSnapshot",
    "AttributionCommand",
    "AttributionFacts",
    "AttributionRecord",
    "AttributionResult",
    "CrossTenantAttributionError",
    "DecisionActor",
    "DurableAttributionIntegrationRequirement",
    "ExecutedOutcomeForbiddenError",
    "ExecutionQuality",
    "InMemoryAttributionStore",
    "LearningAttributionConflictError",
    "LearningAttributionService",
    "LineageSnapshot",
    "MarketTruthMutationError",
    "NarrativeCannotRewriteFactsError",
    "PlannedSetupQuality",
    "TradePlanLineageRef",
    "TraderBehavior",
    "as_human_vs_system_suggestions",
    "attribution_id_for",
    "lesson_suggestions",
    "render_learning_evidence_text",
    "rollup_organization",
]

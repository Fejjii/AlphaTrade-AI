"""Phase 7/8 continuous paper evaluation: measurement only.

Connects Watcher → SetupAssessment → Candidate → paper decision → paper trade
→ Journal → attribution → strategy statistics → learning evidence →
refinement suggestion. Not a second trading authority. AI may suggest a
refinement and must not activate it.
"""

from app.paper_evaluation.contracts import (
    NARRATIVE_NOT_FACT_BANNER,
    PAPER_EVALUATION_SCHEMA,
    REFINEMENT_NOT_ACTIVATED,
    DataQualityClass,
    PaperEvaluationFacts,
    PaperEvaluationObservation,
    PaperEvaluationStage,
    PaperEvaluationSummary,
    RefinementSuggestion,
)
from app.paper_evaluation.errors import (
    CrossTenantPaperEvaluationError,
    NarrativeCannotRewriteEvaluationFactsError,
    PaperEvaluationConflictError,
    PaperEvaluationNotTradingAuthorityError,
    RefinementActivationForbiddenError,
)
from app.paper_evaluation.journal_facts import SqlAlchemyJournalExcursionPort
from app.paper_evaluation.memory import InMemoryPaperEvaluationStore
from app.paper_evaluation.query import PaperEvaluationQueryService
from app.paper_evaluation.recorder import (
    PaperEvaluationRecorder,
    observe_watcher_evaluation,
)
from app.paper_evaluation.refinement import refinement_suggestions, refuse_activation

__all__ = [
    "NARRATIVE_NOT_FACT_BANNER",
    "PAPER_EVALUATION_SCHEMA",
    "REFINEMENT_NOT_ACTIVATED",
    "CrossTenantPaperEvaluationError",
    "DataQualityClass",
    "InMemoryPaperEvaluationStore",
    "NarrativeCannotRewriteEvaluationFactsError",
    "PaperEvaluationConflictError",
    "PaperEvaluationFacts",
    "PaperEvaluationNotTradingAuthorityError",
    "PaperEvaluationObservation",
    "PaperEvaluationQueryService",
    "PaperEvaluationRecorder",
    "PaperEvaluationStage",
    "PaperEvaluationSummary",
    "RefinementActivationForbiddenError",
    "RefinementSuggestion",
    "SqlAlchemyJournalExcursionPort",
    "observe_watcher_evaluation",
    "refinement_suggestions",
    "refuse_activation",
]

"""Paper-only boundary for the interactive agent.

The agent has no setting that turns real trading on. Asking it to do so is a
refusal, and the explicit enablement method raises before any assignment.
"""

from __future__ import annotations

from app.core.config import Settings
from app.core.errors import TradingPolicyError
from app.core.paper_safety import assert_permanent_paper_mode
from app.interactive_agent.contracts import (
    AgentCapability,
    AgentCapabilityCatalog,
    ArtifactKind,
    CapabilityDescriptor,
    CapabilityStatus,
    PaperSafetyContract,
    ProvenanceSource,
)

_REFUSAL = "The interactive agent cannot enable real trading."


def paper_safety_contract(settings: Settings) -> PaperSafetyContract:
    """Return the paper contract after the permanent paper invariant is checked."""
    assert_permanent_paper_mode(settings)
    if settings.enable_real_trading or settings.real_trading_enabled:
        raise TradingPolicyError(
            _REFUSAL,
            details={"real_trading_enabled": False, "execution_attempted": False},
        )
    return PaperSafetyContract(exchange_mode=settings.exchange_mode.value)


def refuse_real_trading_enablement() -> None:
    """Refuse enablement. This function does not read or write trading settings."""
    raise TradingPolicyError(
        _REFUSAL,
        details={
            "real_trading_enabled": False,
            "execution_attempted": False,
            "agent_can_enable_real_trading": False,
        },
    )


def capability_catalog(settings: Settings) -> AgentCapabilityCatalog:
    """Describe implemented reads, proposal boundaries, and unimplemented contracts."""
    safety = paper_safety_contract(settings)
    items = [
        CapabilityDescriptor(
            capability=AgentCapability.DAILY_REVIEW,
            status=CapabilityStatus.READ_THROUGH,
            authority="DailyReviewService",
            notes=(
                "Reads recorded daily evidence with source IDs and separate facts, user "
                "observations, system inference and research suggestions. UTC by default."
            ),
        ),
        CapabilityDescriptor(
            capability=AgentCapability.GENERAL_CONVERSATION,
            status=CapabilityStatus.IMPLEMENTED,
            authority="ConversationService and ModelRouter",
            notes=(
                "The HTTP turn stores the existing model reply. That text does not "
                "confirm or write records."
            ),
        ),
        CapabilityDescriptor(
            capability=AgentCapability.MARKET_AND_PORTFOLIO,
            status=CapabilityStatus.READ_THROUGH,
            authority="CanonicalEvidenceService and PaperPortfolioService",
            notes=(
                "Market answers use canonical perpetual evidence. Unavailable and "
                "stale stay explicit. No price is invented."
            ),
        ),
        CapabilityDescriptor(
            capability=AgentCapability.STRATEGY_ANALYTICS,
            status=CapabilityStatus.READ_THROUGH,
            authority="StrategyAnalyticsService.compute /strategy-analytics/report",
            notes=(
                "Reads closed canonical journal outcomes with strategy/version/stage filters. "
                "Retains metric samples, confidence, missing-data warnings and limitations. "
                "Descriptive history never establishes profitability."
            ),
        ),
        CapabilityDescriptor(
            capability=AgentCapability.GOVERNED_LEARNING,
            status=CapabilityStatus.READ_THROUGH,
            authority="StrategyPromotionService",
            notes="Bounded proposal, replay, paper validation, active-version and rollback reads. "
            "Agent prose cannot approve promotion or enable live execution.",
        ),
        CapabilityDescriptor(
            capability=AgentCapability.STRATEGY_RETRIEVAL,
            status=CapabilityStatus.IMPLEMENTED,
            authority="StrategyLibraryService",
            notes="Lists the caller's strategies. It does not create or update versions.",
        ),
        CapabilityDescriptor(
            capability=AgentCapability.STRATEGY_AUTHORING,
            status=CapabilityStatus.IMPLEMENTED,
            authority="StrategyProposalService drafts",
            notes="Creates a non-authoritative draft preview. Chat text does not confirm it.",
        ),
        CapabilityDescriptor(
            capability=AgentCapability.PATTERN_AND_RULE_CAPTURE,
            status=CapabilityStatus.IMPLEMENTED,
            authority="conversation transcript proposal",
            notes="Stores a rule proposal. It does not write structured rules or versions.",
        ),
        CapabilityDescriptor(
            capability=AgentCapability.TRADE_DISCUSSION,
            status=CapabilityStatus.READ_THROUGH,
            authority="JournalService and conversation transcript",
            notes="Discusses stored trades. Order requests become non-executable proposals.",
        ),
        CapabilityDescriptor(
            capability=AgentCapability.PRE_TRADE_REASONING,
            status=CapabilityStatus.IMPLEMENTED,
            authority="canonical pretrade, risk, sizing, plan and paper execution authorities",
            notes=(
                "paper_trade.prepare_execution prepares an exact canonical paper plan. "
                "Separate explicit hash-protected confirmation rechecks risk and executes "
                "through the existing paper gateway. Live trading remains disabled."
            ),
        ),
        CapabilityDescriptor(
            capability=AgentCapability.JOURNAL_CAPTURE,
            status=CapabilityStatus.IMPLEMENTED,
            authority="JournalService after explicit confirm",
            notes="A turn only proposes. Confirm with the content hash writes one journal row.",
        ),
        CapabilityDescriptor(
            capability=AgentCapability.POST_TRADE_REFLECTION,
            status=CapabilityStatus.READ_THROUGH,
            authority="CoachingService.summary and lesson proposal",
            notes="Coaching is read. Lesson proposals are not accepted into lesson review.",
        ),
        CapabilityDescriptor(
            capability=AgentCapability.KNOWLEDGE_RETRIEVAL,
            status=CapabilityStatus.IMPLEMENTED,
            authority="documents and chunks tables",
            notes="Lexical search of the existing knowledge store. Qdrant is not required.",
        ),
        CapabilityDescriptor(
            capability=AgentCapability.STATISTICS_AND_PERFORMANCE,
            status=CapabilityStatus.READ_THROUGH,
            authority="PerformanceService.build_report",
            notes="Reads stored paper positions. It does not persist a performance snapshot.",
        ),
        CapabilityDescriptor(
            capability=AgentCapability.SCREENSHOT_ANALYSIS,
            status=CapabilityStatus.CONTRACT_ONLY,
            authority="none",
            notes="No image is fetched or interpreted.",
        ),
        CapabilityDescriptor(
            capability=AgentCapability.VOICE_IO,
            status=CapabilityStatus.CONTRACT_ONLY,
            authority="none",
            notes="No audio is transcribed or synthesized.",
        ),
        CapabilityDescriptor(
            capability=AgentCapability.PERSISTENT_CONTEXT,
            status=CapabilityStatus.IMPLEMENTED,
            authority="ConversationService",
            notes="Prior user turns are loaded from the conversation transcript.",
        ),
    ]
    return AgentCapabilityCatalog(
        paper_safety=safety,
        items=items,
        artifact_kinds=list(ArtifactKind),
        provenance_sources=list(ProvenanceSource),
    )

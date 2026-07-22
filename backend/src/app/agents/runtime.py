"""Injectable runtime dependencies for agent nodes (controlled boundaries only)."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.guardrails.service import GuardrailService
from app.observability.emitters import ObservabilityEmitter
from app.providers.factory import resolve_providers
from app.providers.llm import LLMProvider
from app.services.audit_service import AuditService
from app.services.market_data_service import MarketDataService
from app.services.narrative_service import NarrativeService
from app.services.quota_service import QuotaService
from app.services.rag_service import RagService, build_rag_service
from app.services.risk_service import RiskService
from app.services.strategy_service import StrategyService
from app.services.usage_service import UsageService
from app.services.workflow_persistence_service import WorkflowPersistenceService
from app.tools.registry import ToolRegistry, build_default_registry


@dataclass
class AgentRuntime:
    """Services and tools available to graph nodes — never raw providers or DB."""

    settings: Settings
    risk_service: RiskService
    strategy_service: StrategyService
    tool_registry: ToolRegistry
    market_data_service: MarketDataService | None = None
    llm_provider: LLMProvider | None = None
    narrative_service: NarrativeService | None = None
    rag_service: RagService = field(default_factory=lambda: build_rag_service())
    guardrails: GuardrailService = field(default_factory=GuardrailService)
    audit_service: AuditService = field(default_factory=AuditService)
    usage_service: UsageService = field(default_factory=UsageService)
    quota_service: QuotaService | None = None
    observability: ObservabilityEmitter | None = None
    workflow_persistence: WorkflowPersistenceService | None = None
    session: Session | None = None
    quota_exceeded: bool = False
    rate_limited: bool = False

    def __post_init__(self) -> None:
        if self.llm_provider is None:
            self.llm_provider = resolve_providers(self.settings).llm
        if self.narrative_service is None and self.llm_provider is not None:
            self.narrative_service = NarrativeService(
                llm_provider=self.llm_provider,
                llm_model=self.settings.llm_model,
                enabled=self.settings.narrative_llm_enabled,
            )
        if self.observability is None:
            self.observability = ObservabilityEmitter(
                audit_service=self.audit_service,
                usage_service=self.usage_service,
            )

    @classmethod
    def from_session(
        cls,
        session: Session,
        *,
        settings: Settings,
        risk_service: RiskService,
        strategy_service: StrategyService,
        tool_registry: ToolRegistry | None = None,
        market_data_service: MarketDataService | None = None,
        strict_observability: bool = False,
    ) -> AgentRuntime:
        """Build runtime with DB-backed audit, usage, and RAG services."""
        audit = AuditService(session, strict_mode=strict_observability)
        usage = UsageService(session, strict_mode=strict_observability)
        rag = build_rag_service(
            settings,
            session,
            audit_service=audit,
            usage_service=usage,
        )
        tools = tool_registry or build_default_registry(
            settings,
            rag_service=rag,
            db_session=session,
        )
        if market_data_service is None:
            from app.providers.factory import resolve_market_data_provider
            from app.services.indicator_service import IndicatorService
            from app.services.market_cache import MarketDataCache
            from app.services.market_data_service import MarketDataService

            market_data_service = MarketDataService(
                resolve_market_data_provider(settings),
                cache=MarketDataCache(settings),
                indicator_service=IndicatorService(),
                strategy_service=strategy_service,
            )
        workflow = WorkflowPersistenceService(session, audit)
        quota = QuotaService(session, audit_service=audit)
        return cls(
            settings=settings,
            risk_service=risk_service,
            strategy_service=strategy_service,
            tool_registry=tools,
            market_data_service=market_data_service,
            rag_service=rag,
            audit_service=audit,
            usage_service=usage,
            quota_service=quota,
            workflow_persistence=workflow,
            session=session,
            observability=ObservabilityEmitter(audit_service=audit, usage_service=usage),
        )

    @property
    def real_trading_allowed(self) -> bool:
        """Hard gate: real exchange execution is never enabled in this scaffold."""
        return False

"""FastAPI dependency-injection providers."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.providers.exchange.factory import resolve_exchange_execution_provider
from app.providers.factory import resolve_market_data_provider
from app.providers.registry import ProviderRegistry, get_provider_registry
from app.services.alert_delivery_service import AlertDeliveryService
from app.services.analytics.facade import TradingAnalyticsFacade
from app.services.approval_service import ApprovalService
from app.services.audit_service import AuditService
from app.services.backtest_service import BacktestService
from app.services.coaching import CoachingService
from app.services.dashboard_summary_service import DashboardSummaryService
from app.services.execution_service import ExecutionService
from app.services.historical_candle_service import HistoricalCandleService
from app.services.human_vs_system_service import HumanVsSystemService
from app.services.indicator_service import IndicatorService
from app.services.journal_rag_sync_service import JournalRagSyncService
from app.services.journal_service import JournalService
from app.services.learning_analytics import LearningAnalyticsService
from app.services.lesson_candidate_service import LessonCandidateService
from app.services.loss_acceptance_service import LossAcceptanceService
from app.services.manual_level_service import ManualLevelService
from app.services.market_cache import MarketDataCache
from app.services.market_data_service import MarketDataService
from app.services.market_service import MarketService
from app.services.market_watcher_bridge_service import MarketWatcherBridgeService
from app.services.market_watcher_service import MarketWatcherService
from app.services.notifications.preferences_service import NotificationPreferencesService
from app.services.paper_alert_service import PaperAlertService
from app.services.paper_eligibility_service import PaperEligibilityService
from app.services.paper_scheduler_service import PaperSchedulerService
from app.services.paper_validation_candidate_service import PaperValidationCandidateService
from app.services.paper_validation_draft_service import PaperValidationDraftService
from app.services.paper_validation_run_plan_service import PaperValidationRunPlanService
from app.services.paper_validation_run_session_service import PaperValidationRunSessionService
from app.services.paper_validation_runtime_service import PaperValidationRuntimeService
from app.services.paper_validation_service import PaperValidationService
from app.services.paper_validation_session_observation_service import (
    PaperValidationSessionObservationService,
)
from app.services.paper_validation_session_result_service import PaperValidationSessionResultService
from app.services.performance_service import PerformanceService
from app.services.position_service import PositionService
from app.services.position_sizing_service import PositionSizingService
from app.services.pretrade_analysis_service import PreTradeAnalysisService
from app.services.proposal_service import ProposalService
from app.services.quota_service import QuotaService
from app.services.rag_service import RagService, build_rag_service
from app.services.risk.settings_service import RiskSettingsService
from app.services.risk_service import RiskService
from app.services.strategy_library_service import StrategyLibraryService
from app.services.strategy_quality import StrategyQualityService
from app.services.strategy_service import StrategyService
from app.services.strategy_testability_service import StrategyTestabilityService
from app.services.structure_from_text_service import StructureFromTextService
from app.services.structured_rules_service import StructuredRulesService
from app.services.usage_service import UsageService
from app.services.validation_priority import ValidationPriorityService
from app.services.workflow_service import WorkflowService
from app.strategies.registry import StrategyRegistry, get_strategy_registry
from app.tools.registry import ToolRegistry, get_tool_registry

SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[Session, Depends(get_session)]
ProviderRegistryDep = Annotated[ProviderRegistry, Depends(get_provider_registry)]
ToolRegistryDep = Annotated[ToolRegistry, Depends(get_tool_registry)]
StrategyRegistryDep = Annotated[StrategyRegistry, Depends(get_strategy_registry)]


def get_risk_service() -> RiskService:
    return RiskService()


def get_strategy_service(
    registry: StrategyRegistryDep,
) -> StrategyService:
    return StrategyService(registry=registry)


RiskServiceDep = Annotated[RiskService, Depends(get_risk_service)]
StrategyServiceDep = Annotated[StrategyService, Depends(get_strategy_service)]


def get_audit_service(session: SessionDep, settings: SettingsDep) -> AuditService:
    return AuditService(session, strict_mode=settings.observability_strict_mode)


def get_usage_service(session: SessionDep, settings: SettingsDep) -> UsageService:
    return UsageService(session, strict_mode=settings.observability_strict_mode)


def get_quota_service(session: SessionDep) -> QuotaService:
    audit = AuditService(session)
    return QuotaService(session, audit_service=audit)


AuditServiceDep = Annotated[AuditService, Depends(get_audit_service)]
UsageServiceDep = Annotated[UsageService, Depends(get_usage_service)]
QuotaServiceDep = Annotated[QuotaService, Depends(get_quota_service)]


def get_rag_service(session: SessionDep, settings: SettingsDep) -> RagService:
    audit = AuditService(session, strict_mode=settings.observability_strict_mode)
    usage = UsageService(session, strict_mode=settings.observability_strict_mode)
    return build_rag_service(
        settings,
        session,
        audit_service=audit,
        usage_service=usage,
    )


RagServiceDep = Annotated[RagService, Depends(get_rag_service)]


def get_market_service(session: SessionDep, audit_service: AuditServiceDep) -> MarketService:
    return MarketService(session, audit_service)


def get_proposal_service(session: SessionDep, audit_service: AuditServiceDep) -> ProposalService:
    return ProposalService(session, audit_service)


def get_approval_service(session: SessionDep, audit_service: AuditServiceDep) -> ApprovalService:
    return ApprovalService(session, audit_service)


def get_execution_service(
    session: SessionDep,
    settings: SettingsDep,
    audit_service: AuditServiceDep,
) -> ExecutionService:
    exchange_execution = resolve_exchange_execution_provider(settings)
    return ExecutionService(
        session,
        settings,
        audit_service,
        exchange_execution=exchange_execution,
    )


def get_position_service(session: SessionDep, audit_service: AuditServiceDep) -> PositionService:
    return PositionService(session, audit_service)


def get_performance_service(session: SessionDep) -> PerformanceService:
    return PerformanceService(session)


PerformanceServiceDep = Annotated[PerformanceService, Depends(get_performance_service)]


def get_journal_service(
    session: SessionDep,
    audit_service: AuditServiceDep,
    settings: SettingsDep,
    rag_service: RagServiceDep,
) -> JournalService:
    sync = JournalRagSyncService(rag_service, settings)
    return JournalService(session, audit_service, rag_sync=sync)


def get_workflow_service(
    proposal_service: ProposalServiceDep,
    approval_service: ApprovalServiceDep,
) -> WorkflowService:
    return WorkflowService(proposal_service, approval_service)


def get_market_data_service(
    settings: SettingsDep,
    strategy_service: StrategyServiceDep,
) -> MarketDataService:
    provider = resolve_market_data_provider(settings)
    cache = MarketDataCache(settings)
    return MarketDataService(
        provider,
        cache=cache,
        indicator_service=IndicatorService(),
        strategy_service=strategy_service,
    )


MarketDataServiceDep = Annotated[MarketDataService, Depends(get_market_data_service)]
MarketServiceDep = Annotated[MarketService, Depends(get_market_service)]
ProposalServiceDep = Annotated[ProposalService, Depends(get_proposal_service)]
ApprovalServiceDep = Annotated[ApprovalService, Depends(get_approval_service)]
ExecutionServiceDep = Annotated[ExecutionService, Depends(get_execution_service)]
PositionServiceDep = Annotated[PositionService, Depends(get_position_service)]
JournalServiceDep = Annotated[JournalService, Depends(get_journal_service)]
WorkflowServiceDep = Annotated[WorkflowService, Depends(get_workflow_service)]


def get_analytics_facade(session: SessionDep) -> TradingAnalyticsFacade:
    return TradingAnalyticsFacade(session)


AnalyticsFacadeDep = Annotated[TradingAnalyticsFacade, Depends(get_analytics_facade)]


def get_learning_analytics_service(session: SessionDep) -> LearningAnalyticsService:
    return LearningAnalyticsService(session)


LearningAnalyticsServiceDep = Annotated[
    LearningAnalyticsService, Depends(get_learning_analytics_service)
]


def get_validation_priority_service(session: SessionDep) -> ValidationPriorityService:
    return ValidationPriorityService(session)


ValidationPriorityServiceDep = Annotated[
    ValidationPriorityService, Depends(get_validation_priority_service)
]


def get_coaching_service(session: SessionDep) -> CoachingService:
    return CoachingService(session)


CoachingServiceDep = Annotated[CoachingService, Depends(get_coaching_service)]


def get_strategy_quality_service(session: SessionDep) -> StrategyQualityService:
    return StrategyQualityService(session)


StrategyQualityServiceDep = Annotated[StrategyQualityService, Depends(get_strategy_quality_service)]


def get_position_sizing_service() -> PositionSizingService:
    return PositionSizingService()


def get_loss_acceptance_service() -> LossAcceptanceService:
    return LossAcceptanceService()


def get_strategy_library_service(
    session: SessionDep,
    rag_service: RagServiceDep,
) -> StrategyLibraryService:
    return StrategyLibraryService(session, rag_service=rag_service)


def get_manual_level_service(session: SessionDep) -> ManualLevelService:
    return ManualLevelService(session)


def get_pretrade_analysis_service(
    session: SessionDep,
    market_data_service: MarketDataServiceDep,
) -> PreTradeAnalysisService:
    return PreTradeAnalysisService(session, market_data_service)


def get_human_vs_system_service(
    session: SessionDep,
    settings: SettingsDep,
) -> HumanVsSystemService:
    provider = resolve_market_data_provider(settings)
    candle_service = HistoricalCandleService(session, provider, settings)
    return HumanVsSystemService(session, historical_candle_service=candle_service)


def get_lesson_candidate_service(
    session: SessionDep,
    settings: SettingsDep,
    rag_service: RagServiceDep,
) -> LessonCandidateService:
    audit = AuditService(session, strict_mode=settings.observability_strict_mode)
    return LessonCandidateService(
        session,
        audit_service=audit,
        rag_service=rag_service,
        settings=settings,
    )


def get_strategy_testability_service(session: SessionDep) -> StrategyTestabilityService:
    return StrategyTestabilityService(session)


def get_structured_rules_service(session: SessionDep) -> StructuredRulesService:
    return StructuredRulesService(session)


def get_structure_from_text_service() -> StructureFromTextService:
    return StructureFromTextService()


def get_backtest_service(session: SessionDep, settings: SettingsDep) -> BacktestService:
    return BacktestService(session, settings)


def get_paper_validation_service(session: SessionDep) -> PaperValidationService:
    return PaperValidationService(session)


def get_paper_validation_runtime_service(
    session: SessionDep, settings: SettingsDep
) -> PaperValidationRuntimeService:
    return PaperValidationRuntimeService(session, settings)


def get_paper_eligibility_service(
    session: SessionDep, settings: SettingsDep
) -> PaperEligibilityService:
    return PaperEligibilityService(session, settings)


def get_paper_alert_service(session: SessionDep, settings: SettingsDep) -> PaperAlertService:
    delivery = AlertDeliveryService(session, settings)
    return PaperAlertService(session, delivery_service=delivery)


def get_paper_validation_draft_service(session: SessionDep) -> PaperValidationDraftService:
    return PaperValidationDraftService(session)


def get_paper_validation_candidate_service(session: SessionDep) -> PaperValidationCandidateService:
    return PaperValidationCandidateService(session)


def get_paper_validation_run_plan_service(session: SessionDep) -> PaperValidationRunPlanService:
    return PaperValidationRunPlanService(session)


def get_paper_validation_run_session_service(
    session: SessionDep,
) -> PaperValidationRunSessionService:
    return PaperValidationRunSessionService(session)


def get_paper_validation_session_observation_service(
    session: SessionDep,
) -> PaperValidationSessionObservationService:
    return PaperValidationSessionObservationService(session)


def get_paper_validation_session_result_service(
    session: SessionDep,
) -> PaperValidationSessionResultService:
    return PaperValidationSessionResultService(session)


def get_alert_delivery_service(session: SessionDep, settings: SettingsDep) -> AlertDeliveryService:
    return AlertDeliveryService(session, settings)


def get_market_watcher_bridge_service(
    session: SessionDep, settings: SettingsDep, audit_service: AuditServiceDep
) -> MarketWatcherBridgeService:
    return MarketWatcherBridgeService(session, settings, audit_service=audit_service)


def get_market_watcher_service(session: SessionDep, settings: SettingsDep) -> MarketWatcherService:
    return MarketWatcherService(session, settings)


def get_paper_scheduler_service(
    session: SessionDep, settings: SettingsDep, audit_service: AuditServiceDep
) -> PaperSchedulerService:
    return PaperSchedulerService(session, settings, audit_service=audit_service)


def get_historical_candle_service(
    session: SessionDep,
    settings: SettingsDep,
    strategy_service: StrategyServiceDep,
) -> HistoricalCandleService:
    provider = resolve_market_data_provider(settings)
    _ = strategy_service
    return HistoricalCandleService(session, provider, settings)


PositionSizingServiceDep = Annotated[PositionSizingService, Depends(get_position_sizing_service)]
LossAcceptanceServiceDep = Annotated[LossAcceptanceService, Depends(get_loss_acceptance_service)]
StrategyLibraryServiceDep = Annotated[StrategyLibraryService, Depends(get_strategy_library_service)]
ManualLevelServiceDep = Annotated[ManualLevelService, Depends(get_manual_level_service)]
PreTradeAnalysisServiceDep = Annotated[
    PreTradeAnalysisService, Depends(get_pretrade_analysis_service)
]
HumanVsSystemServiceDep = Annotated[HumanVsSystemService, Depends(get_human_vs_system_service)]
LessonCandidateServiceDep = Annotated[LessonCandidateService, Depends(get_lesson_candidate_service)]
StrategyTestabilityServiceDep = Annotated[
    StrategyTestabilityService, Depends(get_strategy_testability_service)
]
StructuredRulesServiceDep = Annotated[StructuredRulesService, Depends(get_structured_rules_service)]
StructureFromTextServiceDep = Annotated[
    StructureFromTextService, Depends(get_structure_from_text_service)
]
BacktestServiceDep = Annotated[BacktestService, Depends(get_backtest_service)]
PaperValidationServiceDep = Annotated[PaperValidationService, Depends(get_paper_validation_service)]
PaperValidationRuntimeServiceDep = Annotated[
    PaperValidationRuntimeService, Depends(get_paper_validation_runtime_service)
]
PaperEligibilityServiceDep = Annotated[
    PaperEligibilityService, Depends(get_paper_eligibility_service)
]
PaperAlertServiceDep = Annotated[PaperAlertService, Depends(get_paper_alert_service)]
PaperValidationDraftServiceDep = Annotated[
    PaperValidationDraftService, Depends(get_paper_validation_draft_service)
]
PaperValidationCandidateServiceDep = Annotated[
    PaperValidationCandidateService, Depends(get_paper_validation_candidate_service)
]
PaperValidationRunPlanServiceDep = Annotated[
    PaperValidationRunPlanService, Depends(get_paper_validation_run_plan_service)
]
PaperValidationRunSessionServiceDep = Annotated[
    PaperValidationRunSessionService, Depends(get_paper_validation_run_session_service)
]
PaperValidationSessionObservationServiceDep = Annotated[
    PaperValidationSessionObservationService,
    Depends(get_paper_validation_session_observation_service),
]
PaperValidationSessionResultServiceDep = Annotated[
    PaperValidationSessionResultService, Depends(get_paper_validation_session_result_service)
]
AlertDeliveryServiceDep = Annotated[AlertDeliveryService, Depends(get_alert_delivery_service)]
MarketWatcherServiceDep = Annotated[MarketWatcherService, Depends(get_market_watcher_service)]
MarketWatcherBridgeServiceDep = Annotated[
    MarketWatcherBridgeService, Depends(get_market_watcher_bridge_service)
]
PaperSchedulerServiceDep = Annotated[PaperSchedulerService, Depends(get_paper_scheduler_service)]
HistoricalCandleServiceDep = Annotated[
    HistoricalCandleService, Depends(get_historical_candle_service)
]


def get_dashboard_summary_service(
    session: SessionDep,
    settings: SettingsDep,
    audit_service: AuditServiceDep,
) -> DashboardSummaryService:
    return DashboardSummaryService(
        session,
        settings,
        risk_settings=RiskSettingsService(session, audit_service),
    )


DashboardSummaryServiceDep = Annotated[
    DashboardSummaryService, Depends(get_dashboard_summary_service)
]


def get_notification_preferences_service(
    session: SessionDep,
    audit_service: AuditServiceDep,
) -> NotificationPreferencesService:
    return NotificationPreferencesService(session, audit_service)


NotificationPreferencesServiceDep = Annotated[
    NotificationPreferencesService, Depends(get_notification_preferences_service)
]


def get_risk_settings_service(
    session: SessionDep,
    audit_service: AuditServiceDep,
) -> RiskSettingsService:
    return RiskSettingsService(session, audit_service)


RiskSettingsServiceDep = Annotated[RiskSettingsService, Depends(get_risk_settings_service)]

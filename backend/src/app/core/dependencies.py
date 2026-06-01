"""FastAPI dependency-injection providers."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.providers.factory import resolve_market_data_provider
from app.providers.registry import ProviderRegistry, get_provider_registry
from app.services.approval_service import ApprovalService
from app.services.audit_service import AuditService
from app.services.execution_service import ExecutionService
from app.services.indicator_service import IndicatorService
from app.services.journal_rag_sync_service import JournalRagSyncService
from app.services.journal_service import JournalService
from app.services.market_cache import MarketDataCache
from app.services.market_data_service import MarketDataService
from app.services.market_service import MarketService
from app.services.position_service import PositionService
from app.services.proposal_service import ProposalService
from app.services.quota_service import QuotaService
from app.services.rag_service import RagService, build_rag_service
from app.services.risk_service import RiskService
from app.services.strategy_service import StrategyService
from app.services.usage_service import UsageService
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
    return ExecutionService(session, settings, audit_service)


def get_position_service(session: SessionDep, audit_service: AuditServiceDep) -> PositionService:
    return PositionService(session, audit_service)


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

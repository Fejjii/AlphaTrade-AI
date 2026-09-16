"""Deny-by-default SQLAlchemy persistence interceptor for READ_ONLY operations.

A single before_flush listener plus repository ``add`` recheck. Unscoped
sessions (no IntentDecision) keep existing HTTP API behavior.
"""

from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.orm import Mapper, Session

from app.core.errors import PersistencePolicyError
from app.core.operation_policy import (
    PersistenceKind,
    assert_write_allowed,
    get_operation_decision,
)
from app.db.models import AuditLog, ModelCallAttempt, OrganizationQuota, UsageEvent
from app.schemas.agent import OperationClass

_ALLOWED_READ_ONLY_MODELS: frozenset[type[object]] = frozenset(
    {
        AuditLog,
        UsageEvent,
        OrganizationQuota,
        ModelCallAttempt,
    }
)

_MODEL_KIND: dict[str, PersistenceKind] = {
    "AuditLog": PersistenceKind.AUDIT,
    "UsageEvent": PersistenceKind.USAGE,
    "OrganizationQuota": PersistenceKind.QUOTA,
    "ModelCallAttempt": PersistenceKind.USAGE,
    "TradeProposal": PersistenceKind.PROPOSAL,
    "ApprovalRequest": PersistenceKind.APPROVAL,
    "Order": PersistenceKind.ORDER,
    "Position": PersistenceKind.POSITION,
    "ExchangeOrder": PersistenceKind.EXECUTION,
    "ExchangeFill": PersistenceKind.FILL,
    "UserStrategy": PersistenceKind.STRATEGY,
    "UserStrategyVersion": PersistenceKind.STRATEGY,
    "StrategyLifecycleEvent": PersistenceKind.STRATEGY,
    "SetupDefinition": PersistenceKind.SETUP,
    "GlobalSetupTemplate": PersistenceKind.SETUP,
    "CompiledSetupDefinition": PersistenceKind.SETUP,
    "SetupMigrationRun": PersistenceKind.SETUP,
    "ManualChartLevel": PersistenceKind.STRATEGY,
    "ManualLevelRevision": PersistenceKind.STRATEGY,
    "BacktestRun": PersistenceKind.BACKTEST,
    "BacktestTrade": PersistenceKind.BACKTEST,
    "BacktestDataset": PersistenceKind.BACKTEST,
    "PaperValidationRun": PersistenceKind.PAPER_VALIDATION,
    "PaperSignal": PersistenceKind.PAPER_VALIDATION,
    "PaperTrade": PersistenceKind.PAPER_VALIDATION,
    "PaperTradeEvent": PersistenceKind.PAPER_VALIDATION,
    "PaperValidationMetricSnapshot": PersistenceKind.PAPER_VALIDATION,
    "PaperValidationSchedulerConfig": PersistenceKind.WATCHER,
    "PaperValidationRuntimeHistory": PersistenceKind.PAPER_VALIDATION,
    "PaperValidationAlert": PersistenceKind.NOTIFICATION,
    "PaperValidationDraft": PersistenceKind.PAPER_VALIDATION,
    "PaperValidationCandidate": PersistenceKind.CANDIDATE,
    "PaperValidationRunPlan": PersistenceKind.PAPER_VALIDATION,
    "PaperValidationRunSession": PersistenceKind.PAPER_VALIDATION,
    "PaperValidationSessionObservation": PersistenceKind.PAPER_VALIDATION,
    "PaperValidationSessionResult": PersistenceKind.PAPER_VALIDATION,
    "MarketWatcherObservation": PersistenceKind.WATCHER,
    "MarketWatcherScanRecord": PersistenceKind.WATCHER,
    "MarketWatcherBridgeDecision": PersistenceKind.WATCHER,
    "WatchlistItem": PersistenceKind.WATCHER,
    "JournalTrade": PersistenceKind.JOURNAL,
    "TradeJournal": PersistenceKind.JOURNAL,
    "JournalTradeEvidence": PersistenceKind.JOURNAL,
    "JournalTradeRuleCheck": PersistenceKind.JOURNAL,
    "JournalTradeObservation": PersistenceKind.JOURNAL,
    "JournalImportBatch": PersistenceKind.JOURNAL,
    "JournalTradeAttachment": PersistenceKind.JOURNAL,
    "JournalLifecycleEvent": PersistenceKind.JOURNAL,
    "JournalProjectionReceipt": PersistenceKind.JOURNAL,
    "JournalTradeVenueCorrection": PersistenceKind.JOURNAL,
    "LessonCandidate": PersistenceKind.JOURNAL,
    "UserRiskSettings": PersistenceKind.RISK_CONFIG,
    "KillSwitchState": PersistenceKind.RISK_CONFIG,
    "DailyRiskState": PersistenceKind.RISK_CONFIG,
    "RiskEvent": PersistenceKind.RISK_CONFIG,
    "UserNotificationPreferences": PersistenceKind.NOTIFICATION,
    "StrategySignal": PersistenceKind.CANDIDATE,
    "TradingViewSignal": PersistenceKind.CANDIDATE,
    "PaperSignalOrchestrationDecision": PersistenceKind.CANDIDATE,
    "TradePlanRevision": PersistenceKind.TRADE_PLAN,
    "ApprovalAuthorization": PersistenceKind.AUTHORIZATION,
    "ExecutionAccount": PersistenceKind.EXECUTION,
    "ExecutionIdempotencyBinding": PersistenceKind.EXECUTION,
    "ExecutionCommand": PersistenceKind.EXECUTION,
    "PlanEntryExecutionClaim": PersistenceKind.EXECUTION,
    "AccountSafetyEpoch": PersistenceKind.RISK_CONFIG,
    "AccountRiskAccountingState": PersistenceKind.RISK_CONFIG,
    "ExecutionReceipt": PersistenceKind.EXECUTION,
    "ExecutionTransition": PersistenceKind.EXECUTION,
    "ExecutionProjection": PersistenceKind.EXECUTION,
    "RiskReservation": PersistenceKind.EXECUTION,
    "VenueSubmitEffect": PersistenceKind.EXECUTION,
    "ExecutionFillFact": PersistenceKind.EXECUTION,
}


def persistence_kind_for(entity: object) -> PersistenceKind:
    name = type(entity).__name__
    return _MODEL_KIND.get(name, PersistenceKind.OTHER)


def is_readonly_allowed_model(entity: object) -> bool:
    return type(entity) in _ALLOWED_READ_ONLY_MODELS


def assert_entity_write_allowed(entity: object) -> None:
    """Service/repository recheck used independently of SQLAlchemy events."""
    decision = get_operation_decision()
    if decision is None or decision.operation_class is not OperationClass.READ_ONLY:
        return
    if is_readonly_allowed_model(entity):
        assert_write_allowed(persistence_kind_for(entity), decision)
        return
    raise PersistencePolicyError(
        f"READ_ONLY forbids domain write of {type(entity).__name__}.",
        details={
            "model": type(entity).__name__,
            "kind": persistence_kind_for(entity).value,
        },
    )


def _iter_pending_writes(session: Session) -> list[object]:
    pending: list[object] = []
    pending.extend(session.new)
    pending.extend(session.dirty)
    pending.extend(session.deleted)
    return pending


def enforce_readonly_flush(session: Session) -> None:
    """Raise if a READ_ONLY request is about to flush forbidden domain rows."""
    decision = get_operation_decision()
    if decision is None or decision.operation_class is not OperationClass.READ_ONLY:
        return
    for entity in _iter_pending_writes(session):
        if is_readonly_allowed_model(entity):
            continue
        raise PersistencePolicyError(
            f"READ_ONLY forbids domain write of {type(entity).__name__}.",
            details={
                "model": type(entity).__name__,
                "kind": persistence_kind_for(entity).value,
            },
        )


def _before_flush(session: Session, _flush_context: object, _instances: object) -> None:
    enforce_readonly_flush(session)


def install_persistence_firewall() -> None:
    """Register the Session before_flush interceptor (idempotent)."""
    if getattr(Session, "_alphatrade_readonly_firewall", False):
        return
    event.listen(Session, "before_flush", _before_flush)
    Session._alphatrade_readonly_firewall = True  # type: ignore[attr-defined]


# Mapper-level import keeps mypy aware this module depends on ORM maps.
_ = Mapper

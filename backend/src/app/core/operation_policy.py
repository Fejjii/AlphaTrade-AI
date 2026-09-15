"""Intent/operation policy context and WRITE allowlist (architecture §4 / §21).

Dispatch uses ``(intent, requested_action)``, never operation class alone.
Authorization issuance is permitted only for ``RequestedAction.APPROVE``.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from enum import StrEnum

from app.core.errors import PersistencePolicyError, TradingPolicyError
from app.schemas.agent import IntentDecision, OperationClass

_current_decision: ContextVar[IntentDecision | None] = ContextVar(
    "alphatrade_intent_decision", default=None
)


def get_operation_decision() -> IntentDecision | None:
    return _current_decision.get()


def set_operation_decision(decision: IntentDecision | None) -> Token[IntentDecision | None]:
    return _current_decision.set(decision)


def reset_operation_decision(token: Token[IntentDecision | None] | None = None) -> None:
    if token is not None:
        _current_decision.reset(token)
        return
    _current_decision.set(None)


@contextmanager
def operation_scope(decision: IntentDecision | None) -> Iterator[IntentDecision | None]:
    token = set_operation_decision(decision)
    try:
        yield decision
    finally:
        reset_operation_decision(token)


_RESTRICTIVE_RANK = {
    OperationClass.READ_ONLY: 0,
    OperationClass.JOURNAL: 1,
    OperationClass.CONFIGURATION: 2,
    OperationClass.PLAN: 3,
    OperationClass.APPROVAL: 4,
    OperationClass.MUTATION: 5,
    OperationClass.EXECUTION: 6,
}


def most_restrictive_class(*classes: OperationClass) -> OperationClass:
    """When classifiers disagree, choose the most restrictive class."""
    return min(classes, key=lambda cls: _RESTRICTIVE_RANK[cls])


def can_issue_authorization(decision: IntentDecision | None) -> bool:
    if decision is None:
        return False
    return decision.may_issue_authorization


def assert_authorization_issuance_allowed(decision: IntentDecision | None) -> None:
    """Repository methods for authorization issuance accept only APPROVE."""
    if can_issue_authorization(decision):
        return
    action = decision.requested_action.value if decision is not None else "none"
    raise TradingPolicyError(
        "Authorization issuance requires exact APPROVE. "
        f"requested_action={action} cannot create an authorization.",
        details={"requested_action": action},
    )


class PersistenceKind(StrEnum):
    AUDIT = "audit"
    QUOTA = "quota"
    USAGE = "usage"
    NON_DOMAIN_MEMORY = "non_domain_memory"
    PROPOSAL = "proposal"
    TRADE_PLAN = "trade_plan"
    APPROVAL = "approval"
    AUTHORIZATION = "authorization"
    EXECUTION = "execution"
    ORDER = "order"
    FILL = "fill"
    POSITION = "position"
    STRATEGY = "strategy"
    SETUP = "setup"
    BACKTEST = "backtest"
    PAPER_VALIDATION = "paper_validation"
    WATCHER = "watcher"
    CANDIDATE = "candidate"
    JOURNAL = "journal"
    RISK_CONFIG = "risk_config"
    NOTIFICATION = "notification"
    OTHER = "other"


_READ_ONLY_ALLOWED_KINDS = frozenset(
    {
        PersistenceKind.AUDIT,
        PersistenceKind.QUOTA,
        PersistenceKind.USAGE,
        PersistenceKind.NON_DOMAIN_MEMORY,
    }
)


def write_allowed(kind: PersistenceKind, decision: IntentDecision | None = None) -> bool:
    """Deny-by-default WRITE policy. Unscoped (no decision) allows existing HTTP APIs."""
    current = decision if decision is not None else get_operation_decision()
    if current is None:
        return True
    if current.operation_class is not OperationClass.READ_ONLY:
        return True
    return kind in _READ_ONLY_ALLOWED_KINDS


def assert_write_allowed(kind: PersistenceKind, decision: IntentDecision | None = None) -> None:
    if write_allowed(kind, decision):
        return
    current = decision if decision is not None else get_operation_decision()
    op = current.operation_class.value if current is not None else "unscoped"
    raise PersistencePolicyError(
        f"READ_ONLY persistence denied for {kind.value}.",
        details={"operation_class": op, "kind": kind.value},
    )

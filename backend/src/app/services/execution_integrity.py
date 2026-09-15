"""Named unique-constraint classification for Phase 1 execution protocol."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

IDEMPOTENCY_CONSTRAINT = "uq_execution_idempotency_binding"
PLAN_CLAIM_CONSTRAINT = "uq_plan_entry_execution_claim"
SAFETY_EPOCH_CONSTRAINT = "uq_account_safety_epoch"
RISK_ACCOUNTING_CONSTRAINT = "uq_account_risk_accounting_state"
CLIENT_ORDER_CONSTRAINT = "uq_venue_submit_effect_client_order_id"


def is_named_unique_violation(exc: IntegrityError, constraint_name: str) -> bool:
    """Return True only when ``exc`` is the named unique constraint.

    Unknown IntegrityError values must be re-raised by callers.
    """

    orig = getattr(exc, "orig", None)
    sources = [str(exc).lower()]
    if orig is not None:
        sources.append(str(orig).lower())
        diag = getattr(orig, "diag", None)
        if diag is not None:
            name = getattr(diag, "constraint_name", None)
            if name == constraint_name:
                return True
    joined = " ".join(sources)
    return constraint_name.lower() in joined


def is_idempotency_unique_violation(exc: IntegrityError) -> bool:
    if is_named_unique_violation(exc, IDEMPOTENCY_CONSTRAINT):
        return True
    message = str(getattr(exc, "orig", exc)).lower()
    return (
        "execution_idempotency_bindings" in message
        and "opaque_key" in message
        and "unique" in message
    )


def is_plan_claim_unique_violation(exc: IntegrityError) -> bool:
    if is_named_unique_violation(exc, PLAN_CLAIM_CONSTRAINT):
        return True
    message = str(getattr(exc, "orig", exc)).lower()
    return (
        "plan_entry_execution_claims" in message
        and "revision_id" in message
        and "unique" in message
    )


def is_safety_epoch_unique_violation(exc: IntegrityError) -> bool:
    if is_named_unique_violation(exc, SAFETY_EPOCH_CONSTRAINT):
        return True
    message = str(getattr(exc, "orig", exc)).lower()
    return "account_safety_epochs" in message and "unique" in message


def is_risk_accounting_unique_violation(exc: IntegrityError) -> bool:
    if is_named_unique_violation(exc, RISK_ACCOUNTING_CONSTRAINT):
        return True
    message = str(getattr(exc, "orig", exc)).lower()
    return "account_risk_accounting_states" in message and "unique" in message


def ensure_db_transaction(session: Session) -> None:
    """Open a caller-owned transaction so SAVEPOINT release cannot autocommit."""

    if not session.in_transaction():
        session.begin()

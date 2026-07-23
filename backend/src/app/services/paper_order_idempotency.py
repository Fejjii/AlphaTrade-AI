"""Bounded savepoint recovery for concurrent paper-order idempotency (AT-028)."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.repositories.orders import OrderRepository

if TYPE_CHECKING:
    from app.db.models import Order

ORDER_IDEMPOTENCY_CONSTRAINT = "uq_orders_idempotency_key"
DEFAULT_MAX_CONVERGENCE_ATTEMPTS = 10
DEFAULT_INITIAL_BACKOFF_SECONDS = 0.025
DEFAULT_MAX_BACKOFF_SECONDS = 0.2


def is_order_idempotency_unique_violation(exc: IntegrityError) -> bool:
    """Return True when ``exc`` is the authoritative order idempotency unique index."""
    orig = getattr(exc, "orig", None)
    if orig is None:
        return False
    diag = getattr(orig, "diag", None)
    if diag is not None:
        constraint = getattr(diag, "constraint_name", None)
        if constraint == ORDER_IDEMPOTENCY_CONSTRAINT:
            return True
    message = str(orig).lower()
    return ORDER_IDEMPOTENCY_CONSTRAINT in message or "orders.idempotency_key" in message


def wait_for_committed_order_by_idempotency_key(
    engine: Engine,
    idempotency_key: str,
    *,
    max_attempts: int = DEFAULT_MAX_CONVERGENCE_ATTEMPTS,
    initial_backoff_seconds: float = DEFAULT_INITIAL_BACKOFF_SECONDS,
    max_backoff_seconds: float = DEFAULT_MAX_BACKOFF_SECONDS,
) -> Order | None:
    """Poll with fresh read sessions until another transaction commits the order row."""
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    backoff = initial_backoff_seconds
    for attempt in range(max_attempts):
        with factory() as session:
            existing = OrderRepository(session).get_by_idempotency_key(idempotency_key)
            if existing is not None:
                return existing
        if attempt + 1 >= max_attempts:
            break
        time.sleep(backoff)
        backoff = min(backoff * 2, max_backoff_seconds)
    return None

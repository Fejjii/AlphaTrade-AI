"""Persistence for internal execution accounts and immutable plan revisions."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.db.models import ExchangeAccount, ExecutionAccount, TradePlanRevision
from app.repositories.base import SQLAlchemyRepository


class ExecutionAccountRepository(SQLAlchemyRepository[ExecutionAccount]):
    model = ExecutionAccount

    def get_scoped(
        self,
        account_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ExecutionAccount | None:
        stmt = select(ExecutionAccount).where(
            ExecutionAccount.id == account_id,
            ExecutionAccount.organization_id == organization_id,
            ExecutionAccount.user_id == user_id,
        )
        return self._session.scalar(stmt)


class ExchangeAccountBindingRepository(SQLAlchemyRepository[ExchangeAccount]):
    model = ExchangeAccount

    def get_scoped(
        self,
        exchange_account_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ExchangeAccount | None:
        stmt = select(ExchangeAccount).where(
            ExchangeAccount.id == exchange_account_id,
            ExchangeAccount.organization_id == organization_id,
            ExchangeAccount.user_id == user_id,
        )
        return self._session.scalar(stmt)


class TradePlanRevisionRepository(SQLAlchemyRepository[TradePlanRevision]):
    model = TradePlanRevision

    def get_scoped(
        self,
        revision_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        plan_id: uuid.UUID | None = None,
        account_id: uuid.UUID | None = None,
    ) -> TradePlanRevision | None:
        stmt = select(TradePlanRevision).where(
            TradePlanRevision.id == revision_id,
            TradePlanRevision.organization_id == organization_id,
            TradePlanRevision.user_id == user_id,
        )
        if plan_id is not None:
            stmt = stmt.where(TradePlanRevision.plan_id == plan_id)
        if account_id is not None:
            stmt = stmt.where(TradePlanRevision.account_id == account_id)
        return self._session.scalar(stmt)

    def list_for_plan_scoped(
        self,
        plan_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> list[TradePlanRevision]:
        stmt = (
            select(TradePlanRevision)
            .where(
                TradePlanRevision.plan_id == plan_id,
                TradePlanRevision.organization_id == organization_id,
                TradePlanRevision.user_id == user_id,
            )
            .order_by(TradePlanRevision.created_at, TradePlanRevision.id)
        )
        return list(self._session.scalars(stmt).all())

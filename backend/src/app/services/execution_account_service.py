"""Register one canonical paper identity without granting execution authority."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ForbiddenError
from app.db.models import ExecutionAccount, Membership
from app.schemas.audit import AuditRecordCreate
from app.schemas.common import ActorType, AuditEventType, MembershipRole
from app.schemas.execution_account import (
    PaperAccountRegistration,
    PaperAccountStatus,
    PaperExecutionAccount,
)
from app.schemas.trade_plan import AccountMode, ExecutionMode
from app.security.tenant import TenantContext
from app.services.audit_service import AuditService


class ExecutionAccountService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def status(self, tenant: TenantContext) -> PaperAccountStatus:
        account = self._existing(tenant)
        return PaperAccountStatus(
            account=PaperExecutionAccount.model_validate(account) if account else None,
            can_register=tenant.membership_role is MembershipRole.OWNER,
        )

    def register(
        self, tenant: TenantContext, *, request_id: str, trace_id: str
    ) -> PaperAccountRegistration:
        """Caller commits account + audit together, retaining the lock until commit.

        Lock the existing unique tenant membership before inspecting accounts.
        Under PostgreSQL READ COMMITTED, the next setup sees the committed UUID.
        Never filter out disabled accounts or replace an account's history.
        """
        membership = self._session.scalar(
            select(Membership)
            .where(
                Membership.organization_id == tenant.organization_id,
                Membership.user_id == tenant.user_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if (
            tenant.membership_role is not MembershipRole.OWNER
            or membership is None
            or membership.role is not MembershipRole.OWNER
        ):
            raise ForbiddenError(
                "Only the authenticated organization owner can set up a paper account."
            )

        account = self._existing(tenant)
        created = account is None
        if account is None:
            account = ExecutionAccount(
                organization_id=tenant.organization_id,
                user_id=tenant.user_id,
                name="Paper account",
                execution_mode=ExecutionMode.PAPER,
                account_mode=AccountMode.NET,
                enabled=True,
            )
            self._session.add(account)
            self._session.flush()
            AuditService(self._session, strict_mode=True).record(
                AuditRecordCreate(
                    request_id=request_id,
                    trace_id=trace_id,
                    event_type=AuditEventType.EXECUTION_ACCOUNT_REGISTERED,
                    resource_type="execution_account",
                    resource_id=str(account.id),
                    actor_type=ActorType.USER,
                    organization_id=tenant.organization_id,
                    user_id=tenant.user_id,
                    metadata={"execution_mode": "PAPER", "account_mode": "NET"},
                )
            )
        return PaperAccountRegistration(
            account=PaperExecutionAccount.model_validate(account), created=created
        )

    def _existing(self, tenant: TenantContext) -> ExecutionAccount | None:
        accounts = list(
            self._session.scalars(
                select(ExecutionAccount)
                .where(
                    ExecutionAccount.organization_id == tenant.organization_id,
                    ExecutionAccount.user_id == tenant.user_id,
                )
                .limit(2)
                .execution_options(populate_existing=True)
            )
        )
        if len(accounts) > 1:
            raise ConflictError(
                "Multiple paper accounts require operator review; "
                "setup cannot select or replace one.",
                code="execution_account_ambiguous",
            )
        if not accounts:
            return None
        account = accounts[0]
        if not account.enabled:
            raise ConflictError(
                "The existing paper account is disabled; setup cannot re-enable or replace it.",
                code="execution_account_disabled",
            )
        if (
            account.execution_mode is not ExecutionMode.PAPER
            or account.account_mode is not AccountMode.NET
        ):
            raise ConflictError(
                "The existing execution account is not PAPER/NET; operator review is required.",
                code="execution_account_invalid",
            )
        return account

"""Paper identity setup: no client-selected principal, mode or activation."""

from uuid import UUID

from app.schemas.common import ORMModel, StrictModel
from app.schemas.trade_plan import AccountMode, ExecutionMode


class RegisterPaperAccountRequest(StrictModel):
    """An explicit empty setup request; all account properties are server-owned."""


class PaperExecutionAccount(ORMModel):
    id: UUID
    name: str
    execution_mode: ExecutionMode
    account_mode: AccountMode
    enabled: bool


class PaperAccountStatus(StrictModel):
    account: PaperExecutionAccount | None
    can_register: bool


class PaperAccountRegistration(StrictModel):
    account: PaperExecutionAccount
    created: bool

"""Read-only paper context ports. Implementations must not execute or mint."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.telegram_paper_agent.contracts import (
    JournalOutcomeView,
    LearningSummaryView,
    PaperTradeStatusView,
    StrategyDraftView,
)


class PaperContextPort(Protocol):
    def paper_trade_status(
        self, *, organization_id: UUID, user_id: UUID
    ) -> PaperTradeStatusView: ...

    def journal_outcome(
        self, *, organization_id: UUID, user_id: UUID, trade_id: UUID | None
    ) -> JournalOutcomeView | None: ...

    def learning_summary(
        self, *, organization_id: UUID, user_id: UUID, candidate_id: UUID | None
    ) -> LearningSummaryView | None: ...

    def strategy_discussion(
        self, *, organization_id: UUID, user_id: UUID, strategy_id: UUID | None
    ) -> StrategyDraftView | None: ...

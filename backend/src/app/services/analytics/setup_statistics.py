"""Per-setup trading statistics (deterministic aggregates)."""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.schemas.analytics import SetupStatistics
from app.schemas.common import SetupType
from app.services.analytics.helpers import (
    SETUP_TYPES,
    average_decimal,
    date_range_bounds,
    is_loss,
    is_win,
    load_journals,
    load_orders,
    load_positions,
    load_proposals,
    paper_pnl_for_position,
    resolve_setup_type,
    severity_label,
    top_n,
)


class SetupStatisticsService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def compute(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        start_date: date | None = None,
        end_date: date | None = None,
        setup_type_filter: SetupType | None = None,
    ) -> list[SetupStatistics]:
        start_dt, end_dt = date_range_bounds(start_date, end_date)
        types = (setup_type_filter,) if setup_type_filter else SETUP_TYPES

        proposals = load_proposals(
            self._session,
            organization_id=organization_id,
            user_id=user_id,
            start_dt=start_dt,
            end_dt=end_dt,
            setup_type=setup_type_filter,
        )
        orders = load_orders(
            self._session,
            organization_id=organization_id,
            user_id=user_id,
            start_dt=start_dt,
            end_dt=end_dt,
            setup_type=setup_type_filter,
        )
        positions = load_positions(
            self._session,
            organization_id=organization_id,
            user_id=user_id,
            start_dt=start_dt,
            end_dt=end_dt,
            setup_type=setup_type_filter,
        )
        journals = load_journals(
            self._session,
            organization_id=organization_id,
            user_id=user_id,
            start_dt=start_dt,
            end_dt=end_dt,
            setup_type=setup_type_filter,
        )

        stats: list[SetupStatistics] = []
        for setup in types:
            setup_proposals = [
                p for p in proposals if p.strategy_id and p.strategy_id.value == setup.value
            ]
            setup_orders = [
                o
                for o in orders
                if resolve_setup_type(strategy_id=o.strategy_id) == setup
                or (
                    o.proposal_id
                    and any(
                        p.id == o.proposal_id and p.strategy_id.value == setup.value
                        for p in proposals
                    )
                )
            ]
            setup_positions = [
                p
                for p in positions
                if resolve_setup_type(strategy_id=p.strategy_id, risk_state=p.risk_state) == setup
            ]
            setup_journals = [
                j for j in journals if j.strategy_id and j.strategy_id.value == setup.value
            ]

            pnls = [pnl for p in setup_positions if (pnl := paper_pnl_for_position(p)) is not None]
            wins = sum(1 for pnl in pnls if is_win(pnl))
            losses = sum(1 for pnl in pnls if is_loss(pnl))

            mistake_counter: Counter[str] = Counter()
            lesson_counter: Counter[str] = Counter()
            for entry in setup_journals:
                mistake_counter.update(entry.mistakes or [])
                if entry.lessons:
                    lesson_counter[entry.lessons.strip()[:200]] += 1

            risk_levels = [p.risk_level.value for p in setup_proposals]
            confidences = [float(p.confidence) for p in setup_proposals]

            last_used: datetime | None = None
            for row in (*setup_proposals, *setup_orders, *setup_journals):
                created = row.created_at
                if created and (last_used is None or created > last_used):
                    last_used = created

            if (
                not setup_proposals
                and not setup_orders
                and not setup_journals
                and not setup_positions
            ):
                continue

            stats.append(
                SetupStatistics(
                    setup_type=setup,
                    proposal_count=len(setup_proposals),
                    paper_trade_count=len(setup_orders),
                    winning_paper_trades=wins,
                    losing_paper_trades=losses,
                    average_paper_pnl=average_decimal(pnls),
                    average_risk_level=severity_label(risk_levels),
                    average_confidence=(
                        sum(confidences) / len(confidences) if confidences else None
                    ),
                    most_common_mistakes=top_n(mistake_counter),
                    most_common_lessons=top_n(lesson_counter, 3),
                    last_used_at=last_used,
                )
            )
        return stats

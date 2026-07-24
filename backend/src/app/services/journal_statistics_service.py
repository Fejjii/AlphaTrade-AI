"""Journal statistics service (AT-031 — Journal Statistics & Setup Analytics v1).

Deterministic, record-only aggregates over canonical ``journal_trades``
(AT-030). Reads recorded values only — no live market I/O, no execution
authority, no mutation. Every metric family carries its own sample count and
results carry explicit confidence labels and warnings, so partial data and
small samples are always visible (docs truthfulness / conservative behavior).

Classification rules (deterministic, documented):

- Only CLOSED trades enter statistics; outcome metrics are undefined for
  planned/open/cancelled rows.
- Win/loss/breakeven uses the recorded ``result``; a closed trade left at
  ``result=open`` falls back to the sign of its recorded ``net_pnl`` (the same
  arithmetic AT-030 uses when closing), otherwise it stays undecided.
- Rule compliance per trade is the worst recorded assessment:
  ``violated`` > ``partial`` > ``compliant`` (any ``followed``) > ``unassessed``.
- Human-vs-system execution is derived from the trade source by decision
  authority: manual, imported, and human-approved proposal-flow paper
  executions are ``human``; paper-validation, backtest, and system-generated
  trades are ``system``.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from typing import Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ValidationAppError
from app.db.models import SetupDefinition, UserStrategy, UserStrategyVersion
from app.repositories.journal_trades import JournalTradeRepository, JournalTradeStatsRow
from app.schemas.backtest import (
    JournalComparisonCohort,
    JournalComparisonCohortResult,
    JournalComparisonFilters,
    JournalComparisonResponse,
)
from app.schemas.common import JournalTradeSource, RuleComplianceStatus, TradeResult
from app.schemas.journal_statistics import (
    ExecutionActor,
    JournalStatsBucket,
    JournalStatsFilters,
    JournalStatsGroupBy,
    JournalStatsResponse,
    JournalStatsWarning,
    JournalStatsWarningCode,
    JournalTradeStatsMetrics,
    SampleConfidence,
    TradeRuleCompliance,
)

_UNASSIGNED_KEY: Final = "unassigned"
_UNASSIGNED_LABEL: Final = "Unassigned"

# Sample-size thresholds for the coarse confidence label.
_CONFIDENCE_LOW: Final = 5
_CONFIDENCE_MODERATE: Final = 20
_CONFIDENCE_HIGH: Final = 50

# Human-vs-system execution classification by decision authority (see module docstring).
_EXECUTION_ACTOR_BY_SOURCE: Final[dict[JournalTradeSource, ExecutionActor]] = {
    JournalTradeSource.MANUAL: ExecutionActor.HUMAN,
    JournalTradeSource.IMPORTED: ExecutionActor.HUMAN,
    JournalTradeSource.PAPER_EXECUTION: ExecutionActor.HUMAN,
    JournalTradeSource.PAPER_VALIDATION: ExecutionActor.SYSTEM,
    JournalTradeSource.BACKTEST: ExecutionActor.SYSTEM,
    JournalTradeSource.SYSTEM: ExecutionActor.SYSTEM,
}

_COMPARISON_COHORTS: Final[
    tuple[tuple[JournalComparisonCohort, frozenset[JournalTradeSource]], ...]
] = (
    (
        JournalComparisonCohort.HUMAN,
        frozenset(
            {
                JournalTradeSource.MANUAL,
                JournalTradeSource.IMPORTED,
                JournalTradeSource.PAPER_EXECUTION,
            }
        ),
    ),
    (
        JournalComparisonCohort.PAPER_SYSTEM,
        frozenset({JournalTradeSource.PAPER_VALIDATION}),
    ),
    (
        JournalComparisonCohort.BACKTEST,
        frozenset({JournalTradeSource.BACKTEST}),
    ),
)


class JournalStatisticsService:
    """Grouped, filterable statistics over canonical journal trades."""

    def __init__(self, session: Session, *, max_rows: int) -> None:
        self._session = session
        self._trades = JournalTradeRepository(session)
        self._max_rows = max_rows

    def compute(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        group_by: JournalStatsGroupBy,
        filters: JournalStatsFilters,
        limit: int = 50,
        offset: int = 0,
    ) -> JournalStatsResponse:
        if (
            filters.date_from is not None
            and filters.date_to is not None
            and filters.date_from > filters.date_to
        ):
            raise ValidationAppError("date_from must not be after date_to.")

        rows, truncated = self._trades.fetch_stats_rows(
            organization_id=organization_id,
            user_id=user_id,
            source=filters.source,
            entry_method=filters.entry_method,
            symbol=filters.symbol,
            timeframe=filters.timeframe,
            market_regime=filters.market_regime,
            setup_id=filters.setup_id,
            user_strategy_id=filters.user_strategy_id,
            strategy_version_id=filters.strategy_version_id,
            date_from=filters.date_from,
            date_to=filters.date_to,
            max_rows=self._max_rows,
        )
        compliance_by_trade = self._load_compliance(
            organization_id=organization_id, user_id=user_id, filters=filters, rows=rows
        )

        annotated = [
            (
                row,
                compliance_by_trade.get(row.id, TradeRuleCompliance.UNASSESSED),
                _EXECUTION_ACTOR_BY_SOURCE[row.source],
            )
            for row in rows
        ]
        if filters.rule_compliance is not None:
            annotated = [a for a in annotated if a[1] == filters.rule_compliance]
        if filters.execution_actor is not None:
            annotated = [a for a in annotated if a[2] == filters.execution_actor]

        overall = _compute_metrics([a[0] for a in annotated])
        if truncated:
            overall.warnings.append(
                JournalStatsWarning(
                    code=JournalStatsWarningCode.RESULT_TRUNCATED,
                    message=(
                        f"Result capped at {self._max_rows} closed trades; aggregates cover "
                        "only the oldest trades in range. Narrow the date range or filters."
                    ),
                )
            )

        buckets = self._build_buckets(annotated, group_by)
        total_buckets = len(buckets)
        page = buckets[offset : offset + limit]

        return JournalStatsResponse(
            group_by=group_by,
            filters=filters,
            overall=overall,
            buckets=page,
            total_buckets=total_buckets,
            limit=limit,
            offset=offset,
            truncated=truncated,
            max_rows=self._max_rows,
            generated_at=datetime.now(UTC),
        )

    def compare_cohorts(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        filters: JournalComparisonFilters,
    ) -> JournalComparisonResponse:
        """Three-cohort comparison reusing AT-031 metric math (AT-034)."""
        if (
            filters.date_from is not None
            and filters.date_to is not None
            and filters.date_from > filters.date_to
        ):
            raise ValidationAppError("date_from must not be after date_to.")

        cohorts: list[JournalComparisonCohortResult] = []
        for cohort, sources in _COMPARISON_COHORTS:
            metrics, truncated = self._metrics_for_sources(
                organization_id=organization_id,
                user_id=user_id,
                sources=sources,
                filters=filters,
            )
            cohorts.append(
                JournalComparisonCohortResult(
                    cohort=cohort,
                    metrics=metrics,
                    sample_count=metrics.trade_count,
                    truncated=truncated,
                )
            )
        return JournalComparisonResponse(
            filters=filters,
            cohorts=cohorts,
            max_rows=self._max_rows,
            generated_at=datetime.now(UTC),
        )

    def _metrics_for_sources(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        sources: frozenset[JournalTradeSource],
        filters: JournalComparisonFilters,
    ) -> tuple[JournalTradeStatsMetrics, bool]:
        rows, truncated = self._trades.fetch_stats_rows(
            organization_id=organization_id,
            user_id=user_id,
            sources=sources,
            symbol=filters.symbol,
            timeframe=filters.timeframe,
            setup_id=filters.setup_id,
            user_strategy_id=filters.strategy_id,
            strategy_version_id=filters.strategy_version_id,
            date_from=filters.date_from,
            date_to=filters.date_to,
            max_rows=self._max_rows,
        )
        metrics = _compute_metrics(rows)
        if truncated:
            metrics.warnings.append(
                JournalStatsWarning(
                    code=JournalStatsWarningCode.RESULT_TRUNCATED,
                    message=(
                        f"Result capped at {self._max_rows} closed trades; aggregates cover "
                        "only the oldest trades in range. Narrow the date range or filters."
                    ),
                )
            )
        return metrics, truncated

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _load_compliance(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        filters: JournalStatsFilters,
        rows: list[JournalTradeStatsRow],
    ) -> dict[uuid.UUID, TradeRuleCompliance]:
        if not rows:
            return {}
        pairs = self._trades.fetch_rule_check_status_pairs(
            organization_id=organization_id,
            user_id=user_id,
            source=filters.source,
            entry_method=filters.entry_method,
            symbol=filters.symbol,
            timeframe=filters.timeframe,
            market_regime=filters.market_regime,
            setup_id=filters.setup_id,
            user_strategy_id=filters.user_strategy_id,
            strategy_version_id=filters.strategy_version_id,
            date_from=filters.date_from,
            date_to=filters.date_to,
        )
        statuses: dict[uuid.UUID, set[RuleComplianceStatus]] = defaultdict(set)
        for trade_id, status in pairs:
            statuses[trade_id].add(status)
        return {trade_id: _classify_compliance(recorded) for trade_id, recorded in statuses.items()}

    def _build_buckets(
        self,
        annotated: list[tuple[JournalTradeStatsRow, TradeRuleCompliance, ExecutionActor]],
        group_by: JournalStatsGroupBy,
    ) -> list[JournalStatsBucket]:
        labels = self._resolve_labels([a[0] for a in annotated], group_by)
        grouped: dict[tuple[str, uuid.UUID | None, str], list[JournalTradeStatsRow]] = defaultdict(
            list
        )
        for row, compliance, actor in annotated:
            grouped[_group_key(row, group_by, compliance, actor, labels)].append(row)

        buckets = [
            JournalStatsBucket(
                key=key,
                group_id=group_id,
                label=label,
                metrics=_compute_metrics(bucket_rows),
            )
            for (key, group_id, label), bucket_rows in grouped.items()
        ]
        # Deterministic order: largest sample first, then label, then key.
        buckets.sort(key=lambda b: (-b.metrics.trade_count, b.label.lower(), b.key))
        return buckets

    def _resolve_labels(
        self,
        rows: list[JournalTradeStatsRow],
        group_by: JournalStatsGroupBy,
    ) -> dict[uuid.UUID, str]:
        """Batch-resolve display labels for the id-based grouping dimensions."""
        if group_by in (JournalStatsGroupBy.SETUP, JournalStatsGroupBy.SETUP_VERSION):
            setup_ids = {row.setup_id for row in rows if row.setup_id is not None}
            if not setup_ids:
                return {}
            setup_stmt = select(
                SetupDefinition.id, SetupDefinition.name, SetupDefinition.version
            ).where(SetupDefinition.id.in_(setup_ids))
            setup_rows = self._session.execute(setup_stmt).all()
            if group_by is JournalStatsGroupBy.SETUP:
                return {sid: name for sid, name, _version in setup_rows}
            return {sid: f"{name} v{version}" for sid, name, version in setup_rows}
        if group_by is JournalStatsGroupBy.STRATEGY:
            strategy_ids = {row.user_strategy_id for row in rows if row.user_strategy_id}
            if not strategy_ids:
                return {}
            strategy_stmt = select(UserStrategy.id, UserStrategy.name).where(
                UserStrategy.id.in_(strategy_ids)
            )
            return {sid: name for sid, name in self._session.execute(strategy_stmt).all()}  # noqa: C416
        if group_by is JournalStatsGroupBy.STRATEGY_VERSION:
            version_ids = {row.strategy_version_id for row in rows if row.strategy_version_id}
            if not version_ids:
                return {}
            version_stmt = (
                select(UserStrategyVersion.id, UserStrategy.name, UserStrategyVersion.version)
                .join(UserStrategy, UserStrategyVersion.strategy_id == UserStrategy.id)
                .where(UserStrategyVersion.id.in_(version_ids))
            )
            return {
                vid: f"{name} v{version}"
                for vid, name, version in self._session.execute(version_stmt).all()
            }
        return {}


# --------------------------------------------------------------------------- #
# Pure, deterministic computation helpers (unit-testable without a session)
# --------------------------------------------------------------------------- #


def _classify_compliance(recorded: set[RuleComplianceStatus]) -> TradeRuleCompliance:
    """Worst recorded assessment wins; never infer compliance from silence."""
    if RuleComplianceStatus.VIOLATED in recorded:
        return TradeRuleCompliance.VIOLATED
    if RuleComplianceStatus.PARTIAL in recorded:
        return TradeRuleCompliance.PARTIAL
    if RuleComplianceStatus.FOLLOWED in recorded:
        return TradeRuleCompliance.COMPLIANT
    return TradeRuleCompliance.UNASSESSED


def _group_key(
    row: JournalTradeStatsRow,
    group_by: JournalStatsGroupBy,
    compliance: TradeRuleCompliance,
    actor: ExecutionActor,
    labels: dict[uuid.UUID, str],
) -> tuple[str, uuid.UUID | None, str]:
    """(key, group_id, label) for one trade under the requested dimension."""
    match group_by:
        case JournalStatsGroupBy.OVERALL:
            return ("overall", None, "All trades")
        case JournalStatsGroupBy.SETUP:
            if row.setup_id is None or row.setup_id not in labels:
                return (_UNASSIGNED_KEY, None, _UNASSIGNED_LABEL)
            name = labels[row.setup_id]
            return (name, None, name)  # groups all versions sharing the setup name
        case JournalStatsGroupBy.SETUP_VERSION:
            if row.setup_id is None:
                return (_UNASSIGNED_KEY, None, _UNASSIGNED_LABEL)
            return (str(row.setup_id), row.setup_id, labels.get(row.setup_id, str(row.setup_id)))
        case JournalStatsGroupBy.STRATEGY:
            if row.user_strategy_id is None:
                return (_UNASSIGNED_KEY, None, _UNASSIGNED_LABEL)
            return (
                str(row.user_strategy_id),
                row.user_strategy_id,
                labels.get(row.user_strategy_id, str(row.user_strategy_id)),
            )
        case JournalStatsGroupBy.STRATEGY_VERSION:
            if row.strategy_version_id is None:
                return (_UNASSIGNED_KEY, None, _UNASSIGNED_LABEL)
            return (
                str(row.strategy_version_id),
                row.strategy_version_id,
                labels.get(row.strategy_version_id, str(row.strategy_version_id)),
            )
        case JournalStatsGroupBy.SYMBOL:
            return (row.symbol, None, row.symbol)
        case JournalStatsGroupBy.TIMEFRAME:
            return (row.timeframe, None, row.timeframe)
        case JournalStatsGroupBy.MARKET_REGIME:
            return (row.market_regime.value, None, row.market_regime.value)
        case JournalStatsGroupBy.SOURCE:
            return (row.source.value, None, row.source.value)
        case JournalStatsGroupBy.ENTRY_METHOD:
            return (row.entry_method.value, None, row.entry_method.value)
        case JournalStatsGroupBy.RULE_COMPLIANCE:
            return (compliance.value, None, compliance.value)
        case JournalStatsGroupBy.EXECUTION_ACTOR:
            return (actor.value, None, actor.value)


def _decide_result(row: JournalTradeStatsRow) -> TradeResult | None:
    """Recorded result, else deterministic net-PnL sign fallback, else undecided."""
    if row.result != TradeResult.OPEN:
        return row.result
    if row.net_pnl is None:
        return None
    if row.net_pnl > 0:
        return TradeResult.WIN
    if row.net_pnl < 0:
        return TradeResult.LOSS
    return TradeResult.BREAKEVEN


def _confidence(trade_count: int) -> SampleConfidence:
    if trade_count < _CONFIDENCE_LOW:
        return SampleConfidence.INSUFFICIENT
    if trade_count < _CONFIDENCE_MODERATE:
        return SampleConfidence.LOW
    if trade_count < _CONFIDENCE_HIGH:
        return SampleConfidence.MODERATE
    return SampleConfidence.HIGH


def _mean(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    return sum(values, Decimal("0")) / Decimal(len(values))


def _compute_metrics(rows: list[JournalTradeStatsRow]) -> JournalTradeStatsMetrics:
    """Deterministic aggregate metrics for one set of closed journal trades."""
    trade_count = len(rows)
    warnings: list[JournalStatsWarning] = []
    if trade_count == 0:
        warnings.append(
            JournalStatsWarning(
                code=JournalStatsWarningCode.NO_CLOSED_TRADES,
                message="No closed trades match the filters; no statistics computable.",
            )
        )
        return JournalTradeStatsMetrics(confidence=SampleConfidence.INSUFFICIENT, warnings=warnings)

    results = [_decide_result(row) for row in rows]
    wins = sum(1 for r in results if r == TradeResult.WIN)
    losses = sum(1 for r in results if r == TradeResult.LOSS)
    breakeven = sum(1 for r in results if r == TradeResult.BREAKEVEN)
    decided = wins + losses
    win_rate = wins / decided if decided else None

    pnl_rows = [row for row in rows if row.net_pnl is not None]
    net_pnls = [row.net_pnl for row in pnl_rows if row.net_pnl is not None]
    winners = [pnl for pnl in net_pnls if pnl > 0]
    losers = [pnl for pnl in net_pnls if pnl < 0]
    gross_win = sum(winners, Decimal("0"))
    gross_loss = sum(losers, Decimal("0"))
    gross_pnls = [row.gross_pnl for row in rows if row.gross_pnl is not None]

    r_values = [
        row.net_pnl / row.planned_risk_amount
        for row in pnl_rows
        if row.net_pnl is not None
        and row.planned_risk_amount is not None
        and row.planned_risk_amount > 0
    ]

    fees = [row.fees for row in rows if row.fees is not None]
    fundings = [row.funding for row in rows if row.funding is not None]
    slippages = [row.slippage for row in rows if row.slippage is not None]
    cost_sample_count = sum(
        1
        for row in rows
        if row.fees is not None or row.funding is not None or row.slippage is not None
    )
    cost_parts = [
        total
        for total in (
            sum(fees, Decimal("0")) if fees else None,
            sum(fundings, Decimal("0")) if fundings else None,
            sum(slippages, Decimal("0")) if slippages else None,
        )
        if total is not None
    ]

    mfe_values = [row.mfe_amount for row in rows if row.mfe_amount is not None]
    mae_values = [row.mae_amount for row in rows if row.mae_amount is not None]

    capture_rows = [
        row for row in rows if row.net_pnl is not None and row.available_profit is not None
    ]
    capture_pcts: list[float] = []
    for row in capture_rows:
        if row.realized_vs_available_pct is not None:
            capture_pcts.append(row.realized_vs_available_pct)
        elif row.available_profit and row.net_pnl is not None:
            capture_pcts.append(float(row.net_pnl / row.available_profit * Decimal("100")))

    confidence = _confidence(trade_count)
    if confidence in (SampleConfidence.INSUFFICIENT, SampleConfidence.LOW):
        warnings.append(
            JournalStatsWarning(
                code=JournalStatsWarningCode.LOW_SAMPLE,
                message=(
                    f"Only {trade_count} closed trade(s); treat these statistics as anecdotal, "
                    "not as evidence of an edge."
                ),
            )
        )
    if decided == 0:
        warnings.append(
            JournalStatsWarning(
                code=JournalStatsWarningCode.NO_DECIDED_TRADES,
                message="No trades with a decided win/loss result; win rate is undefined.",
            )
        )
    if len(pnl_rows) < trade_count:
        warnings.append(
            JournalStatsWarning(
                code=JournalStatsWarningCode.MISSING_PNL,
                message=(
                    f"{trade_count - len(pnl_rows)} of {trade_count} closed trades have no "
                    "recorded net PnL and are excluded from PnL aggregates."
                ),
            )
        )
    if pnl_rows and len(r_values) < len(pnl_rows):
        warnings.append(
            JournalStatsWarning(
                code=JournalStatsWarningCode.MISSING_RISK,
                message=(
                    f"Average R uses {len(r_values)} of {len(pnl_rows)} trades with PnL; the "
                    "rest have no positive planned risk amount recorded."
                ),
            )
        )
    if winners and not losers:
        warnings.append(
            JournalStatsWarning(
                code=JournalStatsWarningCode.NO_LOSING_TRADES,
                message="No losing trades in sample; profit factor is undefined.",
            )
        )
    if (0 < len(mfe_values) < trade_count) or (0 < len(mae_values) < trade_count):
        warnings.append(
            JournalStatsWarning(
                code=JournalStatsWarningCode.PARTIAL_EXCURSION_DATA,
                message=(
                    f"MFE recorded on {len(mfe_values)} and MAE on {len(mae_values)} of "
                    f"{trade_count} trades; excursion aggregates cover only those trades."
                ),
            )
        )
    if 0 < len(capture_rows) < trade_count:
        warnings.append(
            JournalStatsWarning(
                code=JournalStatsWarningCode.PARTIAL_CAPTURE_DATA,
                message=(
                    f"Available-vs-realized profit recorded on {len(capture_rows)} of "
                    f"{trade_count} trades; capture aggregates cover only those trades."
                ),
            )
        )

    return JournalTradeStatsMetrics(
        trade_count=trade_count,
        wins=wins,
        losses=losses,
        breakeven=breakeven,
        win_rate=win_rate,
        pnl_sample_count=len(pnl_rows),
        net_pnl_total=sum(net_pnls, Decimal("0")) if net_pnls else None,
        gross_pnl_total=sum(gross_pnls, Decimal("0")) if gross_pnls else None,
        expectancy=_mean(net_pnls),
        average_winner=_mean(winners),
        average_loser=_mean(losers),
        profit_factor=(float(gross_win / -gross_loss) if losers and gross_loss != 0 else None),
        r_sample_count=len(r_values),
        average_r=(float(_mean(r_values) or 0) if r_values else None),
        cost_sample_count=cost_sample_count,
        fees_total=sum(fees, Decimal("0")) if fees else None,
        funding_total=sum(fundings, Decimal("0")) if fundings else None,
        slippage_total=sum(slippages, Decimal("0")) if slippages else None,
        total_costs=sum(cost_parts, Decimal("0")) if cost_parts else None,
        mfe_sample_count=len(mfe_values),
        average_mfe_amount=_mean(mfe_values),
        mae_sample_count=len(mae_values),
        average_mae_amount=_mean(mae_values),
        capture_sample_count=len(capture_rows),
        available_profit_total=(
            sum(
                (row.available_profit for row in capture_rows if row.available_profit),
                Decimal("0"),
            )
            if capture_rows
            else None
        ),
        realized_on_available_total=(
            sum((row.net_pnl for row in capture_rows if row.net_pnl is not None), Decimal("0"))
            if capture_rows
            else None
        ),
        average_realized_vs_available_pct=(
            sum(capture_pcts) / len(capture_pcts) if capture_pcts else None
        ),
        confidence=confidence,
        warnings=warnings,
    )

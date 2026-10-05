"""Read-only Brain Agent adapter to the canonical Strategy Analytics service.

Selection and presentation only. Metric arithmetic, attribution and evidence
thresholds belong to StrategyAnalyticsService, shared with the HTTP report API.
"""

from __future__ import annotations

import json
import re
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import UserStrategy, UserStrategyVersion
from app.interactive_agent.parsing import extract_timeframe
from app.schemas.common import StrategyId
from app.schemas.strategy_analytics import (
    NestedMaturityStage,
    StrategyAnalyticsDimension,
    StrategyAnalyticsFilters,
    StrategyAnalyticsMetrics,
    StrategyAnalyticsReport,
)
from app.services.strategy_analytics_service import StrategyAnalyticsService

logger = structlog.get_logger(__name__)
_PERFORMANCE = re.compile(
    r"\b(?:perform(?:ed|ance)?|expectancy|average r|median r|profit factor|"
    r"samples?|mae|mfe|insufficient (?:evidence|history))\b",
    re.IGNORECASE,
)
_STAGE = re.compile(r"\b(N[1-3]|N4_PLUS|N4\s*(?:plus|\+))(?=\W|$)", re.IGNORECASE)
_VERSION = re.compile(r"\b(?:version\s*|v)(\d+)\b", re.IGNORECASE)
_STRATEGY_UUID = re.compile(r"\bstrategy(?:_id)?\s+([a-f0-9-]{36})\b", re.IGNORECASE)
_VERSION_UUID = re.compile(r"\b(?:strategy_version_id|version)\s+([a-f0-9-]{36})\b", re.IGNORECASE)
_GROUP_BY = (
    StrategyAnalyticsDimension.STRATEGY,
    StrategyAnalyticsDimension.STRATEGY_VERSION,
    StrategyAnalyticsDimension.NESTED_MATURITY_STAGE,
)
_METRICS = (
    ("expectancy", "expectancy (recorded net PnL/trade)"),
    ("average_r", "average R"),
    ("median_r", "median R"),
    ("profit_factor", "profit factor"),
    ("average_mae_amount", "MAE (recorded amount)"),
    ("average_mfe_amount", "MFE (recorded amount)"),
)


class _ClarificationError(ValueError):
    pass


def is_strategy_definition_comparison(message: str) -> bool:
    """Comparing strategy rules/families does not request historical metrics."""
    if (
        _PERFORMANCE.search(message)
        or _STAGE.search(message)
        or _VERSION.search(message)
        or re.search(r"\bwin rate\b", message, re.IGNORECASE)
    ):
        return False
    return bool(
        re.search(r"\b(?:compare|versus|vs|difference|differences)\b", message, re.IGNORECASE)
        and re.search(r"\b(?:nested|sfp|strateg(?:y|ies))\b", message, re.IGNORECASE)
    )


def is_strategy_analytics_question(message: str) -> bool:
    """Historical questions take precedence over setup-state and library reads."""
    if is_strategy_definition_comparison(message):
        return False
    historical_target = _STAGE.search(message) or re.search(
        r"\b(?:nested|strateg(?:y|ies))\b", message, re.IGNORECASE
    )
    return bool(_PERFORMANCE.search(message)) or bool(
        historical_target
        and re.search(r"\b(?:win rate|compare|versus|vs)\b", message, re.IGNORECASE)
    )


def _merge(values: dict[str, Any], field: str, value: object) -> None:
    if value is None:
        return
    if values.get(field) is not None and values[field] != value:
        raise _ClarificationError(
            f"Conflicting {field} filters. Supply one explicit analytics filter."
        )
    values[field] = value


def _select_filters(
    session: Session,
    *,
    organization_id: UUID,
    user_id: UUID,
    message: str,
    strategy_id: UUID | None,
    symbol: str | None,
    timeframe: str | None,
    filters: StrategyAnalyticsFilters | None,
) -> list[StrategyAnalyticsFilters]:
    values = (filters or StrategyAnalyticsFilters()).model_dump()
    _merge(values, "strategy_id", strategy_id)
    for pattern, field in ((_STRATEGY_UUID, "strategy_id"), (_VERSION_UUID, "strategy_version_id")):
        matches = pattern.findall(message)
        if len(set(matches)) > 1:
            raise _ClarificationError(f"Select one {field} before comparing maturity stages.")
        if matches:
            _merge(values, field, UUID(matches[0]))
    symbols = set(re.findall(r"\b[A-Z][A-Z0-9]{1,20}(?:USDT|USD)\b", message.upper()))
    aliases = set(re.findall(r"\b(BTC|ETH|SOL)\b", message.upper()))
    symbols.update(f"{alias}USDT" for alias in aliases)
    if len(symbols) > 1:
        raise _ClarificationError("Select one symbol per analytics request.")
    _merge(values, "symbol", next(iter(symbols), None))
    if values["symbol"] is None:
        _merge(values, "symbol", symbol)
    frames = set(re.findall(r"\b(?:1m|3m|5m|15m|30m|1h|2h|4h|6h|12h|1d|1w)\b", message.lower()))
    if len(frames) > 1:
        raise _ClarificationError("Select one timeframe per analytics request.")
    _merge(values, "timeframe", extract_timeframe(message))
    if values["timeframe"] is None:
        _merge(values, "timeframe", timeframe)

    scope = (UserStrategy.organization_id == organization_id, UserStrategy.user_id == user_id)
    selected = values["strategy_id"]
    # Resolve exact names only, never use fuzzy knowledge hits or the first library row.
    name = re.search(r"\bhow did\s+(.+?)\s+(?:perform|do)\b", message, re.IGNORECASE)
    target = name.group(1).strip(" \"'") if name else None
    nested = bool(re.search(r"\bnested\b", message, re.IGNORECASE) or _STAGE.search(message))
    query = select(UserStrategy.id).where(*scope)
    if (
        target
        and target.lower()
        not in {"nested", "nested continuation", "n1", "n2", "n3", "n4 plus", "n4_plus"}
        and not re.search(r"\b(?:setups?|this strategy|my strategy)\b", target, re.IGNORECASE)
    ):
        candidates = list(
            session.scalars(query.where(func.lower(UserStrategy.name) == target.lower()).limit(2))
        )
        if len(candidates) != 1:
            raise _ClarificationError(
                "Strategy name is unavailable or ambiguous. Supply your strategy_id."
            )
        _merge(values, "strategy_id", candidates[0])
        selected = candidates[0]
    if selected is None and values["strategy_version_id"] is None and nested:
        candidates = list(
            session.scalars(
                query.where(UserStrategy.setup_type == StrategyId.NESTED_CONTINUATION).limit(2)
            )
        )
        if len(candidates) != 1:
            raise _ClarificationError(
                "Select a Nested strategy_id from your library; no unique strategy was resolved."
            )
        selected = candidates[0]
    if selected is not None:
        row = session.scalar(select(UserStrategy).where(*scope, UserStrategy.id == selected))
        if row is None:
            raise _ClarificationError("Selected strategy is unavailable in your scope.")
        if nested and row.setup_type != StrategyId.NESTED_CONTINUATION:
            raise _ClarificationError("Nested maturity questions require a Nested strategy_id.")
        values["strategy_id"] = selected

    version_ids = values["strategy_version_id"]
    version_text = _VERSION_UUID.sub("", message)
    if len(set(_VERSION.findall(version_text))) > 1:
        raise _ClarificationError("Select one strategy version per stage comparison.")
    number = _VERSION.search(version_text)
    if number is not None or version_ids is not None:
        version_query = select(UserStrategyVersion).join(UserStrategy).where(*scope)
        if selected is not None:
            version_query = version_query.where(UserStrategyVersion.strategy_id == selected)
        if version_ids is not None:
            version_query = version_query.where(UserStrategyVersion.id == version_ids)
        if number is not None:
            if selected is None and version_ids is None:
                raise _ClarificationError(
                    "A version number requires your strategy_id or strategy_version_id."
                )
            version_query = version_query.where(UserStrategyVersion.version == int(number.group(1)))
        version = session.scalar(version_query)
        if version is None:
            raise _ClarificationError("Selected strategy version is unavailable in your scope.")
        if nested:
            nested_type = session.scalar(
                select(UserStrategy.setup_type).where(
                    *scope, UserStrategy.id == version.strategy_id
                )
            )
            if nested_type != StrategyId.NESTED_CONTINUATION:
                raise _ClarificationError(
                    "Nested maturity questions require a Nested strategy version."
                )
        values["strategy_id"] = version.strategy_id
        values["strategy_version_id"] = version.id
    elif re.search(
        r"\b(?:this|current|latest)\s+(?:strategy\s+)?version\b", message, re.IGNORECASE
    ):
        raise _ClarificationError(
            "Supply the exact strategy_version_id or a strategy_id with a version number."
        )
    elif selected is None and re.search(r"\b(?:this|my) strategy\b", message, re.IGNORECASE):
        raise _ClarificationError("Supply your strategy_id or open a strategy-bound conversation.")

    # Unsupported prose constraints must not silently widen a historical report.
    if (
        re.search(
            r"\b(?:today|yesterday|last|since|between|before|after|during|from|to)\b|\d{4}-\d{2}-\d{2}",
            message,
            re.IGNORECASE,
        )
        and values["date_from"] is None
        and values["date_to"] is None
    ):
        raise _ClarificationError(
            "Supply timezone-aware date_from/date_to in analytics_filters for a date range."
        )
    if (
        re.search(r"\b(?:paper|manual|imported|backtest|source)\b", message, re.IGNORECASE)
        and values["source"] is None
    ):
        raise _ClarificationError("Supply the canonical source in analytics_filters.")
    if (
        re.search(r"\b(?:regime|ranging|trending|volatile)\b", message, re.IGNORECASE)
        and values["market_regime"] is None
    ):
        raise _ClarificationError("Supply market_regime in analytics_filters.")

    stages = list(
        dict.fromkeys(
            token.upper().replace(" ", "").replace("N4PLUS", "N4_PLUS").replace("N4+", "N4_PLUS")
            for token in _STAGE.findall(message)
        )
    )
    if re.search(r"\b(?:compare|versus|vs)\b", message, re.IGNORECASE) and len(stages) != 2:
        raise _ClarificationError(
            "Analytics comparisons currently require exactly two maturity stages."
        )
    if len(stages) > 1:
        if len(stages) != 2 or not re.search(r"\b(?:compare|versus|vs)\b", message, re.IGNORECASE):
            raise _ClarificationError("Compare exactly two maturity stages, or select one stage.")
        if values["nested_maturity_stage"] is not None:
            raise _ClarificationError(
                "A stage comparison cannot also have a single-stage analytics filter."
            )
        return [
            StrategyAnalyticsFilters(**{**values, "nested_maturity_stage": stage})
            for stage in stages
        ]
    if stages:
        _merge(values, "nested_maturity_stage", NestedMaturityStage(stages[0]))
    return [StrategyAnalyticsFilters(**values)]


def _metrics_text(metrics: StrategyAnalyticsMetrics) -> str:
    lines = [
        f"Closed samples: {metrics.trade_count}; confidence: {metrics.confidence.value}; "
        f"insufficient history: {metrics.insufficient_history}."
    ]
    for field, label in _METRICS:
        sample = metrics.metric_samples[field]
        value = getattr(metrics, field)
        rendered = "unavailable" if value is None or not sample.available else str(value)
        evidence = (
            "insufficient evidence" if sample.insufficient_history else "descriptive sample only"
        )
        lines.append(f"{label}: {rendered} (n={sample.sample_count}; {evidence}).")
    lines.append("Missing fields: " + json.dumps(metrics.missing_fields, sort_keys=True) + ".")
    lines.append(
        "Warnings: "
        + ", ".join(
            [warning.code for warning in metrics.warnings]
            + [warning.code for warning in metrics.analytics_warnings]
        )
        + "."
    )
    return "\n".join(lines)


def _render(reports: list[StrategyAnalyticsReport]) -> str:
    lines = [
        "Source: StrategyAnalyticsService.compute; GET /strategy-analytics/report; "
        "strategy-analytics/v1.",
        "Closed canonical journal outcomes; maturity from first recorded paper_trade_opened event.",
        "Descriptive recorded history only. Insufficient history cannot "
        "establish profitability or an edge.",
        "Unavailable metrics stay unavailable. MAE/MFE are recorded monetary amounts.",
        "Full version/stage metrics, metric samples, warnings and limitations "
        "are in strategy_analytics.",
    ]
    lines.extend(reports[0].limitations)
    for report in reports:
        lines.append("Filters: " + report.filters.model_dump_json(exclude_none=True) + ".")
        lines.append("Overall aggregates pool all matching versions and stages:")
        lines.append(_metrics_text(report.overall))
        lines.append(
            f"Scan: {report.scanned_trade_count}/{report.max_rows}; truncated: "
            f"{report.truncated}; minimum samples: {report.min_sample_size}."
        )
        for bucket in report.buckets[:3]:
            dimensions = ", ".join(
                f"{key.value}={value or 'unassigned'}" for key, value in bucket.dimensions.items()
            )
            insufficient_metrics = (
                ", ".join(
                    name
                    for name, sample in bucket.metrics.metric_samples.items()
                    if sample.insufficient_history or not sample.available
                )
                or "none (descriptive sample only)"
            )
            lines.append(
                f"{dimensions}: n={bucket.metrics.trade_count}, "
                f"confidence={bucket.metrics.confidence.value}, "
                f"insufficient history={bucket.metrics.insufficient_history}. "
                f"Metrics with insufficient/unavailable evidence: {insufficient_metrics}."
            )
        if report.total_buckets > min(3, len(report.buckets)):
            lines.append(
                f"Version/stage summary abbreviated; {report.total_buckets} buckets "
                f"total, {len(report.buckets)} returned in strategy_analytics "
                f"(limit={report.limit}, offset={report.offset})."
            )
    text = "\n".join(lines)
    if len(text) > 4000:
        return (
            text[:3850]
            + "\nReply abbreviated. Full filters, version identities, coverage, warnings "
            "and limitations are retained in strategy_analytics."
        )
    return text


def read_strategy_analytics(
    session: Session,
    *,
    organization_id: UUID,
    user_id: UUID,
    message: str,
    strategy_id: UUID | None = None,
    symbol: str | None = None,
    timeframe: str | None = None,
    filters: StrategyAnalyticsFilters | None = None,
    max_rows: int = 10_000,
) -> tuple[list[StrategyAnalyticsReport], str, list[str]]:
    """No commit, flush, snapshots, positions, execution or strategy mutation."""
    try:
        with session.no_autoflush:
            selected = _select_filters(
                session,
                organization_id=organization_id,
                user_id=user_id,
                message=message,
                strategy_id=strategy_id,
                symbol=symbol,
                timeframe=timeframe,
                filters=filters,
            )
            service = StrategyAnalyticsService(session, max_rows=max_rows)
            reports = [
                service.compute(
                    organization_id=organization_id,
                    user_id=user_id,
                    filters=item,
                    group_by=_GROUP_BY,
                )
                for item in selected
            ]
    except _ClarificationError as exc:
        return (
            [],
            f"Strategy analytics needs clarification: {exc} No performance inferred.",
            [str(exc)],
        )
    except Exception:
        logger.warning("interactive_agent_strategy_analytics_unavailable")
        limitation = (
            "Canonical Strategy Analytics is unavailable. No performance values were estimated."
        )
        return [], limitation, [limitation]
    limitations = list(dict.fromkeys(note for report in reports for note in report.limitations))
    return reports, _render(reports), limitations

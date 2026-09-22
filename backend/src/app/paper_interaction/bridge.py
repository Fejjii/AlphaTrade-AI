"""Connect paper Watcher scans to measurement discussion without a second authority.

Watcher scan report → optional durable Telegram notification → bound discussion.
Paper-evaluation summary → Telegram learning text.

Deterministic fact lines exclude AI narrative. Refinement lines stay
``activate=false``. This module does not mint Candidates, write market truth,
approve strategies, place orders, or enable Watcher, Telegram, or live trading.
The paper worker leaves the scan hook unset unless a caller supplies one.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from app.paper_evaluation.contracts import (
    REFINEMENT_NOT_ACTIVATED,
    PaperEvaluationSummary,
)
from app.paper_evaluation.query import PaperEvaluationQueryService
from app.signal_fusion.assessment import SetupAssessment
from app.signal_fusion.candidate import Candidate
from app.signal_fusion.evidence_window import CanonicalEvidenceWindowV1
from app.telegram_paper_agent.contracts import (
    JournalOutcomeView,
    LearningSummaryView,
    PaperAlertRecipient,
    PaperNotificationProjection,
    PaperTradeStatusView,
    StrategyDraftView,
    WatcherScanNotice,
)
from app.telegram_paper_agent.gateway import TelegramPaperAgent
from app.telegram_paper_agent.ports import PaperContextPort
from app.workers.watcher_paper import WatcherPaperScanReport

_HEX = frozenset("0123456789abcdef")


@dataclass(frozen=True, slots=True)
class ConfirmedScanEvidence:
    """Canonical objects already produced by the Watcher. Not a new assessment."""

    candidate: Candidate
    assessment: SetupAssessment
    window: CanonicalEvidenceWindowV1


def notice_from_scan_report(report: WatcherPaperScanReport) -> WatcherScanNotice | None:
    """Copy scan facts into a notification notice. Returns none without a user id."""

    if report.user_id is None:
        return None
    return WatcherScanNotice(
        organization_id=report.organization_id,
        user_id=report.user_id,
        scan_scope=report.scan_scope,
        symbol=report.symbol,
        status=report.status,
        reason_code=report.reason_code,
        published=report.published,
        candidate_ids=report.candidate_ids,
        request_hash=_sha256_or_none(report.request_hash),
        lineage_id=report.lineage_id,
    )


def confirmed_evidence_from_report(report: WatcherPaperScanReport) -> ConfirmedScanEvidence | None:
    """Use the persisted discussion snapshot when the scan published a Candidate."""

    discussion = report.discussion
    if discussion is None or not report.published:
        return None
    return ConfirmedScanEvidence(
        candidate=discussion.candidate,
        assessment=discussion.assessment,
        window=discussion.window,
    )


def project_scan_report(
    agent: TelegramPaperAgent,
    report: WatcherPaperScanReport,
    *,
    recipient: PaperAlertRecipient,
    evidence: ConfirmedScanEvidence | None = None,
) -> PaperNotificationProjection | None:
    """Project one scan into the durable Telegram outbox. Empty scans are not alerts."""

    notice = notice_from_scan_report(report)
    if notice is None:
        return None
    resolved = evidence if evidence is not None else confirmed_evidence_from_report(report)
    return agent.project_watcher_notice(
        notice=notice,
        recipient=recipient,
        candidate=None if resolved is None else resolved.candidate,
        assessment=None if resolved is None else resolved.assessment,
        window=None if resolved is None else resolved.window,
    )


def telegram_scan_hook(
    agent: TelegramPaperAgent,
    recipient: PaperAlertRecipient,
) -> Callable[[WatcherPaperScanReport], None]:
    """Worker hook. Exceptions propagate to the worker, which logs and continues."""

    def hook(report: WatcherPaperScanReport) -> None:
        project_scan_report(agent, report, recipient=recipient)

    return hook


def evaluation_fact_lines(summary: PaperEvaluationSummary) -> tuple[str, ...] | None:
    """Deterministic lines only. Narrative text is never copied."""

    facts = summary.facts
    has_measurement = (
        facts.watcher.scan_count > 0
        or facts.conversion.candidates > 0
        or facts.conversion.closed > 0
        or bool(summary.refinements)
    )
    if not has_measurement:
        return None
    lines = [
        f"facts_hash:{facts.content_hash}",
        f"scans:{facts.watcher.scan_count}",
        f"candidates:{facts.conversion.candidates}",
        f"closed:{facts.conversion.closed}",
        f"stop_violations:{facts.rule_adherence.stop_violation_count}",
        f"journal_violations:{facts.rule_adherence.journal_violated_count}",
        "counterfactual_pnl:none",
        f"live_executable:{str(facts.live_executable).lower()}",
        f"watcher_orchestration_enabled:{str(facts.watcher_orchestration_enabled).lower()}",
        f"telegram_interaction_enabled:{str(facts.telegram_interaction_enabled).lower()}",
    ]
    if facts.strategy_overall.average_mfe is not None:
        lines.append(f"average_mfe:{facts.strategy_overall.average_mfe}")
    if facts.strategy_overall.average_mae is not None:
        lines.append(f"average_mae:{facts.strategy_overall.average_mae}")
    if facts.strategy_overall.net_pnl_total is not None:
        lines.append(f"net_pnl_total:{facts.strategy_overall.net_pnl_total}")
    for suggestion in summary.refinements:
        lines.append(
            "refinement:"
            f"{suggestion.category}:activate={str(suggestion.activate).lower()}:"
            f"auto_activate={str(suggestion.auto_activate).lower()}"
        )
    return tuple(lines)


class EvaluationLearningContext:
    """Read-only Telegram context. Learning text comes from paper-evaluation facts."""

    def __init__(self, inner: PaperContextPort, query: PaperEvaluationQueryService) -> None:
        self._inner = inner
        self._query = query

    def paper_trade_status(self, *, organization_id: UUID, user_id: UUID) -> PaperTradeStatusView:
        return self._inner.paper_trade_status(organization_id=organization_id, user_id=user_id)

    def journal_outcome(
        self, *, organization_id: UUID, user_id: UUID, trade_id: UUID | None
    ) -> JournalOutcomeView | None:
        return self._inner.journal_outcome(
            organization_id=organization_id, user_id=user_id, trade_id=trade_id
        )

    def strategy_discussion(
        self, *, organization_id: UUID, user_id: UUID, strategy_id: UUID | None
    ) -> StrategyDraftView | None:
        return self._inner.strategy_discussion(
            organization_id=organization_id, user_id=user_id, strategy_id=strategy_id
        )

    def learning_summary(
        self, *, organization_id: UUID, user_id: UUID, candidate_id: UUID | None
    ) -> LearningSummaryView | None:
        del user_id
        summary = self._query.summary(organization_id=organization_id, narrative=None)
        lines = evaluation_fact_lines(summary)
        if lines is None:
            return None
        return LearningSummaryView(
            organization_id=organization_id,
            candidate_id=candidate_id,
            banner=REFINEMENT_NOT_ACTIVATED,
            fact_lines=lines,
        )


def _sha256_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    lowered = value.lower()
    if len(lowered) != 64 or any(char not in _HEX for char in lowered):
        return None
    return lowered

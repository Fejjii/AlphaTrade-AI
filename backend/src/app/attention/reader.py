"""SELECT-only tenant adapter. Never starts providers, jobs, delivery or execution."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, TypeAdapter
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.attention.contracts import AttentionCategory as Category
from app.attention.contracts import AttentionQueue, AttentionSignal
from app.attention.service import build_queue
from app.daily_review.contracts import ReviewSource, ReviewTopic
from app.daily_review.reader import DailyReviewService
from app.daily_review.service import daily_window
from app.db.models import (
    BacktestRun,
    DailyRiskState,
    JournalTrade,
    JournalTradeObservation,
    KillSwitchState,
    LessonCandidate,
    PaperValidationAlert,
    PaperValidationRun,
    RiskEvent,
    StrategyConversationProposal,
    TradeJournal,
    UserRiskSettings,
)
from app.db.paper_evaluation import PaperEvaluationObservationRow
from app.db.strategy_brain import BrainSetupRow
from app.db.telegram_security import TelegramOutboxRow
from app.db.watcher_orchestration import WatcherHealthSnapshotRow
from app.db.watcher_watchlist import WatcherSymbolStatusRow, WatcherWatchlistRow
from app.market_contracts.identity import interval_timedelta
from app.schemas.common import (
    AlertDeliveryChannel,
    AlertDeliveryStatus,
    JournalTradeSource,
    JournalTradeStatus,
    RiskAction,
    StrategyProposalStatus,
    Timeframe,
)
from app.services.canonical_serialization import canonical_sha256
from app.telegram_security.contracts import OutboxState

MARKET_TTL = timedelta(minutes=15)
RISK_TTL = timedelta(days=1)
RESEARCH_TTL = timedelta(days=7)


def utc(value: datetime) -> datetime:
    # Persisted timestamps are UTC; SQLite drops PostgreSQL timezone metadata.
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def lesson_key(text: str) -> str:
    return canonical_sha256({"lesson": " ".join(text.split())})


class AttentionQueueService:
    """Organization market facts; user-private risk, research, journal and delivery.

    Caller authorizes membership and owns the read transaction. No autoflush,
    commit, acknowledgement writes, risk evaluations or implicit provider reads.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def queue(self, *, organization_id: UUID, user_id: UUID, now: datetime) -> AttentionQueue:
        now = TypeAdapter(AwareDatetime).validate_python(now).astimezone(UTC)
        with self.session.no_autoflush:
            signals = self._read(organization_id, user_id, now)
        return build_queue(
            tuple(signals),
            organization_id=organization_id,
            user_id=user_id,
            now=now,
            limitations=(
                "Market notices expire after 15 minutes unless a setup records its own expiry; "
                "risk events cover 24 hours and completed research covers seven days.",
                "Paper positions use canonical open paper JournalTrade records only.",
                "Daily Review lessons cover the current UTC day; pending lesson candidates "
                "remain visible until their stored status changes.",
                "Acknowledgement is projected only from existing alert read_at storage; "
                "this queue cannot write acknowledgements.",
                "Global runtime/provider rows without tenant ownership are excluded.",
            ),
        )

    def _read(self, org: UUID, user: UUID, now: datetime) -> list[AttentionSignal]:
        signals: list[AttentionSignal] = []

        def rows(model: Any, *conditions: Any, private: bool = True) -> list[Any]:
            query = select(model).where(model.organization_id == org, *conditions)
            if private:
                query = query.where(model.user_id == user)
            return list(self.session.scalars(query).all())

        def add(
            row: Any,
            at: datetime,
            category: Category,
            key: str,
            title: str,
            reason: str,
            action: str,
            *,
            record_id: str | None = None,
            shared: bool = False,
            expires: datetime | None = None,
            severity: str = "medium",
            symbol: str | None = None,
            strategy: str | None = None,
            version: UUID | None = None,
            acknowledgement: str = "unsupported",
        ) -> None:
            signals.append(
                AttentionSignal.model_validate(
                    {
                        "organization_id": org,
                        "user_id": None if shared else user,
                        "semantic_key": key,
                        "category": category,
                        "severity": severity,
                        "title": title,
                        "reason": reason,
                        "symbol": symbol,
                        "strategy_id": strategy,
                        "strategy_version_id": version,
                        "recommended_next_action": action,
                        "expires_at": utc(expires) if expires else None,
                        "acknowledgement_state": acknowledgement,
                        "sources": (
                            ReviewSource(
                                record_type=row.__tablename__,
                                record_id=record_id or str(row.id),
                                occurred_at=utc(at),
                            ),
                        ),
                    }
                )
            )

        setups = rows(
            BrainSetupRow,
            BrainSetupRow.expires_at > now,
            BrainSetupRow.observed_at <= now,
            private=False,
        )
        linked = {str(r.assessment_id) for r in setups if r.assessment_id}
        for row in setups:
            if row.state not in {
                "WATCH",
                "FORMING",
                "CONFIRMED",
                "TRADE_CANDIDATE",
                "BLOCKED_BY_RISK",
            }:
                continue
            payload = row.payload
            category = {
                "BLOCKED_BY_RISK": Category.RISK_BLOCK,
                "CONFIRMED": Category.CONFIRMED,
                "TRADE_CANDIDATE": Category.CONFIRMED,
            }.get(row.state, Category.FORMING)
            add(
                row,
                row.observed_at,
                category,
                str(row.id),
                "Risk-blocked setup"
                if category == Category.RISK_BLOCK
                else "Confirmed setup to review"
                if category == Category.CONFIRMED
                else "Forming setup",
                f"Recorded setup state: {row.state}.",
                "Review the recorded risk block; keep the block in force."
                if category == Category.RISK_BLOCK
                else "Review setup evidence and validity before any separate paper approval.",
                shared=True,
                expires=row.expires_at,
                symbol=row.symbol,
                strategy=str(row.strategy_id),
                version=row.strategy_version_id,
                severity="high" if category == Category.RISK_BLOCK else "medium",
            )
            availability = payload.get("required_evidence")
            evidence = payload.get("evidence", {})
            missing = sorted(
                k
                for k, v in evidence.items()
                if k in {"closed_ohlcv", "volume"} and v in {"MISSING", "INCOMPLETE"}
            )
            if availability in {"MISSING", "INCOMPLETE"} or missing:
                add(
                    row,
                    row.observed_at,
                    Category.MISSING_EVIDENCE,
                    str(row.id),
                    "Required setup evidence missing",
                    f"Recorded evidence: {availability or ', '.join(missing)}.",
                    "Review missing evidence; obtain a complete evaluation before proceeding.",
                    shared=True,
                    expires=row.expires_at,
                    severity="high",
                    symbol=row.symbol,
                    strategy=str(row.strategy_id),
                    version=row.strategy_version_id,
                )
            # Same closed-bar freshness boundary used by the existing Brain setup projection.
            fresh_until = None
            if payload.get("timeframe"):
                delta = interval_timedelta(Timeframe(payload["timeframe"]))
                fresh_until = utc(row.observed_at) + delta
                if payload.get("family") == "sfp" and payload.get("evidence_close_at"):
                    fresh_until = utc(datetime.fromisoformat(payload["evidence_close_at"])) + (
                        delta * payload["required_evidence_max_age_bars"]
                    )
            if (
                availability == "STALE"
                or any(evidence.get(k) == "STALE" for k in ("closed_ohlcv", "volume"))
                or (fresh_until is not None and now >= fresh_until)
            ):
                add(
                    row,
                    row.observed_at,
                    Category.STALE_EVIDENCE,
                    str(row.id),
                    "Setup market evidence stale",
                    "Recorded evidence is stale or its closed-bar freshness window ended.",
                    "Review a fresh recorded evaluation; do not rely on the stale setup.",
                    shared=True,
                    expires=row.expires_at,
                    severity="high",
                    symbol=row.symbol,
                    strategy=str(row.strategy_id),
                    version=row.strategy_version_id,
                )

        # Latest observation per stage and lineage, including successful recovery records.
        observations = rows(
            PaperEvaluationObservationRow,
            PaperEvaluationObservationRow.occurred_at > now - MARKET_TTL,
            PaperEvaluationObservationRow.occurred_at <= now,
            PaperEvaluationObservationRow.replayed.is_(False),
            PaperEvaluationObservationRow.stage.in_(
                ("watcher_scan", "setup_assessment", "eligibility")
            ),
            private=False,
        )
        latest: dict[tuple[str, str, UUID | None, UUID | None, str], Any] = {}
        for row in sorted(observations, key=lambda r: (utc(r.occurred_at), str(r.observation_id))):
            lineage = str(row.candidate_id or "") if row.stage == "eligibility" else ""
            latest[
                (
                    row.stage,
                    row.source_system,
                    row.strategy_version_id,
                    row.setup_definition_id,
                    lineage,
                )
            ] = row
        for key, row in latest.items():
            reason = (
                row.reason_code or row.scan_status or row.assessment_state or "Recorded observation"
            )
            observed_category: Category | None = None
            if row.eligibility_state == "blocked":
                observed_category = Category.RISK_BLOCK
            elif row.reason_code in {"provider_outage", "provider_unreachable"}:
                observed_category = Category.PROVIDER_OUTAGE
            elif (
                row.reason_code in {"canonical_evidence_unavailable", "required_evidence_missing"}
                or row.data_quality == "unavailable"
            ):
                observed_category = Category.MISSING_EVIDENCE
            elif row.data_quality == "stale":
                observed_category = Category.STALE_EVIDENCE
            elif row.assessment_state == "confirmed_setup":
                observed_category = Category.CONFIRMED
            elif row.assessment_state in {"watch", "partial_match"}:
                observed_category = Category.FORMING
            elif row.stage == "watcher_scan" and row.scan_status in {
                "failed",
                "blocked",
                "degraded",
            }:
                observed_category = Category.WATCHER
            if (
                row.assessment_state in {"invalidated", "expired"}
                or row.eligibility_state == "expired"
            ):
                continue
            if observed_category in {Category.FORMING, Category.CONFIRMED} and (
                (row.assessment_id and str(row.assessment_id) in linked)
                or any(r.strategy_version_id == row.strategy_version_id for r in setups)
            ):
                continue
            if observed_category:
                add(
                    row,
                    row.occurred_at,
                    observed_category,
                    canonical_sha256(
                        {
                            "lineage": [
                                str(row.strategy_version_id),
                                str(row.setup_definition_id),
                                key[-1],
                                row.source_system if not row.strategy_version_id else "",
                            ]
                        }
                    ),
                    observed_category.value.replace("_", " ").capitalize(),
                    f"Recorded observation: {reason}.",
                    "Review the recorded evaluation; preserve risk and evidence gates.",
                    record_id=str(row.observation_id),
                    shared=True,
                    expires=utc(row.occurred_at) + MARKET_TTL,
                    version=row.strategy_version_id,
                    severity="high"
                    if observed_category not in {Category.FORMING, Category.CONFIRMED}
                    else "medium",
                )

        for row in rows(WatcherHealthSnapshotRow, private=False):
            if row.enabled and row.state not in {"healthy", "disabled"}:
                add(
                    row,
                    row.generated_at,
                    Category.WATCHER,
                    row.scan_scope,
                    "Watcher needs review",
                    f"Recorded state: {row.state}; reason: {row.reason_code}.",
                    "Review Watcher health and the recorded failure reason.",
                    shared=True,
                    expires=utc(row.generated_at) + MARKET_TTL,
                )
        config = self.session.get(WatcherWatchlistRow, org)
        if config:
            for row in rows(WatcherSymbolStatusRow, private=False):
                if row.configuration_revision != config.revision:
                    continue
                error = row.payload.get("error_state")
                freshness = row.payload.get("freshness")
                category = (
                    Category.PROVIDER_OUTAGE
                    if error in {"provider_outage", "provider_unreachable"}
                    else (Category.STALE_EVIDENCE if freshness == "stale" else Category.WATCHER)
                )
                if error or freshness == "stale":
                    add(
                        row,
                        row.observed_at,
                        category,
                        row.symbol,
                        "Watcher symbol needs review",
                        f"Recorded error: {error or 'none'}; freshness: {freshness or 'unknown'}.",
                        "Review this symbol's recorded Watcher evidence.",
                        record_id=row.symbol,
                        shared=True,
                        expires=utc(row.observed_at) + MARKET_TTL,
                        symbol=row.symbol,
                    )

        for row in rows(KillSwitchState, KillSwitchState.active.is_(True), private=False):
            add(
                row,
                row.updated_at,
                Category.RISK_BLOCK,
                "organization_kill_switch",
                "Organization kill switch active",
                "Stored tenant kill switch blocks execution.",
                "Review recorded kill-switch status; keep the execution block in force.",
                shared=True,
                severity="critical",
            )
        settings = self.session.scalar(
            select(UserRiskSettings).where(
                UserRiskSettings.organization_id == org, UserRiskSettings.user_id == user
            )
        )
        timezone = settings.timezone if settings else "UTC"
        day = now.astimezone(ZoneInfo(timezone)).date()
        for row in rows(DailyRiskState, DailyRiskState.day == day, DailyRiskState.locked.is_(True)):
            add(
                row,
                row.updated_at,
                Category.RISK_BLOCK,
                f"daily_lock:{day}",
                "Recorded daily risk lock active",
                f"Stored daily risk state is locked for {day} ({timezone}).",
                "Review the daily risk lock; preserve the recorded restriction.",
                severity="high",
                expires=daily_window(day, timezone).end,
            )
        for row in rows(RiskEvent, RiskEvent.event_at > now - RISK_TTL, RiskEvent.event_at <= now):
            if row.action_taken == RiskAction.ALLOW:
                continue
            category = (
                Category.RISK_BLOCK if row.action_taken == RiskAction.BLOCK else Category.RISK_EVENT
            )
            symbol = row.details.get("symbol")
            context = (
                row.details.get("candidate_id") or row.details.get("proposal_id") or symbol or ""
            )
            add(
                row,
                row.event_at,
                category,
                f"{row.rule_triggered.value}:{context}",
                "Risk block to review"
                if category == Category.RISK_BLOCK
                else "Risk event to review",
                f"Recorded rule: {row.rule_triggered.value}; action: {row.action_taken.value}.",
                "Review the risk event; preserve all risk restrictions.",
                severity="high"
                if category == Category.RISK_BLOCK
                and row.severity.value not in {"high", "critical"}
                else row.severity.value,
                expires=utc(row.event_at) + RISK_TTL,
                symbol=symbol,
            )
        for row in rows(
            JournalTrade,
            JournalTrade.status == JournalTradeStatus.OPEN,
            JournalTrade.source.in_(
                (JournalTradeSource.PAPER_EXECUTION, JournalTradeSource.PAPER_VALIDATION)
            ),
        ):
            add(
                row,
                row.updated_at,
                Category.POSITION,
                str(row.id),
                "Open paper position",
                "Canonical paper journal records this position as open.",
                "Review the paper position and its recorded risk plan.",
                symbol=row.symbol,
                strategy=str(row.user_strategy_id) if row.user_strategy_id else None,
                version=row.strategy_version_id,
                severity="low",
            )
        for row in rows(
            StrategyConversationProposal,
            StrategyConversationProposal.status == StrategyProposalStatus.DRAFT,
        ):
            add(
                row,
                row.created_at,
                Category.PROPOSAL,
                canonical_sha256(
                    {
                        "proposal": [
                            str(row.target_strategy_id),
                            str(row.parent_version_id),
                            row.content_hash,
                        ]
                    }
                )
                if row.content_hash
                else str(row.id),
                "Strategy proposal awaits approval",
                "Recorded strategy proposal is a draft; no confirmation is recorded.",
                "Review proposed rules and evidence in the human confirmation workflow.",
                strategy=str(row.target_strategy_id) if row.target_strategy_id else None,
                version=row.parent_version_id,
            )
        for model in (BacktestRun, PaperValidationRun):
            for row in rows(model):
                status = row.status.value
                if status == "cancelled":
                    continue
                terminal = status in {"completed", "failed", "passed"}
                category = (
                    Category.REPLAY if model is BacktestRun and terminal else Category.VALIDATION
                )
                add(
                    row,
                    row.updated_at,
                    category,
                    f"{row.__tablename__}:{row.id}",
                    "Recorded replay result"
                    if category == Category.REPLAY
                    else "Strategy validation job",
                    f"Recorded {row.__tablename__} status: {status}.",
                    "Review recorded evidence; strategy approval requires a human decision."
                    if terminal
                    else "Review job status in the existing validation workflow.",
                    expires=utc(row.updated_at) + RESEARCH_TTL if terminal else None,
                    severity="high" if status == "failed" else "info",
                    strategy=str(row.strategy_id),
                    version=row.strategy_version_id,
                )
        for row in rows(
            TelegramOutboxRow,
            TelegramOutboxRow.state.in_(
                (OutboxState.RETRYABLE.value, OutboxState.DEAD_LETTER.value)
            ),
        ):
            add(
                row,
                row.updated_at,
                Category.TELEGRAM_FAILURE,
                row.idempotency_key,
                "Telegram delivery failed",
                f"Recorded outbox state: {row.state}; attempts: {row.attempt}.",
                "Review delivery diagnostics and settings; this queue does not resend.",
                record_id=str(row.outbox_id),
            )
        alerts = self.session.scalars(
            select(PaperValidationAlert).where(
                PaperValidationAlert.organization_id == org,
                or_(PaperValidationAlert.user_id == user, PaperValidationAlert.user_id.is_(None)),
                PaperValidationAlert.delivery_channel == AlertDeliveryChannel.TELEGRAM,
                PaperValidationAlert.delivery_status == AlertDeliveryStatus.FAILED,
            )
        ).all()
        for row in alerts:
            add(
                row,
                row.updated_at,
                Category.TELEGRAM_FAILURE,
                row.dedup_key or str(row.id),
                "Telegram alert delivery failed",
                "Stored Telegram alert delivery status is failed.",
                "Review delivery diagnostics in alerts; this queue does not resend.",
                shared=row.user_id is None,
                acknowledgement="acknowledged" if row.read_at else "unacknowledged",
            )
        for row in rows(LessonCandidate, LessonCandidate.status == "pending_review"):
            add(
                row,
                row.created_at,
                Category.LESSON,
                lesson_key(row.lesson_text),
                "Lesson awaits review",
                row.lesson_text,
                "Review this recorded lesson before changing any strategy rules.",
                severity="low",
                strategy=str(row.related_strategy_id) if row.related_strategy_id else None,
            )
        review = DailyReviewService(self.session).review(
            organization_id=org,
            user_id=user,
            window=daily_window(now.astimezone(UTC).date()),
            generated_at=now,
        )
        for item in (*review.user_observations, *review.system_inference):
            if item.topic != ReviewTopic.LESSON or not item.text:
                continue
            if (
                item.code.startswith("lesson_candidate_")
                and item.code != "lesson_candidate_pending_review"
            ):
                continue
            symbol = None
            # Review contracts carry provenance but no symbol. Resolve only owned
            # journal references, never a global/unscoped get by a supplied ID.
            for source in item.sources:
                if source.record_type == TradeJournal.__tablename__:
                    symbol = self.session.scalar(
                        select(TradeJournal.symbol).where(
                            TradeJournal.id == UUID(source.record_id),
                            TradeJournal.organization_id == org,
                            TradeJournal.user_id == user,
                        )
                    )
                elif source.record_type == JournalTradeObservation.__tablename__:
                    symbol = self.session.scalar(
                        select(JournalTrade.symbol)
                        .join(
                            JournalTradeObservation,
                            JournalTrade.id == JournalTradeObservation.journal_trade_id,
                        )
                        .where(
                            JournalTradeObservation.id == UUID(source.record_id),
                            JournalTradeObservation.organization_id == org,
                            JournalTrade.organization_id == org,
                            JournalTrade.user_id == user,
                        )
                    )
            signals.append(
                AttentionSignal(
                    organization_id=org,
                    user_id=user,
                    semantic_key=lesson_key(item.text),
                    category=Category.LESSON,
                    severity="low",
                    title="Daily Review lesson",
                    reason=item.text,
                    symbol=symbol,
                    sources=item.sources,
                    strategy_version_id=item.strategy_version_id,
                    recommended_next_action="Review the lesson before changing strategy rules.",
                )
            )
        return signals

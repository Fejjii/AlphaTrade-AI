"""Research Validation Loop service (AT-035).

Advisory promotion of completed backtest evidence into the existing
paper-validation candidate queue. Paper-only — never feeds execution or risk.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import NotFoundError, ValidationAppError
from app.db.models import BacktestDataset as BacktestDatasetModel
from app.db.models import BacktestRun as BacktestRunModel
from app.db.models import PaperValidationAlert as AlertModel
from app.db.models import PaperValidationCandidate as CandidateModel
from app.db.models import PaperValidationDraft as DraftModel
from app.db.models import UserStrategy, UserStrategyVersion
from app.repositories.backtest import BacktestRunRepository
from app.repositories.paper_validation_candidate import PaperValidationCandidateRepository
from app.repositories.paper_validation_draft import PaperValidationDraftRepository
from app.repositories.paper_validation_run_plan import PaperValidationRunPlanRepository
from app.schemas.audit import AuditRecordCreate
from app.schemas.backtest import SetupEvidenceItem, SetupEvidenceTier
from app.schemas.common import (
    ActorType,
    AlertDeliveryChannel,
    AlertDeliveryStatus,
    AuditEventType,
    AuditResult,
    AuditSeverity,
    BacktestRunStatus,
    PaperAlertSeverity,
    PaperAlertType,
    PaperValidationCandidateStatus,
    PaperValidationDraftPrepStatus,
    PaperValidationDraftRiskMode,
    PaperValidationDraftStatus,
    PromotionSource,
    SetupAlertReviewStatus,
)
from app.schemas.paper_validation_draft import PaperValidationDraftChecklist
from app.schemas.research_validation import (
    ADVISORY_NOTE,
    PROMOTE_RESEARCH_VALIDATION_CANDIDATE_CONFIRM,
    ResearchValidationEligibility,
    ResearchValidationEvidenceItem,
    ResearchValidationEvidenceResponse,
    ResearchValidationLinks,
    ResearchValidationPromoteRequest,
    ResearchValidationPromoteResult,
    ResearchValidationStatusResponse,
)
from app.services.audit_service import AuditService
from app.services.paper_validation_candidate_service import PaperValidationCandidateService
from app.services.setup_evidence_service import SetupEvidenceService

_COMPLETE_CHECKLIST = PaperValidationDraftChecklist(
    trend_checked=True,
    support_resistance_checked=True,
    volume_checked=True,
    risk_reward_checked=True,
    invalidation_checked=True,
    higher_timeframe_checked=True,
    news_or_funding_checked=True,
)


class ResearchValidationService:
    """Evaluate research evidence and promote into the paper validation queue."""

    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._runs = BacktestRunRepository(session)
        self._candidates = PaperValidationCandidateRepository(session)
        self._drafts = PaperValidationDraftRepository(session)
        self._plans = PaperValidationRunPlanRepository(session)
        self._evidence = SetupEvidenceService(session, self._settings)
        self._audit = AuditService(session)

    def list_evidence(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        backtest_run_id: uuid.UUID | None = None,
        strategy_id: uuid.UUID | None = None,
        strategy_version_id: uuid.UUID | None = None,
    ) -> ResearchValidationEvidenceResponse:
        _ = user_id
        runs = self._runs.list_for_research_evidence(
            organization_id,
            backtest_run_id=backtest_run_id,
            strategy_id=strategy_id,
            strategy_version_id=strategy_version_id,
        )
        items = [self._build_evidence_item(run, organization_id=organization_id) for run in runs]
        return ResearchValidationEvidenceResponse(
            items=items,
            generated_at=datetime.now(UTC),
            note=ADVISORY_NOTE,
        )

    def get_status(
        self,
        backtest_run_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ResearchValidationStatusResponse:
        _ = user_id
        run = self._runs.get_scoped(backtest_run_id, organization_id=organization_id)
        if run is None:
            raise NotFoundError("Backtest run not found.")
        evidence = self._build_evidence_item(run, organization_id=organization_id)
        candidate = self._candidates.get_active_for_backtest_run(organization_id, backtest_run_id)
        links = self._build_links(
            backtest_run_id=backtest_run_id,
            strategy_id=run.strategy_id,
            strategy_version_id=run.strategy_version_id,
            candidate=candidate,
        )
        return ResearchValidationStatusResponse(
            evidence=evidence,
            links=links,
            generated_at=datetime.now(UTC),
            note=ADVISORY_NOTE,
        )

    def promote(
        self,
        payload: ResearchValidationPromoteRequest,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ResearchValidationPromoteResult:
        if payload.confirm != PROMOTE_RESEARCH_VALIDATION_CANDIDATE_CONFIRM:
            self._record_audit(
                "research_validation_promote_blocked",
                organization_id=organization_id,
                user_id=user_id,
                resource_id=str(payload.backtest_run_id),
                metadata={"reason": "confirmation_required"},
            )
            raise ValidationAppError(
                "Exact confirmation required to promote a research validation candidate.",
                details={
                    "required_confirm": PROMOTE_RESEARCH_VALIDATION_CANDIDATE_CONFIRM,
                },
            )

        self._record_audit(
            "research_validation_promote_requested",
            organization_id=organization_id,
            user_id=user_id,
            resource_id=str(payload.backtest_run_id),
        )

        run = self._runs.get_scoped(payload.backtest_run_id, organization_id=organization_id)
        if run is None:
            self._record_audit(
                "research_validation_promote_blocked",
                organization_id=organization_id,
                user_id=user_id,
                resource_id=str(payload.backtest_run_id),
                metadata={"reason": "backtest_not_found"},
            )
            raise ValidationAppError(
                "Backtest run not found for this organization.",
                details={"backtest_run_id": str(payload.backtest_run_id)},
            )

        eligibility, evidence_item, setup_item = self._evaluate_for_promote(
            run, organization_id=organization_id
        )
        if not eligibility.eligible:
            self._record_audit(
                "research_validation_promote_blocked",
                organization_id=organization_id,
                user_id=user_id,
                resource_id=str(payload.backtest_run_id),
                metadata={
                    "reason": eligibility.blocked_reason,
                    "tier": eligibility.tier.value if eligibility.tier else None,
                },
            )
            raise ValidationAppError(
                eligibility.blocked_reason or "Research validation promotion blocked.",
                details={
                    "backtest_run_id": str(payload.backtest_run_id),
                    "blocked_reason": eligibility.blocked_reason,
                    "tier": eligibility.tier.value if eligibility.tier else None,
                },
            )

        existing = self._candidates.get_active_for_backtest_run(
            organization_id, payload.backtest_run_id
        )
        if existing is not None:
            self._record_audit(
                "research_validation_promote_already_exists",
                organization_id=organization_id,
                user_id=user_id,
                resource_id=str(payload.backtest_run_id),
                metadata={"candidate_id": str(existing.id)},
            )
            return ResearchValidationPromoteResult(
                candidate=PaperValidationCandidateService._to_item(existing),
                already_exists=True,
                eligibility=eligibility,
                links=self._build_links(
                    backtest_run_id=payload.backtest_run_id,
                    strategy_id=run.strategy_id,
                    strategy_version_id=run.strategy_version_id,
                    candidate=existing,
                ),
            )

        assert setup_item is not None
        assert evidence_item is not None
        assert run.strategy_version_id is not None

        alert = self._create_synthetic_alert(
            run,
            evidence_item=evidence_item,
            organization_id=organization_id,
            user_id=user_id,
        )
        draft = self._create_synthetic_draft(
            alert,
            run,
            evidence_item=evidence_item,
            organization_id=organization_id,
            user_id=user_id,
        )
        candidate = self._create_candidate(
            draft,
            run,
            evidence_item=evidence_item,
            setup_item=setup_item,
            organization_id=organization_id,
            user_id=user_id,
        )
        self._candidates.add(candidate)
        self._record_audit(
            "research_validation_candidate_created",
            organization_id=organization_id,
            user_id=user_id,
            resource_id=str(payload.backtest_run_id),
            metadata={
                "candidate_id": str(candidate.id),
                "draft_id": str(draft.id),
                "source_alert_id": str(alert.id),
                "evidence_tier": evidence_item.evidence_tier.value,
            },
        )
        return ResearchValidationPromoteResult(
            candidate=PaperValidationCandidateService._to_item(candidate),
            already_exists=False,
            eligibility=eligibility,
            links=self._build_links(
                backtest_run_id=payload.backtest_run_id,
                strategy_id=run.strategy_id,
                strategy_version_id=run.strategy_version_id,
                candidate=candidate,
            ),
        )

    def _evaluate_for_promote(
        self,
        run: BacktestRunModel,
        *,
        organization_id: uuid.UUID,
    ) -> tuple[
        ResearchValidationEligibility,
        ResearchValidationEvidenceItem | None,
        SetupEvidenceItem | None,
    ]:
        blocked = self._hard_block_reason(run)
        if blocked is not None:
            tier: SetupEvidenceTier | None = None
            setup_item: SetupEvidenceItem | None = None
            if run.strategy_version_id is not None:
                setup_item = self._setup_evidence_for_version(
                    organization_id=organization_id,
                    user_id=run.user_id,
                    strategy_id=run.strategy_id,
                    strategy_version_id=run.strategy_version_id,
                )
                if setup_item is not None:
                    tier = setup_item.tier
            return (
                ResearchValidationEligibility(
                    eligible=False,
                    tier=tier,
                    warnings=[],
                    blocked_reason=blocked,
                ),
                None,
                setup_item,
            )

        assert run.strategy_version_id is not None
        setup_item = self._setup_evidence_for_version(
            organization_id=organization_id,
            user_id=run.user_id,
            strategy_id=run.strategy_id,
            strategy_version_id=run.strategy_version_id,
        )
        if setup_item is None:
            return (
                ResearchValidationEligibility(
                    eligible=False,
                    tier=None,
                    warnings=[],
                    blocked_reason="Strategy version not found for this organization.",
                ),
                None,
                None,
            )

        evidence = self._build_evidence_item(
            run,
            organization_id=organization_id,
            setup_item=setup_item,
        )
        if setup_item.tier == SetupEvidenceTier.TIER3:
            blocked_tier3 = "Insufficient evidence (tier3) for research validation promotion."
            return (
                ResearchValidationEligibility(
                    eligible=False,
                    tier=SetupEvidenceTier.TIER3,
                    warnings=evidence.warnings,
                    blocked_reason=blocked_tier3,
                ),
                evidence,
                setup_item,
            )

        return (
            ResearchValidationEligibility(
                eligible=True,
                tier=setup_item.tier,
                warnings=evidence.warnings,
                blocked_reason=None,
            ),
            evidence,
            setup_item,
        )

    def _hard_block_reason(self, run: BacktestRunModel) -> str | None:
        status = run.status
        status_value = status.value if isinstance(status, BacktestRunStatus) else str(status)
        if status_value != BacktestRunStatus.COMPLETED.value:
            return "Backtest run is not completed."
        if run.strategy_version_id is None:
            return "Backtest run is missing strategy_version_id."
        result = run.result if isinstance(run.result, dict) else None
        oos = result.get("oos_metrics") if result is not None else None
        if not isinstance(oos, dict):
            return "Backtest run is missing out-of-sample (OOS) metrics."
        return None

    def _build_evidence_item(
        self,
        run: BacktestRunModel,
        *,
        organization_id: uuid.UUID,
        setup_item: SetupEvidenceItem | None = None,
    ) -> ResearchValidationEvidenceItem:
        strategy, version = self._load_strategy_version(run)
        if setup_item is None and run.strategy_version_id is not None:
            setup_item = self._setup_evidence_for_version(
                organization_id=organization_id,
                user_id=run.user_id,
                strategy_id=run.strategy_id,
                strategy_version_id=run.strategy_version_id,
            )

        oos_trade_count, oos_expectancy, oos_profit_factor, total_trades = (
            self._extract_run_metrics(run)
        )
        sample_size = oos_trade_count if oos_trade_count > 0 else total_trades
        symbol, timeframe, regime, dataset_hash = self._extract_context(run)

        tier = setup_item.tier if setup_item is not None else SetupEvidenceTier.TIER3
        confirm_trade_count = (
            setup_item.measured.confirm_trade_count if setup_item is not None else 0
        )
        warnings = self._warnings_for(
            tier=tier,
            confirm_trade_count=confirm_trade_count,
            oos_trade_count=oos_trade_count,
        )

        blocked = self._hard_block_reason(run)
        if blocked is None and tier == SetupEvidenceTier.TIER3:
            blocked = "Insufficient evidence (tier3) for research validation promotion."

        eligible = blocked is None and tier in {
            SetupEvidenceTier.TIER1,
            SetupEvidenceTier.TIER2,
        }

        existing_candidate = self._candidates.get_active_for_backtest_run(organization_id, run.id)
        existing_plan_id: uuid.UUID | None = None
        if existing_candidate is not None:
            plan = self._plans.get_active_for_candidate(organization_id, existing_candidate.id)
            if plan is not None:
                existing_plan_id = plan.id

        status = (
            run.status
            if isinstance(run.status, BacktestRunStatus)
            else BacktestRunStatus(str(run.status))
        )

        return ResearchValidationEvidenceItem(
            backtest_run_id=run.id,
            strategy_id=run.strategy_id,
            strategy_version_id=run.strategy_version_id,
            strategy_name=strategy.name if strategy is not None else "unknown",
            version=version.version if version is not None else 0,
            symbol=symbol,
            timeframe=timeframe,
            regime=regime,
            status=status,
            dataset_hash=dataset_hash,
            config_hash=run.config_hash,
            result_hash=run.result_hash,
            evidence_tier=tier,
            sample_size=sample_size,
            oos_trade_count=oos_trade_count,
            oos_expectancy=oos_expectancy,
            oos_profit_factor=oos_profit_factor,
            confirm_trade_count=confirm_trade_count,
            eligible_for_promotion=eligible,
            warnings=warnings,
            existing_candidate_id=existing_candidate.id if existing_candidate else None,
            existing_run_plan_id=existing_plan_id,
            promotion_blocked_reason=blocked,
        )

    def _warnings_for(
        self,
        *,
        tier: SetupEvidenceTier,
        confirm_trade_count: int,
        oos_trade_count: int,
    ) -> list[str]:
        warnings: list[str] = []
        if confirm_trade_count < self._settings.backtest_tier1_min_confirm_trades:
            warnings.append("insufficient_confirm_sample")
        _ = (tier, oos_trade_count)
        return warnings

    def _setup_evidence_for_version(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        strategy_id: uuid.UUID,
        strategy_version_id: uuid.UUID,
    ) -> SetupEvidenceItem | None:
        response = self._evidence.evaluate(
            organization_id=organization_id,
            user_id=user_id,
            strategy_id=strategy_id,
            strategy_version_id=strategy_version_id,
        )
        for item in response.items:
            if item.strategy_version_id == strategy_version_id:
                return item
        return None

    def _load_strategy_version(
        self, run: BacktestRunModel
    ) -> tuple[UserStrategy | None, UserStrategyVersion | None]:
        strategy = self._session.get(UserStrategy, run.strategy_id)
        version: UserStrategyVersion | None = None
        if run.strategy_version_id is not None:
            version = self._session.get(UserStrategyVersion, run.strategy_version_id)
        return strategy, version

    @staticmethod
    def _extract_run_metrics(
        run: BacktestRunModel,
    ) -> tuple[int, Decimal | None, float | None, int]:
        result = run.result if isinstance(run.result, dict) else {}
        raw_metrics = result.get("metrics")
        metrics: dict[str, Any] = raw_metrics if isinstance(raw_metrics, dict) else {}
        total_trades = int(metrics.get("trade_count") or 0)
        oos = result.get("oos_metrics")
        if not isinstance(oos, dict):
            return 0, None, None, total_trades
        oos_trade_count = int(oos.get("trade_count") or 0)
        raw_exp = oos.get("expectancy")
        oos_expectancy = Decimal(str(raw_exp)) if raw_exp is not None else None
        raw_pf = oos.get("profit_factor")
        oos_profit_factor = float(raw_pf) if raw_pf is not None else None
        return oos_trade_count, oos_expectancy, oos_profit_factor, total_trades

    def _extract_context(
        self, run: BacktestRunModel
    ) -> tuple[str | None, str | None, str | None, str | None]:
        symbol: str | None = None
        timeframe: str | None = None
        regime: str | None = None
        dataset_hash: str | None = None

        if run.dataset_id is not None:
            dataset = self._session.get(BacktestDatasetModel, run.dataset_id)
            if dataset is not None:
                symbol = dataset.symbol
                timeframe = dataset.timeframe
                dataset_hash = dataset.dataset_hash

        assumptions = run.assumptions if isinstance(run.assumptions, dict) else {}
        if symbol is None and isinstance(assumptions.get("symbol"), str):
            symbol = assumptions["symbol"]
        if timeframe is None:
            tf = assumptions.get("timeframe")
            if isinstance(tf, str):
                timeframe = tf

        snapshot = run.config_snapshot if isinstance(run.config_snapshot, dict) else {}
        if dataset_hash is None and isinstance(snapshot.get("dataset_hash"), str):
            dataset_hash = snapshot["dataset_hash"]
        regime = self._extract_regime(snapshot, assumptions)
        return symbol, timeframe, regime, dataset_hash

    @staticmethod
    def _extract_regime(
        snapshot: dict[str, Any],
        assumptions: dict[str, Any],
    ) -> str | None:
        for source in (snapshot, assumptions, snapshot.get("assumptions")):
            if not isinstance(source, dict):
                continue
            for key in ("regime", "market_regime"):
                value = source.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return None

    def _create_synthetic_alert(
        self,
        run: BacktestRunModel,
        *,
        evidence_item: ResearchValidationEvidenceItem,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> AlertModel:
        dedup_key = f"research_validation:{run.id}"
        alert = AlertModel(
            organization_id=organization_id,
            user_id=user_id,
            alert_type=PaperAlertType.RESEARCH_VALIDATION_PROMOTION,
            severity=PaperAlertSeverity.INFO,
            strategy_id=run.strategy_id,
            message=(
                "Research validation promotion for "
                f"{evidence_item.strategy_name} v{evidence_item.version} "
                f"({evidence_item.evidence_tier.value})."
            ),
            dedup_key=dedup_key,
            metadata_json={
                "source": "research_validation",
                "backtest_run_id": str(run.id),
                "strategy_id": str(run.strategy_id),
                "strategy_version_id": str(run.strategy_version_id),
                "evidence_tier": evidence_item.evidence_tier.value,
                "symbol": evidence_item.symbol,
                "timeframe": evidence_item.timeframe,
                "condition": "research_validation",
            },
            delivery_status=AlertDeliveryStatus.DISABLED,
            delivery_channel=AlertDeliveryChannel.IN_APP,
            review_status=SetupAlertReviewStatus.IMPORTANT.value,
        )
        self._session.add(alert)
        self._session.flush()
        return alert

    def _create_synthetic_draft(
        self,
        alert: AlertModel,
        run: BacktestRunModel,
        *,
        evidence_item: ResearchValidationEvidenceItem,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> DraftModel:
        thesis = (
            f"Research validation promotion from backtest {run.id} "
            f"({evidence_item.strategy_name} v{evidence_item.version}, "
            f"{evidence_item.evidence_tier.value}). Advisory only."
        )
        entry = (
            "Paper-validate the researched setup using the frozen backtest "
            "assumptions and evidence snapshot; no live execution."
        )
        invalidation = (
            "Invalidate if live paper outcomes diverge materially from OOS "
            "expectancy/profit-factor, or if data freshness/regime context breaks."
        )
        risk_notes = (
            "Research-origin candidate. Paper-only. Does not authorize real trading "
            "or change risk controls."
        )
        draft = DraftModel(
            organization_id=organization_id,
            source_alert_id=alert.id,
            symbol=evidence_item.symbol,
            timeframe=evidence_item.timeframe,
            condition="research_validation",
            direction=None,
            confidence=None,
            reason=thesis,
            review_status=SetupAlertReviewStatus.IMPORTANT.value,
            risk_mode=PaperValidationDraftRiskMode.CONSERVATIVE.value,
            status=PaperValidationDraftStatus.DRAFT.value,
            created_by=user_id,
            thesis=thesis,
            entry_criteria=entry,
            invalidation_criteria=invalidation,
            risk_notes=risk_notes,
            checklist_status=_COMPLETE_CHECKLIST.model_dump(),
            prep_status=PaperValidationDraftPrepStatus.READY_FOR_VALIDATION.value,
        )
        self._drafts.add(draft)
        return draft

    def _create_candidate(
        self,
        draft: DraftModel,
        run: BacktestRunModel,
        *,
        evidence_item: ResearchValidationEvidenceItem,
        setup_item: SetupEvidenceItem,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> CandidateModel:
        snapshot: dict[str, Any] = {
            "measured": setup_item.measured.model_dump(mode="json"),
            "thresholds": setup_item.thresholds.model_dump(mode="json"),
            "tier": setup_item.tier.value,
            "backtest_run_id": str(run.id),
            "oos_trade_count": evidence_item.oos_trade_count,
            "oos_expectancy": (
                str(evidence_item.oos_expectancy)
                if evidence_item.oos_expectancy is not None
                else None
            ),
            "oos_profit_factor": evidence_item.oos_profit_factor,
            "sample_size": evidence_item.sample_size,
            "warnings": list(evidence_item.warnings),
        }
        return CandidateModel(
            organization_id=organization_id,
            draft_id=draft.id,
            source_alert_id=draft.source_alert_id,
            symbol=draft.symbol,
            timeframe=draft.timeframe,
            condition=draft.condition,
            direction=draft.direction,
            confidence=draft.confidence,
            trigger_level=draft.trigger_level,
            invalidation_level=draft.invalidation_level,
            latest_price=draft.latest_price,
            thesis=draft.thesis,
            entry_criteria=draft.entry_criteria,
            invalidation_criteria=draft.invalidation_criteria,
            risk_notes=draft.risk_notes,
            checklist_snapshot=_COMPLETE_CHECKLIST.model_dump(),
            risk_mode=draft.risk_mode,
            candidate_status=PaperValidationCandidateStatus.QUEUED.value,
            created_by=user_id,
            promotion_source=PromotionSource.RESEARCH_VALIDATION.value,
            backtest_run_id=run.id,
            strategy_id=run.strategy_id,
            strategy_version_id=run.strategy_version_id,
            dataset_hash=evidence_item.dataset_hash,
            config_hash=run.config_hash,
            result_hash=run.result_hash,
            evidence_tier=evidence_item.evidence_tier.value,
            sample_size=evidence_item.sample_size,
            oos_expectancy=evidence_item.oos_expectancy,
            regime=evidence_item.regime,
            evidence_snapshot=snapshot,
        )

    def _build_links(
        self,
        *,
        backtest_run_id: uuid.UUID,
        strategy_id: uuid.UUID | None,
        strategy_version_id: uuid.UUID | None,
        candidate: CandidateModel | None,
    ) -> ResearchValidationLinks:
        run_plan_id: uuid.UUID | None = None
        if candidate is not None:
            plan = self._plans.get_active_for_candidate(candidate.organization_id, candidate.id)
            if plan is not None:
                run_plan_id = plan.id

        comparison_path: str | None = None
        setup_path: str | None = None
        stats_path: str | None = None
        if strategy_id is not None and strategy_version_id is not None:
            comparison_path = (
                f"/journal/comparison?strategy_id={strategy_id}"
                f"&strategy_version_id={strategy_version_id}"
            )
            setup_path = (
                f"/journal/setup-evidence?strategy_id={strategy_id}"
                f"&strategy_version_id={strategy_version_id}"
            )
            stats_path = (
                f"/journal/statistics?user_strategy_id={strategy_id}"
                f"&strategy_version_id={strategy_version_id}"
            )

        return ResearchValidationLinks(
            candidate_id=candidate.id if candidate is not None else None,
            draft_id=candidate.draft_id if candidate is not None else None,
            source_alert_id=candidate.source_alert_id if candidate is not None else None,
            run_plan_id=run_plan_id,
            backtest_run_id=backtest_run_id,
            strategy_id=strategy_id,
            strategy_version_id=strategy_version_id,
            journal_comparison_path=comparison_path,
            setup_evidence_path=setup_path,
            journal_statistics_path=stats_path,
        )

    def _record_audit(
        self,
        action: str,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
        resource_id: str,
        metadata: dict[str, object] | None = None,
    ) -> None:
        self._audit.record(
            AuditRecordCreate(
                request_id=f"research-validation-{resource_id}",
                trace_id=str(uuid.uuid4()),
                user_id=user_id,
                organization_id=organization_id,
                event_type=AuditEventType.PAPER_VALIDATION_RUNTIME,
                resource_type="research_validation",
                resource_id=resource_id,
                actor_type=ActorType.USER,
                result=AuditResult.SUCCESS,
                severity=AuditSeverity.INFO,
                metadata={"action": action, **(metadata or {})},
            )
        )

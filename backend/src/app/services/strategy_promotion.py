"""Conservative strategy promotion after backtest v1."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import ConflictError, NotFoundError, TradingPolicyError, ValidationAppError
from app.db.models import (
    BacktestRun,
    PaperTrade,
    PaperValidationRun,
    StrategyConversationProposal,
    StrategyLifecycleEvent,
    UserStrategy,
    UserStrategyVersion,
)
from app.repositories.conversations import StrategyConversationProposalRepository
from app.schemas.backtest import BacktestMetrics
from app.schemas.common import (
    BacktestRecommendation,
    BacktestSplitLabel,
    BacktestStatus,
    PaperTradeStatus,
    PaperValidationRuntimeMode,
    PaperValidationStatus,
    StrategyLifecycleState,
    StrategyProposalStatus,
    StrategyValidationStatus,
)
from app.schemas.governed_learning import (
    GOVERNED_LEARNING,
    GovernedLearningList,
    GovernedLearningStatus,
    LearningPromotionApproval,
    LearningRollbackApproval,
    LearningValidationEvidence,
)
from app.schemas.strategy_library import StrategyCard
from app.schemas.strategy_lifecycle import StrategyLifecycleEventRecord
from app.schemas.strategy_replay import ReplayComparison, ReplayComparisonRequest

MIN_SAMPLE_SIZE = 20
PREFERRED_SAMPLE_SIZE = 30
MIN_PROFIT_FACTOR = 1.1
MAX_DRAWDOWN_PCT = 25.0
MAX_SINGLE_LOSS_PCT_OF_CAPITAL = 10.0

_VALIDATION_REFS = "governed_validation_001"


class StrategyPromotionService:
    """Governed paper promotion using canonical proposals, replays and version history.

    Legacy backtest recommendations below remain descriptive and are never approval.
    """

    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        from app.services.strategy_proposal_service import StrategyProposalService
        from app.services.strategy_versioning import StrategyVersioningService

        self._session = session
        self._settings = settings or get_settings()
        self._proposals = StrategyProposalService(session)
        self._versions = StrategyVersioningService(session)

    def _require(
        self, proposal_id: UUID, organization_id: UUID, user_id: UUID, *, lock: bool = False
    ) -> StrategyConversationProposal:
        row = (
            StrategyConversationProposalRepository(self._session).get_scoped_for_update(
                proposal_id, organization_id=organization_id, user_id=user_id
            )
            if lock
            else self._proposals.require(
                proposal_id, organization_id=organization_id, user_id=user_id
            )
        )
        if row is None:
            raise NotFoundError("Governed strategy proposal not found.")
        if GOVERNED_LEARNING not in row.context_refs:
            raise NotFoundError("Governed strategy proposal not found.")
        self._proposals.assert_governed_identity(row, row.content_hash or "")
        return row

    def _compare(self, row: StrategyConversationProposal) -> ReplayComparison:
        from app.services.backtest_service import BacktestService
        from app.services.strategy_replay_service import StrategyReplayService

        refs = row.context_refs.get(_VALIDATION_REFS, {})
        if not refs.get("baseline_run_id") or not refs.get("proposed_run_id"):
            raise ValidationAppError("Completed replay and baseline comparison are missing.")
        comparison = StrategyReplayService(
            self._session, BacktestService(self._session, self._settings)
        ).compare(
            ReplayComparisonRequest(
                baseline_run_id=refs["baseline_run_id"],
                proposed_run_id=refs["proposed_run_id"],
            ),
            organization_id=row.organization_id,
            user_id=row.user_id,
            persist_audit=False,
        )
        if (
            comparison.baseline_version_id != row.parent_version_id
            or comparison.proposed_version_id != row.resulting_version_id
        ):
            raise ValidationAppError(
                "Baseline/candidate mismatch: exact proposal versions required."
            )
        for run_id in (comparison.baseline_run_id, comparison.proposed_run_id):
            run = self._session.get(BacktestRun, run_id)
            if run is None or run.strategy_id != row.target_strategy_id:
                raise ValidationAppError("Comparison strategy does not match the proposal.")
        return comparison

    def _paper(self, row: StrategyConversationProposal) -> PaperValidationRun:
        refs = row.context_refs.get(_VALIDATION_REFS, {})
        identity = refs.get("paper_validation_run_id")
        run = self._session.get(PaperValidationRun, UUID(identity)) if identity else None
        if (
            run is None
            or run.organization_id != row.organization_id
            or run.user_id != row.user_id
            or run.strategy_id != row.target_strategy_id
            or run.strategy_version_id != row.resulting_version_id
        ):
            raise ValidationAppError(
                "Separate paper validation for the exact candidate is missing."
            )
        return run

    def _promotion_event(self, row: StrategyConversationProposal) -> StrategyLifecycleEvent | None:
        return self._session.scalar(
            select(StrategyLifecycleEvent)
            .where(
                StrategyLifecycleEvent.organization_id == row.organization_id,
                StrategyLifecycleEvent.strategy_version_id == row.resulting_version_id,
                StrategyLifecycleEvent.reason == "governed paper promotion",
            )
            .order_by(StrategyLifecycleEvent.occurred_at.desc())
            .limit(1)
        )

    def status(
        self, proposal_id: UUID, *, organization_id: UUID, user_id: UUID
    ) -> GovernedLearningStatus:
        """Bounded SELECTs only; missing evidence never becomes a performance claim."""
        with self._session.no_autoflush:
            row = self._require(proposal_id, organization_id, user_id)
            if (
                row.target_strategy_id is None
                or row.parent_version_id is None
                or row.content_hash is None
            ):
                raise ValidationAppError("Governed proposal is missing captured strategy identity.")
            metadata = row.context_refs[GOVERNED_LEARNING]
            strategy = self._versions.require_strategy(
                row.target_strategy_id,
                organization_id=organization_id,
                user_id=user_id,
            )
            selected = self._versions.selected_version(strategy)
            state = (
                self._versions.latest_lifecycle_event_for_version(selected.id) if selected else None
            )
            active = (
                selected
                if state
                and state.new_state
                in {
                    StrategyLifecycleState.APPROVED,
                    StrategyLifecycleState.ACTIVE,
                    StrategyLifecycleState.PAPER_ACTIVE,
                }
                else None
            )
            promotion = self._promotion_event(row)
            approval_state = (
                "approved"
                if promotion
                else "validating"
                if row.resulting_version_id
                else "proposed"
            )
            if row.status is StrategyProposalStatus.REJECTED:
                approval_state = "rejected"
            elif row.status is StrategyProposalStatus.SUPERSEDED:
                approval_state = "superseded"
            if (
                promotion
                and state
                and state.evidence_snapshot.get("rolled_back_from_version_id")
                == str(row.resulting_version_id)
            ):
                approval_state = "rolled_back"
            result = GovernedLearningStatus(
                proposal_id=row.id,
                strategy_id=strategy.id,
                base_version_id=row.parent_version_id,
                proposed_version_id=row.resulting_version_id,
                content_hash=row.content_hash,
                source_observations=metadata["source_observations"],
                hypothesis=metadata["hypothesis"],
                reason=metadata["reason"],
                proposed_parameters=metadata["proposed_parameters"],
                evidence_ids=metadata["evidence_ids"],
                sample_limitations=metadata["sample_limitations"],
                validation_plan=metadata["validation_plan"],
                created_by=row.user_id,
                created_at=row.created_at,
                approval_state=approval_state,
                paper_active_version_id=active.id if active else None,
            )
            if promotion:
                rollback = promotion.evidence_snapshot.get("rollback_version_id")
                result.rollback_version_id = UUID(rollback) if rollback else None
                result.can_roll_back = bool(
                    active and active.id == row.resulting_version_id and rollback
                )
                if result.can_roll_back and result.rollback_version_id is not None:
                    from app.services.canonical_strategy_evaluation import (
                        resolve_executable_strategy_policy,
                    )
                    from app.signal_fusion.errors import StrategyEvaluationPolicyError

                    try:
                        resolve_executable_strategy_policy(
                            self._session,
                            organization_id=organization_id,
                            user_id=user_id,
                            strategy_version_id=result.rollback_version_id,
                        )
                    except (NotFoundError, StrategyEvaluationPolicyError):
                        result.can_roll_back = False
            comparison = None
            try:
                comparison = self._compare(row)
                result.replayed = True
                result.comparison_hash = comparison.comparison_hash
                result.baseline_run_id = comparison.baseline_run_id
                result.proposed_run_id = comparison.proposed_run_id
                result.observed_net_pnl_delta = comparison.evaluation_net_pnl_delta
                result.outperformed_baseline = (
                    comparison.evaluation_net_pnl_delta > 0
                    if comparison.evaluation_net_pnl_delta is not None
                    else None
                )
                if any(
                    sample.status in {"missing_data", "cancelled"}
                    for sample in [*comparison.baseline_samples, *comparison.proposed_samples]
                ):
                    result.blockers.append("Replay has missing data or was cancelled.")
            except (ValidationAppError, NotFoundError, ValueError, KeyError) as exc:
                result.blockers.append(str(exc))
            paper_count = 0
            try:
                paper = self._paper(row)
                result.paper_validation_run_id = paper.id
                trades = select(PaperTrade).where(
                    PaperTrade.paper_validation_run_id == paper.id,
                    PaperTrade.organization_id == organization_id,
                    PaperTrade.user_id == user_id,
                    PaperTrade.strategy_version_id == row.resulting_version_id,
                    PaperTrade.status == PaperTradeStatus.CLOSED,
                )
                paper_count = (
                    self._session.scalar(select(func.count()).select_from(trades.subquery())) or 0
                )
                missing_pnl = (
                    self._session.scalar(
                        select(func.count()).select_from(
                            trades.where(PaperTrade.net_pnl.is_(None)).subquery()
                        )
                    )
                    or 0
                )
                measured = trades.subquery()
                net_pnl = self._session.scalar(select(func.sum(measured.c.net_pnl))) or Decimal(0)
                complete = (
                    paper.status is PaperValidationStatus.PASSED
                    and paper.ended_at is not None
                    and paper.runtime_mode is PaperValidationRuntimeMode.AUTO_PAPER
                    and not paper.blockers
                    and not missing_pnl
                    and (paper.metrics or {}).get("paper_trades_count") == paper_count
                    and Decimal(str((paper.metrics or {}).get("net_pnl", "NaN"))) == net_pnl
                )
                result.paper_validation_completed = complete
                if not complete:
                    result.blockers.append(
                        "Paper validation has not completed with reconciled closed trades."
                    )
            except ValidationAppError as exc:
                result.blockers.append(str(exc))
            parent = self._session.get(UserStrategyVersion, row.parent_version_id)
            requirements = (
                StrategyCard.model_validate(parent.card).promotion_requirements if parent else None
            )
            replay_counts = (
                [
                    s.trade_count
                    for s in [*comparison.baseline_samples, *comparison.proposed_samples]
                    if s.split_label is BacktestSplitLabel.OUT_OF_SAMPLE
                ]
                if comparison
                else []
            )
            if comparison and (not replay_counts or min(replay_counts) <= 1):
                result.blockers.append("One winning trade cannot establish a strategy promotion.")
            if result.paper_validation_completed and paper_count <= 1:
                result.blockers.append("One paper trade cannot establish strategy validation.")
            declared = bool(
                requirements
                and requirements.minimum_replay_trades is not None
                and requirements.minimum_paper_trades is not None
            )
            if requirements:
                if (
                    replay_counts
                    and requirements.minimum_replay_trades is not None
                    and min(replay_counts) < requirements.minimum_replay_trades
                ):
                    result.blockers.append(
                        "Insufficient replay evidence for the base strategy's requirements."
                    )
                if (
                    result.paper_validation_completed
                    and requirements.minimum_paper_trades is not None
                    and paper_count < requirements.minimum_paper_trades
                ):
                    result.blockers.append(
                        "Insufficient paper evidence for the base strategy's requirements."
                    )
            result.insufficient_evidence = not declared or bool(result.blockers)
            result.explicit_evidence_review_required = (
                result.insufficient_evidence
                or bool(result.sample_limitations)
                or result.outperformed_baseline is not True
                or bool(
                    comparison
                    and any(
                        s.status == "insufficient_sample"
                        for s in [*comparison.baseline_samples, *comparison.proposed_samples]
                    )
                )
            )
            return result

    def list_status(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        strategy_id: UUID | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> GovernedLearningList:
        if not 1 <= limit <= 20 or not 0 <= offset <= 10000:
            raise ValidationAppError(
                "Status reads are limited to 1-20 proposals and a bounded offset."
            )
        query = select(StrategyConversationProposal.id).where(
            StrategyConversationProposal.organization_id == organization_id,
            StrategyConversationProposal.user_id == user_id,
            StrategyConversationProposal.context_refs[GOVERNED_LEARNING].is_not(None),
        )
        # JSON null differs between SQLite and PostgreSQL; require the discriminator's reason.
        query = query.where(
            StrategyConversationProposal.context_refs[GOVERNED_LEARNING]["reason"]
            .as_string()
            .is_not(None)
        )
        if strategy_id is not None:
            with self._session.no_autoflush:
                self._versions.require_strategy(
                    strategy_id, organization_id=organization_id, user_id=user_id
                )
            query = query.where(StrategyConversationProposal.target_strategy_id == strategy_id)
        with self._session.no_autoflush:
            ids = list(
                self._session.scalars(
                    query.order_by(StrategyConversationProposal.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
            )
        return GovernedLearningList(
            items=[
                self.status(identity, organization_id=organization_id, user_id=user_id)
                for identity in ids
            ],
            limit=limit,
            offset=offset,
        )

    def record_validation(
        self,
        proposal_id: UUID,
        payload: LearningValidationEvidence,
        *,
        organization_id: UUID,
        user_id: UUID,
    ) -> GovernedLearningStatus:
        row = self._require(proposal_id, organization_id, user_id, lock=True)
        self._proposals.assert_governed_identity(row, payload.expected_content_hash)
        if not row.resulting_version_id or self._promotion_event(row):
            raise ConflictError("Validation requires an unpromoted immutable candidate.")
        with self._session.begin_nested():
            row.context_refs = {
                **row.context_refs,
                _VALIDATION_REFS: payload.model_dump(
                    mode="json", exclude={"expected_content_hash"}
                ),
            }
            self._compare(row)
            if payload.paper_validation_run_id:
                self._paper(row)
            self._session.flush()
        return self.status(proposal_id, organization_id=organization_id, user_id=user_id)

    def require_candidate_replay(
        self, version_id: UUID, *, organization_id: UUID, user_id: UUID
    ) -> StrategyConversationProposal:
        row = self._session.scalar(
            select(StrategyConversationProposal).where(
                StrategyConversationProposal.organization_id == organization_id,
                StrategyConversationProposal.user_id == user_id,
                StrategyConversationProposal.resulting_version_id == version_id,
            )
        )
        if row is None or GOVERNED_LEARNING not in row.context_refs:
            raise ValidationAppError("Exact candidate is not a governed validation request.")
        if self._promotion_event(row):
            raise ValidationAppError("Promoted versions cannot restart candidate validation.")
        self._proposals.assert_governed_identity(row, row.content_hash or "")
        comparison = self._compare(row)
        if any(
            s.status in {"missing_data", "cancelled"}
            for s in [*comparison.baseline_samples, *comparison.proposed_samples]
        ):
            raise ValidationAppError("Candidate replay has missing data or was cancelled.")
        return row

    def promote(
        self,
        proposal_id: UUID,
        payload: LearningPromotionApproval,
        *,
        organization_id: UUID,
        user_id: UUID,
    ) -> StrategyLifecycleEventRecord:
        from app.interactive_agent.action_registry import require_action_permission
        from app.services.compiled_setup_service import CompiledSetupService

        require_action_permission(self._session, organization_id=organization_id, user_id=user_id)
        if payload.execution_mode != "paper" or payload.confirm != "APPROVE_PAPER_PROMOTION":
            raise TradingPolicyError(
                "Only explicit human approval for paper promotion is permitted."
            )
        row = self._require(proposal_id, organization_id, user_id, lock=True)
        self._proposals.assert_governed_identity(row, payload.expected_content_hash)
        if payload.expected_version_id != row.resulting_version_id:
            raise ConflictError("Approval version does not match the immutable candidate.")
        previous = self._promotion_event(row)
        if previous:
            if previous.evidence_snapshot.get(
                "comparison_hash"
            ) != payload.expected_comparison_hash or previous.evidence_snapshot.get(
                "paper_validation_run_id"
            ) != str(payload.expected_paper_validation_run_id):
                raise ConflictError("Duplicate approval evidence identity differs.")
            return StrategyLifecycleEventRecord.model_validate(previous, from_attributes=True)
        strategy = self._session.scalar(
            select(UserStrategy).where(UserStrategy.id == row.target_strategy_id).with_for_update()
        )
        if strategy is None:
            raise NotFoundError("Strategy not found.")
        parent = self._versions.selected_version(strategy)
        if parent is None or parent.id != row.parent_version_id:
            raise ConflictError("Selected baseline changed; proposal requires a new review.")
        status = self.status(proposal_id, organization_id=organization_id, user_id=user_id)
        if status.blockers:
            raise ValidationAppError(
                "Promotion blocked by validation evidence.", details={"blockers": status.blockers}
            )
        if (
            status.comparison_hash != payload.expected_comparison_hash
            or status.paper_validation_run_id != payload.expected_paper_validation_run_id
        ):
            raise ConflictError("Approval does not match the reviewed validation evidence.")
        if status.explicit_evidence_review_required and not payload.evidence_review:
            raise ValidationAppError(
                "Insufficient or limited evidence requires explicit human evidence review."
            )
        with self._session.begin_nested():
            compiled = CompiledSetupService(self._session).compile_version(
                row.resulting_version_id, organization_id=organization_id, user_id=user_id
            )
            if compiled.compiled is None:
                raise ValidationAppError("Promotion requires an executable compiled version.")
            evidence: dict[str, object] = {
                "proposal_id": str(row.id),
                "proposal_content_hash": row.content_hash,
                "comparison_hash": status.comparison_hash,
                "baseline_run_id": str(status.baseline_run_id),
                "proposed_run_id": str(status.proposed_run_id),
                "paper_validation_run_id": str(status.paper_validation_run_id),
                "rollback_version_id": str(parent.id),
                "execution_scope": "paper_only",
                "explicit_human_approval": True,
                "evidence_review": payload.evidence_review,
                "insufficient_evidence": status.insufficient_evidence,
                "compiled_content_hash": compiled.compiled.content_hash,
                "validation_snapshot": status.model_dump(mode="json"),
                "historical_runs": [
                    {
                        "run_id": str(run.id),
                        "strategy_version_id": str(run.strategy_version_id),
                        "config_hash": run.config_hash,
                        "result_hash": run.result_hash,
                        "dataset_id": str(run.dataset_id),
                        "windows": (run.config_snapshot or {})["replay_request"]["windows"],
                    }
                    for identity in (status.baseline_run_id, status.proposed_run_id)
                    if (run := self._session.get(BacktestRun, identity)) is not None
                ],
                "paper_metrics": self._paper(row).metrics,
            }
            self._versions.append_lifecycle(
                organization_id=organization_id,
                strategy_id=strategy.id,
                strategy_version_id=row.resulting_version_id,
                new_state=StrategyLifecycleState.APPROVED,
                actor_user_id=user_id,
                reason="governed human approval",
                evidence_snapshot=evidence,
            )
            version = self._session.get(UserStrategyVersion, row.resulting_version_id)
            if version is None:
                raise NotFoundError("Immutable candidate version not found.")
            strategy.current_version = version.version
            event = self._versions.append_lifecycle(
                organization_id=organization_id,
                strategy_id=strategy.id,
                strategy_version_id=version.id,
                new_state=StrategyLifecycleState.ACTIVE,
                actor_user_id=user_id,
                reason="governed paper promotion",
                evidence_snapshot=evidence,
            )
            return StrategyLifecycleEventRecord.model_validate(event, from_attributes=True)

    def rollback(
        self,
        strategy_id: UUID,
        payload: LearningRollbackApproval,
        *,
        organization_id: UUID,
        user_id: UUID,
    ) -> StrategyLifecycleEventRecord:
        from app.interactive_agent.action_registry import require_action_permission
        from app.services.canonical_strategy_evaluation import resolve_executable_strategy_policy

        require_action_permission(self._session, organization_id=organization_id, user_id=user_id)
        if payload.execution_mode != "paper" or payload.confirm != "ROLLBACK_PAPER_STRATEGY":
            raise TradingPolicyError("Rollback can select paper strategy versions only.")
        self._versions.require_strategy(
            strategy_id, organization_id=organization_id, user_id=user_id
        )
        strategy = self._session.scalar(
            select(UserStrategy).where(UserStrategy.id == strategy_id).with_for_update()
        )
        if strategy is None:
            raise NotFoundError("Strategy not found.")
        selected = self._versions.selected_version(strategy)
        if selected is None or selected.id != payload.expected_active_version_id:
            raise ConflictError("Paper active version changed before rollback.")
        event = self._versions.latest_lifecycle_event_for_version(selected.id)
        if event is None or event.evidence_snapshot.get("rollback_version_id") != str(
            payload.target_version_id
        ):
            raise ValidationAppError("Target is not the stored rollback relationship.")
        target = self._session.get(UserStrategyVersion, payload.target_version_id)
        if target is None or target.strategy_id != strategy.id:
            raise NotFoundError("Rollback version not found.")
        resolve_executable_strategy_policy(
            self._session,
            organization_id=organization_id,
            user_id=user_id,
            strategy_version_id=target.id,
        )
        strategy.current_version = target.version
        result = self._versions.append_lifecycle(
            organization_id=organization_id,
            strategy_id=strategy.id,
            strategy_version_id=target.id,
            new_state=StrategyLifecycleState.ACTIVE,
            actor_user_id=user_id,
            reason="governed paper rollback",
            evidence_snapshot={
                "rolled_back_from_version_id": str(selected.id),
                "execution_scope": "paper_only",
                "explicit_human_approval": True,
                "reason": payload.reason,
            },
        )
        return StrategyLifecycleEventRecord.model_validate(result, from_attributes=True)


@dataclass(frozen=True)
class PromotionDecision:
    recommendation: BacktestRecommendation
    backtest_status: BacktestStatus
    validation_status: StrategyValidationStatus | None
    paper_eligible: bool
    limitations: list[str]


def evaluate_promotion(
    *,
    metrics: BacktestMetrics,
    machine_readable: bool,
    data_quality: str,
    meets_success_criteria: bool,
) -> PromotionDecision:
    limitations: list[str] = []

    if not machine_readable:
        return PromotionDecision(
            recommendation=BacktestRecommendation.NEEDS_STRUCTURED_RULES,
            backtest_status=BacktestStatus.FAILED,
            validation_status=None,
            paper_eligible=False,
            limitations=["Rules could not be evaluated mechanically."],
        )

    if data_quality != "ok":
        return PromotionDecision(
            recommendation=BacktestRecommendation.UNRELIABLE_DATA,
            backtest_status=BacktestStatus.FAILED,
            validation_status=None,
            paper_eligible=False,
            limitations=["Historical data incomplete or stale — result unreliable."],
        )

    if metrics.trade_count < MIN_SAMPLE_SIZE:
        limitations.append(
            f"Sample size {metrics.trade_count} below minimum {MIN_SAMPLE_SIZE} — "
            "statistical confidence is low."
        )
        return PromotionDecision(
            recommendation=BacktestRecommendation.NEEDS_MORE_SAMPLE,
            backtest_status=BacktestStatus.COMPLETED,
            validation_status=StrategyValidationStatus.IN_REVIEW,
            paper_eligible=False,
            limitations=limitations,
        )

    if metrics.expectancy <= 0:
        limitations.append("Negative or zero expectancy — not paper eligible.")
        return PromotionDecision(
            recommendation=BacktestRecommendation.RESTRICTED,
            backtest_status=BacktestStatus.COMPLETED,
            validation_status=StrategyValidationStatus.RESTRICTED,
            paper_eligible=False,
            limitations=limitations,
        )

    if metrics.profit_factor < MIN_PROFIT_FACTOR:
        limitations.append(
            f"Profit factor {metrics.profit_factor:.2f} below threshold {MIN_PROFIT_FACTOR}."
        )
        return PromotionDecision(
            recommendation=BacktestRecommendation.NEEDS_REVIEW,
            backtest_status=BacktestStatus.COMPLETED,
            validation_status=StrategyValidationStatus.IN_REVIEW,
            paper_eligible=False,
            limitations=limitations,
        )

    if metrics.max_drawdown_pct > MAX_DRAWDOWN_PCT:
        limitations.append(
            f"Max drawdown {metrics.max_drawdown_pct:.1f}% exceeds {MAX_DRAWDOWN_PCT}% threshold."
        )
        return PromotionDecision(
            recommendation=BacktestRecommendation.RESTRICTED,
            backtest_status=BacktestStatus.COMPLETED,
            validation_status=StrategyValidationStatus.RESTRICTED,
            paper_eligible=False,
            limitations=limitations,
        )

    if metrics.largest_loss < 0 and abs(metrics.largest_loss) > Decimal("1000"):
        limitations.append("Large single-trade loss detected — review sizing rules.")

    if metrics.trade_count < PREFERRED_SAMPLE_SIZE:
        limitations.append(
            f"Sample size {metrics.trade_count} below preferred {PREFERRED_SAMPLE_SIZE}."
        )
        return PromotionDecision(
            recommendation=BacktestRecommendation.NEEDS_REVIEW,
            backtest_status=BacktestStatus.COMPLETED,
            validation_status=StrategyValidationStatus.IN_REVIEW,
            paper_eligible=False,
            limitations=limitations,
        )

    if meets_success_criteria and metrics.profit_factor >= MIN_PROFIT_FACTOR:
        return PromotionDecision(
            recommendation=BacktestRecommendation.PAPER_ELIGIBLE,
            backtest_status=BacktestStatus.COMPLETED,
            validation_status=StrategyValidationStatus.IN_REVIEW,
            paper_eligible=True,
            limitations=limitations
            or ["Paper eligible — requires paper validation before any live consideration."],
        )

    return PromotionDecision(
        recommendation=BacktestRecommendation.BACKTESTED,
        backtest_status=BacktestStatus.COMPLETED,
        validation_status=StrategyValidationStatus.IN_REVIEW,
        paper_eligible=False,
        limitations=limitations or ["Backtest completed — manual review recommended."],
    )

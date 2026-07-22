"""Paper validation draft service (Slice 78-79 - draft/prep only, no execution)."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationAppError
from app.db.models import PaperValidationAlert as AlertModel
from app.db.models import PaperValidationDraft as DraftModel
from app.repositories.paper_scheduler import PaperAlertRepository
from app.repositories.paper_validation_draft import PaperValidationDraftRepository
from app.schemas.audit import AuditRecordCreate
from app.schemas.common import (
    ActorType,
    AuditEventType,
    AuditResult,
    AuditSeverity,
    PaperValidationDraftPrepStatus,
    PaperValidationDraftRiskMode,
    PaperValidationDraftStatus,
    SetupAlertReviewStatus,
)
from app.schemas.paper_validation_draft import (
    CREATE_PAPER_VALIDATION_DRAFT_CONFIRM,
    PREP_CHECKLIST_KEYS,
    PaginatedPaperValidationDrafts,
    PaperValidationDraftChecklist,
    PaperValidationDraftItem,
    PaperValidationDraftPrepUpdateRequest,
    PaperValidationDraftSummary,
    SetupAlertDraftCreateRequest,
    SetupAlertDraftCreateResult,
)
from app.services.audit_service import AuditService

_DRAFTABLE_REVIEW_STATUSES = {
    SetupAlertReviewStatus.WATCHING,
    SetupAlertReviewStatus.IMPORTANT,
}


class PaperValidationDraftService:
    """Create and read non-executable paper validation drafts from setup alerts."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._alerts = PaperAlertRepository(session)
        self._drafts = PaperValidationDraftRepository(session)
        self._audit = AuditService(session)

    def create_from_setup_alert(
        self,
        alert_id: uuid.UUID,
        payload: SetupAlertDraftCreateRequest,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> SetupAlertDraftCreateResult:
        if payload.confirm != CREATE_PAPER_VALIDATION_DRAFT_CONFIRM:
            self._record_audit(
                "setup_alert_draft_blocked",
                alert_id=alert_id,
                organization_id=organization_id,
                user_id=user_id,
                metadata={"reason": "confirmation_required"},
                durable=True,
            )
            raise ValidationAppError(
                "Exact confirmation required to create a paper validation draft.",
                details={"required_confirm": CREATE_PAPER_VALIDATION_DRAFT_CONFIRM},
            )

        self._record_audit(
            "setup_alert_draft_requested",
            alert_id=alert_id,
            organization_id=organization_id,
            user_id=user_id,
            metadata={
                "risk_mode": payload.risk_mode.value,
                "has_notes": bool(payload.notes),
            },
        )

        row = self._alerts.get_setup_review_alert(alert_id, organization_id=organization_id)
        if row is None:
            from sqlalchemy import select

            generic = self._session.scalar(
                select(AlertModel).where(
                    AlertModel.id == alert_id,
                    AlertModel.organization_id == organization_id,
                )
            )
            if generic is not None:
                self._record_audit(
                    "setup_alert_draft_blocked",
                    alert_id=alert_id,
                    organization_id=organization_id,
                    user_id=user_id,
                    metadata={"reason": "non_market_watcher_alert"},
                    durable=True,
                )
                raise ValidationAppError(
                    "Only scanner-created setup alerts can be converted to drafts.",
                    details={"alert_id": str(alert_id)},
                )
            raise NotFoundError("Alert not found.")

        try:
            review_status = SetupAlertReviewStatus(row.review_status)
        except ValueError:
            review_status = SetupAlertReviewStatus.UNREVIEWED

        if review_status not in _DRAFTABLE_REVIEW_STATUSES:
            self._record_audit(
                "setup_alert_draft_blocked",
                alert_id=alert_id,
                organization_id=organization_id,
                user_id=user_id,
                metadata={
                    "reason": "review_status_not_draftable",
                    "review_status": review_status.value,
                },
                durable=True,
            )
            raise ValidationAppError(
                "Only watching or important setup alerts can be converted to drafts.",
                details={
                    "alert_id": str(alert_id),
                    "review_status": review_status.value,
                },
            )

        existing = self._drafts.get_active_for_alert(organization_id, alert_id)
        if existing is not None:
            self._record_audit(
                "setup_alert_draft_already_exists",
                alert_id=alert_id,
                organization_id=organization_id,
                user_id=user_id,
                metadata={"draft_id": str(existing.id)},
            )
            return SetupAlertDraftCreateResult(
                draft=self._to_item(existing),
                already_exists=True,
            )

        draft = self._build_draft(row, payload, organization_id=organization_id, user_id=user_id)
        self._drafts.add(draft)
        self._record_audit(
            "setup_alert_draft_created",
            alert_id=alert_id,
            organization_id=organization_id,
            user_id=user_id,
            metadata={
                "draft_id": str(draft.id),
                "risk_mode": payload.risk_mode.value,
                "review_status": review_status.value,
            },
        )
        return SetupAlertDraftCreateResult(draft=self._to_item(draft), already_exists=False)

    def update_prep(
        self,
        draft_id: uuid.UUID,
        payload: PaperValidationDraftPrepUpdateRequest,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> PaperValidationDraftItem:
        row = self._drafts.get_for_org(draft_id, organization_id=organization_id)
        if row is None:
            raise NotFoundError("Draft not found.")

        if row.status != PaperValidationDraftStatus.DRAFT.value:
            self._record_prep_audit(
                "paper_draft_prep_blocked",
                draft_id=draft_id,
                source_alert_id=row.source_alert_id,
                organization_id=organization_id,
                user_id=user_id,
                metadata={"reason": "draft_not_editable", "status": row.status},
                durable=True,
            )
            raise ValidationAppError(
                "Only active drafts can receive prep updates.",
                details={"draft_id": str(draft_id), "status": row.status},
            )

        if payload.prep_status is not None:
            row.prep_status = payload.prep_status.value
        if payload.thesis is not None:
            row.thesis = payload.thesis
        if payload.entry_criteria is not None:
            row.entry_criteria = payload.entry_criteria
        if payload.invalidation_criteria is not None:
            row.invalidation_criteria = payload.invalidation_criteria
        if payload.risk_notes is not None:
            row.risk_notes = payload.risk_notes
        if payload.checklist is not None:
            row.checklist_status = payload.checklist.model_dump()

        item = self._to_item(row)
        audit_metadata = self._prep_audit_metadata(item)
        self._record_prep_audit(
            "paper_draft_prep_updated",
            draft_id=draft_id,
            source_alert_id=row.source_alert_id,
            organization_id=organization_id,
            user_id=user_id,
            metadata=audit_metadata,
        )
        if item.is_ready_for_validation:
            self._record_prep_audit(
                "paper_draft_marked_ready",
                draft_id=draft_id,
                source_alert_id=row.source_alert_id,
                organization_id=organization_id,
                user_id=user_id,
                metadata=audit_metadata,
            )
        return item

    def list_drafts(
        self,
        organization_id: uuid.UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedPaperValidationDrafts:
        rows, total = self._drafts.list_for_org(
            organization_id,
            status=PaperValidationDraftStatus.DRAFT,
            limit=limit,
            offset=offset,
        )
        return PaginatedPaperValidationDrafts(
            items=[self._to_item(row) for row in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    def get_draft(
        self,
        draft_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
    ) -> PaperValidationDraftItem:
        row = self._drafts.get_for_org(draft_id, organization_id=organization_id)
        if row is None:
            raise NotFoundError("Draft not found.")
        return self._to_item(row)

    def draft_summary(self, organization_id: uuid.UUID) -> PaperValidationDraftSummary:
        rows, total = self._drafts.list_for_org(
            organization_id,
            status=PaperValidationDraftStatus.DRAFT,
            limit=500,
            offset=0,
        )
        latest = self._drafts.latest_for_org(organization_id)
        ready_count = sum(1 for row in rows if self._to_item(row).is_ready_for_validation)
        return PaperValidationDraftSummary(
            total_drafts=total,
            latest_condition=latest.condition if latest is not None else None,
            latest_created_at=latest.created_at if latest is not None else None,
            ready_for_validation_count=ready_count,
        )

    @staticmethod
    def _build_draft(
        alert: AlertModel,
        payload: SetupAlertDraftCreateRequest,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
    ) -> DraftModel:
        meta = alert.metadata_json or {}
        metrics = meta.get("metrics") if isinstance(meta.get("metrics"), dict) else {}
        latest_price = metrics.get("latest_price")
        if latest_price is None:
            latest_price = meta.get("latest_price")
        confidence = meta.get("confidence")
        trigger_level = meta.get("trigger_level")
        invalidation_level = meta.get("invalidation_level")
        return DraftModel(
            organization_id=organization_id,
            source_alert_id=alert.id,
            symbol=meta.get("symbol") if isinstance(meta.get("symbol"), str) else None,
            timeframe=meta.get("timeframe") if isinstance(meta.get("timeframe"), str) else None,
            condition=meta.get("condition") if isinstance(meta.get("condition"), str) else None,
            direction=meta.get("direction") if isinstance(meta.get("direction"), str) else None,
            confidence=float(confidence) if isinstance(confidence, (int, float)) else None,
            reason=meta.get("reason") if isinstance(meta.get("reason"), str) else None,
            trigger_level=float(trigger_level) if isinstance(trigger_level, (int, float)) else None,
            invalidation_level=(
                float(invalidation_level) if isinstance(invalidation_level, (int, float)) else None
            ),
            latest_price=float(latest_price) if isinstance(latest_price, (int, float)) else None,
            review_status=alert.review_status,
            user_notes=payload.notes,
            risk_mode=payload.risk_mode.value,
            status=PaperValidationDraftStatus.DRAFT.value,
            created_by=user_id,
            prep_status=PaperValidationDraftPrepStatus.DRAFT.value,
        )

    @classmethod
    def _parse_checklist(cls, raw: dict[str, object] | None) -> PaperValidationDraftChecklist:
        values: dict[str, bool] = {}
        if isinstance(raw, dict):
            for key in PREP_CHECKLIST_KEYS:
                value = raw.get(key)
                if isinstance(value, bool):
                    values[key] = value
        return PaperValidationDraftChecklist(**values)

    @classmethod
    def _compute_readiness(
        cls,
        *,
        prep_status: str,
        thesis: str | None,
        entry_criteria: str | None,
        invalidation_criteria: str | None,
        checklist: PaperValidationDraftChecklist,
    ) -> tuple[int, list[str], bool]:
        missing_checklist = [
            key for key in PREP_CHECKLIST_KEYS if not getattr(checklist, key, False)
        ]
        score_items = [
            bool(thesis and thesis.strip()),
            bool(entry_criteria and entry_criteria.strip()),
            bool(invalidation_criteria and invalidation_criteria.strip()),
        ] + [getattr(checklist, key, False) for key in PREP_CHECKLIST_KEYS]
        score = round(sum(score_items) / len(score_items) * 100)

        try:
            prep = PaperValidationDraftPrepStatus(prep_status)
        except ValueError:
            prep = PaperValidationDraftPrepStatus.DRAFT

        is_ready = (
            prep == PaperValidationDraftPrepStatus.READY_FOR_VALIDATION
            and bool(thesis and thesis.strip())
            and bool(entry_criteria and entry_criteria.strip())
            and bool(invalidation_criteria and invalidation_criteria.strip())
            and checklist.invalidation_checked
            and checklist.risk_reward_checked
            and checklist.higher_timeframe_checked
        )
        return score, missing_checklist, is_ready

    @classmethod
    def _to_item(cls, row: DraftModel) -> PaperValidationDraftItem:
        try:
            risk_mode = PaperValidationDraftRiskMode(row.risk_mode)
        except ValueError:
            risk_mode = PaperValidationDraftRiskMode.CONSERVATIVE
        try:
            status = PaperValidationDraftStatus(row.status)
        except ValueError:
            status = PaperValidationDraftStatus.DRAFT
        try:
            prep_status = PaperValidationDraftPrepStatus(row.prep_status)
        except ValueError:
            prep_status = PaperValidationDraftPrepStatus.DRAFT

        checklist = cls._parse_checklist(row.checklist_status)
        score, missing_checklist, is_ready = cls._compute_readiness(
            prep_status=prep_status.value,
            thesis=row.thesis,
            entry_criteria=row.entry_criteria,
            invalidation_criteria=row.invalidation_criteria,
            checklist=checklist,
        )
        return PaperValidationDraftItem(
            draft_id=row.id,
            source_alert_id=row.source_alert_id,
            symbol=row.symbol,
            timeframe=row.timeframe,
            condition=row.condition,
            direction=row.direction,
            confidence=row.confidence,
            trigger_level=row.trigger_level,
            invalidation_level=row.invalidation_level,
            latest_price=row.latest_price,
            reason=row.reason,
            risk_mode=risk_mode,
            status=status,
            created_at=row.created_at,
            created_by=row.created_by,
            thesis=row.thesis,
            entry_criteria=row.entry_criteria,
            invalidation_criteria=row.invalidation_criteria,
            risk_notes=row.risk_notes,
            prep_status=prep_status,
            checklist=checklist,
            prep_completion_score=score,
            missing_checklist_items=missing_checklist,
            is_ready_for_validation=is_ready,
        )

    @staticmethod
    def _prep_audit_metadata(item: PaperValidationDraftItem) -> dict[str, object]:
        return {
            "draft_id": str(item.draft_id),
            "prep_status": item.prep_status.value,
            "prep_completion_score": item.prep_completion_score,
            "is_ready_for_validation": item.is_ready_for_validation,
            "missing_checklist_count": len(item.missing_checklist_items),
            "has_thesis": bool(item.thesis and item.thesis.strip()),
            "has_entry_criteria": bool(item.entry_criteria and item.entry_criteria.strip()),
            "has_invalidation_criteria": bool(
                item.invalidation_criteria and item.invalidation_criteria.strip()
            ),
            "has_risk_notes": bool(item.risk_notes and item.risk_notes.strip()),
        }

    def _record_audit(
        self,
        action: str,
        *,
        alert_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
        metadata: dict[str, object] | None = None,
        durable: bool = False,
    ) -> None:
        payload = AuditRecordCreate(
            request_id=f"setup-alert-draft-{alert_id}",
            trace_id=str(uuid.uuid4()),
            user_id=user_id,
            organization_id=organization_id,
            event_type=AuditEventType.PAPER_VALIDATION_RUNTIME,
            resource_type="paper_validation_draft",
            resource_id=str(alert_id),
            actor_type=ActorType.USER,
            result=AuditResult.SUCCESS,
            severity=AuditSeverity.INFO,
            metadata={"action": action, **(metadata or {})},
        )
        if durable:
            self._audit.record_durable_isolated(payload)
        else:
            self._audit.record(payload)

    def _record_prep_audit(
        self,
        action: str,
        *,
        draft_id: uuid.UUID,
        source_alert_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
        metadata: dict[str, object] | None = None,
        durable: bool = False,
    ) -> None:
        payload = AuditRecordCreate(
            request_id=f"paper-draft-prep-{draft_id}",
            trace_id=str(uuid.uuid4()),
            user_id=user_id,
            organization_id=organization_id,
            event_type=AuditEventType.PAPER_VALIDATION_RUNTIME,
            resource_type="paper_validation_draft",
            resource_id=str(draft_id),
            actor_type=ActorType.USER,
            result=AuditResult.SUCCESS,
            severity=AuditSeverity.INFO,
            metadata={
                "action": action,
                "source_alert_id": str(source_alert_id),
                **(metadata or {}),
            },
        )
        if durable:
            self._audit.record_durable_isolated(payload)
        else:
            self._audit.record(payload)

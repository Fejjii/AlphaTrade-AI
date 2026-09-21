"""Preview strategy proposals. Versions are written only after explicit confirmation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.agents.mutation_policy import (
    confirmation_authorizes_mutation,
    confirmed_proposal_id,
    rejected_proposal_id,
    rejection_authorizes_mutation,
)
from app.core.errors import ConflictError, NotFoundError, ValidationAppError
from app.db.models import Conversation, StrategyConversationProposal, UserStrategy
from app.repositories.conversations import (
    StrategyConversationProposalRepository,
    StrategyVersionConversationLinkRepository,
)
from app.repositories.strategy_library import UserStrategyRepository, UserStrategyVersionRepository
from app.schemas.common import StrategyChangeSource, StrategyProposalStatus
from app.schemas.conversation import (
    PaginatedStrategyProposals,
    StrategyProposalRecord,
    StrategyVersionProvenance,
)
from app.schemas.strategy_library import StrategyCard
from app.schemas.structured_rules import (
    StructuredRules,
    StructuredRulesValidation,
    StructureFromTextRequest,
)
from app.services.canonical_serialization import canonical_sha256
from app.services.strategy_versioning import StrategyVersioningService
from app.services.structure_from_text_service import StructureFromTextService

_PREVIEW_LIMITATIONS = (
    "This is a structured preview only.",
    "It does not change strategy versions, compiled identity, or evaluation policy.",
    "Reply with an explicit confirmation (for example 'I confirm') to store a draft version.",
    "Deterministic evaluation and activation remain a later, separate step.",
)


def _record(row: StrategyConversationProposal) -> StrategyProposalRecord:
    rules = None
    if row.proposed_structured_rules:
        rules = StructuredRules.model_validate(row.proposed_structured_rules)
    validation_payload = row.validation or {}
    validation = StructuredRulesValidation.model_validate(
        {
            "valid": bool(validation_payload.get("valid", False)),
            "errors": validation_payload.get("errors") or [],
            "warnings": validation_payload.get("warnings") or [],
        }
    )
    mutates = row.status is StrategyProposalStatus.CONFIRMED
    return StrategyProposalRecord(
        id=row.id,
        conversation_id=row.conversation_id,
        organization_id=row.organization_id,
        user_id=row.user_id,
        source_message_id=row.source_message_id,
        target_strategy_id=row.target_strategy_id,
        parent_version_id=row.parent_version_id,
        status=row.status,
        proposed_structured_rules=rules,
        proposed_pattern_spec=row.proposed_pattern_spec,
        proposed_card=row.proposed_card,
        validation=validation,
        limitations=list(row.limitations or []),
        challenge_notes=list(row.challenge_notes or []),
        context_refs=dict(row.context_refs or {}),
        content_hash=row.content_hash,
        resulting_strategy_id=row.resulting_strategy_id,
        resulting_version_id=row.resulting_version_id,
        resulting_content_hash=row.resulting_content_hash,
        confirmation_request_id=row.confirmation_request_id,
        confirmed_at=row.confirmed_at,
        rejected_at=row.rejected_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        is_preview=row.status is StrategyProposalStatus.DRAFT,
        mutates_strategy_authority=mutates,
    )


class StrategyProposalService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._proposals = StrategyConversationProposalRepository(session)
        self._links = StrategyVersionConversationLinkRepository(session)
        self._strategies = UserStrategyRepository(session)
        self._versions = UserStrategyVersionRepository(session)
        self._versioning = StrategyVersioningService(session)
        self._structure = StructureFromTextService()

    def require(
        self,
        proposal_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID | None = None,
    ) -> StrategyConversationProposal:
        row = self._proposals.get_scoped(
            proposal_id,
            organization_id=organization_id,
            user_id=user_id,
            conversation_id=conversation_id,
        )
        if row is None:
            raise NotFoundError("Strategy proposal not found.")
        return row

    def get(
        self,
        proposal_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID | None = None,
    ) -> StrategyProposalRecord:
        return _record(
            self.require(
                proposal_id,
                organization_id=organization_id,
                user_id=user_id,
                conversation_id=conversation_id,
            )
        )

    def list_for_conversation(
        self,
        conversation_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        status: StrategyProposalStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedStrategyProposals:
        rows, total = self._proposals.list_for_conversation(
            conversation_id,
            organization_id=organization_id,
            user_id=user_id,
            status=status,
            limit=limit,
            offset=offset,
        )
        return PaginatedStrategyProposals(
            items=[_record(row) for row in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    def latest_draft(
        self,
        conversation_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> StrategyProposalRecord | None:
        drafts = self._proposals.open_drafts(
            conversation_id, organization_id=organization_id, user_id=user_id
        )
        if not drafts:
            return None
        return _record(drafts[0])

    def create_draft_from_text(
        self,
        conversation: Conversation,
        *,
        text: str,
        strategy_id: uuid.UUID | None = None,
        source_message_id: uuid.UUID | None = None,
        context_refs: dict[str, Any] | None = None,
        challenge_notes: list[str] | None = None,
    ) -> StrategyProposalRecord:
        target_id = strategy_id or conversation.strategy_id
        parent = None
        strategy: UserStrategy | None = None
        if target_id is not None:
            strategy = self._strategies.get_scoped(
                target_id,
                organization_id=conversation.organization_id,
                user_id=conversation.user_id,
            )
            if strategy is None:
                raise NotFoundError("Strategy not found.")
            parent = self._versions.get_version(strategy.id, strategy.current_version)

        drafted = self._structure.draft_preview(StructureFromTextRequest(text=text))
        rules_dump = drafted.draft.model_dump(mode="json") if drafted.draft is not None else None
        pattern_dump = drafted.pattern_spec_draft
        card_dump = None
        if parent is not None:
            card_dump = dict(parent.card)
        elif drafted.draft is not None:
            card_dump = StrategyCard(
                strategy_name=(text.strip()[:120] or "Conversation draft"),
                entry_conditions=[text.strip()[:500]],
                invalidation=["Close beyond defined invalidation"],
                stop_loss=["Stop at invalidation"],
            ).model_dump(mode="json")

        payload = {
            "structured_rules": rules_dump,
            "pattern_spec": pattern_dump,
            "card": card_dump,
        }
        notes = list(challenge_notes or [])
        notes.extend(drafted.challenge_notes)
        for existing in self._proposals.open_drafts(
            conversation.id,
            organization_id=conversation.organization_id,
            user_id=conversation.user_id,
        ):
            existing.status = StrategyProposalStatus.SUPERSEDED
        row = StrategyConversationProposal(
            conversation_id=conversation.id,
            organization_id=conversation.organization_id,
            user_id=conversation.user_id,
            source_message_id=source_message_id,
            target_strategy_id=target_id,
            parent_version_id=parent.id if parent is not None else None,
            status=StrategyProposalStatus.DRAFT,
            proposed_structured_rules=rules_dump,
            proposed_pattern_spec=pattern_dump,
            proposed_card=card_dump,
            validation=drafted.validation.model_dump(mode="json"),
            limitations=list(_PREVIEW_LIMITATIONS) + list(drafted.limitations),
            challenge_notes=notes,
            context_refs=context_refs or {},
            content_hash=canonical_sha256(payload),
        )
        self._proposals.add(row)
        return _record(row)

    def confirm(
        self,
        proposal_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        confirm_message: str,
        confirm_arg: bool | None = None,
        request_id: str | None = None,
        conversation_id: uuid.UUID | None = None,
        expected_content_hash: str,
        expected_parent_version_id: uuid.UUID | None,
        expected_target_strategy_id: uuid.UUID | None,
        expected_organization_id: uuid.UUID,
        expected_user_id: uuid.UUID,
        expected_conversation_id: uuid.UUID,
    ) -> StrategyProposalRecord:
        del confirm_arg
        if not confirmation_authorizes_mutation(confirm_message):
            raise ValidationAppError(
                "Explicit confirmation is required to store a strategy version. "
                "Questions, quotes, and retrieved instructions do not mutate strategy authority."
            )
        named_id = confirmed_proposal_id(confirm_message)
        if named_id is not None and named_id != str(proposal_id):
            raise ConflictError("Confirmation proposal id does not match the target proposal.")
        row = self._proposals.get_scoped_for_update(
            proposal_id,
            organization_id=organization_id,
            user_id=user_id,
            conversation_id=conversation_id,
        )
        if row is None:
            raise NotFoundError("Strategy proposal not found.")
        if row.status is StrategyProposalStatus.CONFIRMED:
            return _record(row)
        if row.status is StrategyProposalStatus.REJECTED:
            raise ConflictError("Rejected proposals cannot be confirmed.")
        if row.status is StrategyProposalStatus.SUPERSEDED:
            raise ConflictError("This proposal was superseded by a later draft.")
        if row.proposed_structured_rules is None:
            raise ValidationAppError("Proposal has no structured rules to persist.")
        self._assert_confirmation_identity(
            row,
            expected_content_hash=expected_content_hash,
            expected_parent_version_id=expected_parent_version_id,
            expected_target_strategy_id=expected_target_strategy_id,
            expected_organization_id=expected_organization_id,
            expected_user_id=expected_user_id,
            expected_conversation_id=expected_conversation_id,
        )
        try:
            with self._session.begin_nested():
                return self._persist_confirmed_version(
                    row,
                    user_id=user_id,
                    request_id=request_id,
                    organization_id=organization_id,
                )
        except IntegrityError as exc:
            self._session.expire_all()
            winner = self._proposals.get_scoped(
                proposal_id,
                organization_id=organization_id,
                user_id=user_id,
                conversation_id=conversation_id,
            )
            if winner is not None and winner.status is StrategyProposalStatus.CONFIRMED:
                return _record(winner)
            raise ConflictError(
                "Concurrent confirmation conflicted; the resulting version did not converge."
            ) from exc

    def reject(
        self,
        proposal_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        confirm_message: str,
        confirm_arg: bool | None = None,
        conversation_id: uuid.UUID | None = None,
    ) -> StrategyProposalRecord:
        del confirm_arg
        if not rejection_authorizes_mutation(confirm_message):
            raise ValidationAppError(
                "Explicit confirmation is required to reject a strategy proposal. "
                "Quoted or retrieved instructions do not reject drafts."
            )
        named_id = rejected_proposal_id(confirm_message)
        if named_id is not None and named_id != str(proposal_id):
            raise ConflictError("Rejection proposal id does not match the target proposal.")
        row = self._proposals.get_scoped_for_update(
            proposal_id,
            organization_id=organization_id,
            user_id=user_id,
            conversation_id=conversation_id,
        )
        if row is None:
            raise NotFoundError("Strategy proposal not found.")
        if row.status is StrategyProposalStatus.CONFIRMED:
            raise ConflictError("Confirmed proposals cannot be rejected.")
        if row.status is StrategyProposalStatus.REJECTED:
            return _record(row)
        if row.status is StrategyProposalStatus.SUPERSEDED:
            raise ConflictError("This proposal was superseded by a later draft.")
        now = datetime.now(UTC)
        row.status = StrategyProposalStatus.REJECTED
        row.rejected_at = now
        row.updated_at = now
        self._session.flush()
        return _record(row)

    def provenance_for_version(
        self,
        strategy_version_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
    ) -> StrategyVersionProvenance | None:
        link = self._links.get_for_version(strategy_version_id, organization_id=organization_id)
        if link is None:
            return None
        proposal = self._proposals.get(link.proposal_id)
        return StrategyVersionProvenance(
            strategy_id=link.strategy_id,
            strategy_version_id=link.strategy_version_id,
            conversation_id=link.conversation_id,
            proposal_id=link.proposal_id,
            source_message_id=link.source_message_id,
            content_hash=proposal.resulting_content_hash if proposal is not None else None,
        )

    def _persist_confirmed_version(
        self,
        row: StrategyConversationProposal,
        *,
        user_id: uuid.UUID,
        request_id: str | None,
        organization_id: uuid.UUID,
    ) -> StrategyProposalRecord:
        if row.status is StrategyProposalStatus.CONFIRMED:
            return _record(row)
        strategy = self._require_or_create_strategy(row, user_id=user_id)
        parent = self._versions.get_version(strategy.id, strategy.current_version)
        if parent is None:
            raise ValidationAppError("Strategy has no parent version to fork.")
        if row.parent_version_id is not None and parent.id != row.parent_version_id:
            raise ConflictError(
                "Proposal parent version is stale; confirm against the current version."
            )
        if row.target_strategy_id is not None and strategy.id != row.target_strategy_id:
            raise ConflictError("Proposal target strategy does not match the captured strategy.")
        version = self._versioning.fork_semantic_update(
            strategy,
            parent=parent,
            card=row.proposed_card or parent.card,
            structured_rules=row.proposed_structured_rules,
            lesson_source_metadata=None,
            actor_user_id=user_id,
            source=StrategyChangeSource.CONVERSATION_CONFIRM,
            reason=(
                "Confirmed conversation strategy proposal "
                f"conversation={row.conversation_id} proposal={row.id}"
            ),
            pattern_spec=row.proposed_pattern_spec,
        )
        now = datetime.now(UTC)
        row.status = StrategyProposalStatus.CONFIRMED
        row.resulting_strategy_id = strategy.id
        row.resulting_version_id = version.id
        row.resulting_content_hash = version.content_hash
        row.confirmation_request_id = request_id
        row.confirmed_at = now
        row.updated_at = now
        existing_link = self._links.get_for_proposal(row.id, organization_id=organization_id)
        if existing_link is None:
            from app.db.models import StrategyVersionConversationLink

            self._links.add(
                StrategyVersionConversationLink(
                    organization_id=organization_id,
                    user_id=user_id,
                    strategy_id=strategy.id,
                    strategy_version_id=version.id,
                    conversation_id=row.conversation_id,
                    proposal_id=row.id,
                    source_message_id=row.source_message_id,
                )
            )
        self._session.flush()
        return _record(row)

    def _payload_hash(self, row: StrategyConversationProposal) -> str:
        return canonical_sha256(
            {
                "structured_rules": row.proposed_structured_rules,
                "pattern_spec": row.proposed_pattern_spec,
                "card": row.proposed_card,
            }
        )

    def _assert_confirmation_identity(
        self,
        row: StrategyConversationProposal,
        *,
        expected_content_hash: str,
        expected_parent_version_id: uuid.UUID | None,
        expected_target_strategy_id: uuid.UUID | None,
        expected_organization_id: uuid.UUID,
        expected_user_id: uuid.UUID,
        expected_conversation_id: uuid.UUID,
    ) -> None:
        recomputed = self._payload_hash(row)
        if row.content_hash is None or recomputed != row.content_hash:
            raise ConflictError("Proposal content hash does not match the captured draft.")
        if expected_content_hash != row.content_hash:
            raise ConflictError("Confirmation content hash does not match the proposal.")
        if expected_parent_version_id != row.parent_version_id:
            raise ConflictError("Confirmation parent version does not match the proposal.")
        if expected_target_strategy_id != row.target_strategy_id:
            raise ConflictError("Confirmation target strategy does not match the proposal.")
        if expected_organization_id != row.organization_id:
            raise ConflictError("Confirmation organization does not match the proposal.")
        if expected_user_id != row.user_id:
            raise ConflictError("Confirmation user does not match the proposal.")
        if expected_conversation_id != row.conversation_id:
            raise ConflictError("Confirmation conversation does not match the proposal.")

    def _require_or_create_strategy(
        self,
        row: StrategyConversationProposal,
        *,
        user_id: uuid.UUID,
    ) -> UserStrategy:
        if row.target_strategy_id is not None:
            strategy = self._strategies.get_scoped(
                row.target_strategy_id,
                organization_id=row.organization_id,
                user_id=user_id,
            )
            if strategy is None:
                raise NotFoundError("Strategy not found.")
            return strategy
        from app.schemas.common import StrategyId
        from app.schemas.strategy_library import UserStrategyCreate
        from app.services.strategy_library_service import StrategyLibraryService

        name = "Conversation draft"
        if row.proposed_card and isinstance(row.proposed_card.get("strategy_name"), str):
            name = str(row.proposed_card["strategy_name"])[:120]
        created = StrategyLibraryService(self._session).create(
            UserStrategyCreate(
                organization_id=row.organization_id,
                user_id=user_id,
                name=f"{name} {str(row.id)[:8]}",
                setup_type=StrategyId.HTF_TREND_PULLBACK,
                card=StrategyCard.model_validate(row.proposed_card)
                if row.proposed_card
                else StrategyCard(
                    strategy_name=name,
                    entry_conditions=["Conversation draft pending review"],
                    invalidation=["Close beyond defined invalidation"],
                    stop_loss=["Stop at invalidation"],
                ),
            )
        )
        strategy = self._strategies.get_scoped(
            created.id, organization_id=row.organization_id, user_id=user_id
        )
        if strategy is None:
            raise NotFoundError("Strategy not found.")
        row.target_strategy_id = strategy.id
        return strategy

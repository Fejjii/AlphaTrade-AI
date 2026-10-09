"""Authenticated private capture API. A receipt is returned after outer commit."""

from typing import Literal
from uuid import UUID

import structlog
from fastapi import APIRouter, Query
from sqlalchemy import select

from app.agent_capture.contracts import (
    CaptureRetry,
    Category,
    SavedEntriesPage,
    SavedEntry,
    SavedEntryUpdate,
)
from app.agent_capture.service import CaptureService
from app.agent_capture.store import entry_record, list_entries, require_entry, update_entry
from app.core.dependencies import SessionDep, SettingsDep
from app.db.models import ConversationMessage
from app.interactive_agent.contracts import (
    PAYLOAD_KEY,
    AgentTurnRequest,
    AgentTurnResult,
    TurnOperation,
)
from app.security.rbac import TraderDep

router = APIRouter(prefix="/agent/saved", tags=["agent"])
logger = structlog.get_logger(__name__)


def capture_result(
    session: SessionDep,
    settings: SettingsDep,
    organization_id: UUID,
    user_id: UUID,
    result: AgentTurnResult,
    request: AgentTurnRequest,
) -> None:
    if result.operation is TurnOperation.REFUSE or request.action is not None:
        return
    result.capture_source_message_id = result.user_message_id
    capture = None
    try:
        with session.begin_nested():
            capture = CaptureService(session, settings)
            entries, status, clarification = capture.capture(
                organization_id=organization_id,
                user_id=user_id,
                conversation_id=result.conversation_id,
                message_id=result.user_message_id,
                source_document_id=request.source_document_id,
            )
            result.saved_entries = entries
            result.capture_status = status
            result.capture_clarification = clarification
    except Exception as exc:
        logger.warning("agent_capture_failed", error=type(exc).__name__)
        result.saved_entries = []
        result.capture_status = "failed"
        result.capture_error = (
            "Your message is retained in this conversation. Capture could not be saved; "
            "retry when the provider or storage is available."
        )
    if capture is not None and capture.model.last_usage:
        result.model_usage.append(capture.model.last_usage)
    assistant = session.get(ConversationMessage, result.assistant_message_id)
    if assistant is not None:
        payload = dict(assistant.payload or {})
        detail = dict(payload.get(PAYLOAD_KEY) or {})
        detail["model_usage"] = result.model_usage
        detail["capture"] = {
            "saved_entries": [e.model_dump(mode="json") for e in result.saved_entries],
            "status": result.capture_status,
            "error": result.capture_error,
            "clarification": result.capture_clarification,
            "source_message_id": str(result.user_message_id),
            "model_usage": result.model_usage,
        }
        payload[PAYLOAD_KEY] = detail
        assistant.payload = payload


@router.get("", response_model=SavedEntriesPage)
async def saved_list(
    tenant: TraderDep,
    session: SessionDep,
    category: Category | None = None,
    view: Literal["journal", "knowledge"] | None = None,
    q: str = Query(default="", max_length=200),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> SavedEntriesPage:
    return list_entries(
        session,
        tenant.organization_id,
        tenant.user_id,
        category=category,
        view=view,
        q=q,
        limit=limit,
        offset=offset,
    )


@router.post("/retry", response_model=SavedEntriesPage)
async def retry_capture(
    body: CaptureRetry, tenant: TraderDep, session: SessionDep, settings: SettingsDep
) -> SavedEntriesPage:
    from app.core.errors import NotFoundError

    message = session.scalar(
        select(ConversationMessage).where(
            ConversationMessage.id == body.source_message_id,
            ConversationMessage.conversation_id == body.conversation_id,
            ConversationMessage.organization_id == tenant.organization_id,
            ConversationMessage.user_id == tenant.user_id,
        )
    )
    if message is None:
        raise NotFoundError("Source message not found.")
    source = (message.payload.get(PAYLOAD_KEY) or {}).get("source_document_id")
    entries, status, clarification = CaptureService(session, settings).capture(
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        conversation_id=body.conversation_id,
        message_id=body.source_message_id,
        source_document_id=UUID(source) if source else None,
    )
    if status == "clarification":
        from app.core.errors import ValidationAppError

        raise ValidationAppError(clarification or "Capture needs clarification.")
    for assistant in session.scalars(
        select(ConversationMessage).where(
            ConversationMessage.conversation_id == body.conversation_id,
            ConversationMessage.organization_id == tenant.organization_id,
            ConversationMessage.user_id == tenant.user_id,
        )
    ):
        payload = dict(assistant.payload or {})
        detail = dict(payload.get(PAYLOAD_KEY) or {})
        receipt = detail.get("capture") or {}
        if receipt.get("source_message_id") == str(body.source_message_id):
            detail["capture"] = {
                **receipt,
                "saved_entries": [e.model_dump(mode="json") for e in entries],
                "status": status,
                "error": None,
                "clarification": None,
            }
            payload[PAYLOAD_KEY] = detail
            assistant.payload = payload
    session.commit()
    return SavedEntriesPage(items=entries, total=len(entries))


@router.get("/{entry_id}", response_model=SavedEntry)
async def saved_get(entry_id: UUID, tenant: TraderDep, session: SessionDep) -> SavedEntry:
    return entry_record(require_entry(session, entry_id, tenant.organization_id, tenant.user_id))


@router.patch("/{entry_id}", response_model=SavedEntry)
async def saved_update(
    entry_id: UUID, body: SavedEntryUpdate, tenant: TraderDep, session: SessionDep
) -> SavedEntry:
    result = update_entry(session, entry_id, body, tenant.organization_id, tenant.user_id)
    session.commit()
    return result

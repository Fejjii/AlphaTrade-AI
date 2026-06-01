"""AI trading workspace chat API — LangGraph agent orchestration."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request

from app.core.dependencies import SessionDep
from app.schemas.chat import AgentMessageResponse, ChatMessageRequest
from app.security.quota_enforcement import require_quota
from app.security.rate_limit import tenant_rate_limit_dependency
from app.security.rbac import TraderDep
from app.services.agent_service import AgentInvokeContext, build_agent_service

router = APIRouter(prefix="/chat", tags=["chat"])

_CHAT_RATE_LIMIT = Depends(
    tenant_rate_limit_dependency(
        "chat:message",
        limit=60,
        window_seconds=3600,
        ip_limit=120,
        user_limit=60,
    )
)
_CHAT_QUOTA = require_quota("agent_chat")


@router.post(
    "/message",
    response_model=AgentMessageResponse,
    summary="Send chat message",
    dependencies=[_CHAT_RATE_LIMIT, _CHAT_QUOTA],
)
async def send_message(
    body: ChatMessageRequest,
    request: Request,
    tenant: TraderDep,
    session: SessionDep,
) -> AgentMessageResponse:
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    conv_id = uuid.UUID(body.conversation_id) if body.conversation_id else None

    service = build_agent_service(session=session)
    return service.run(
        body.message,
        AgentInvokeContext(
            request_id=request_id,
            user_id=tenant.user_id,
            organization_id=tenant.organization_id,
            conversation_id=conv_id,
        ),
        symbol=body.symbol,
        timeframe=body.timeframe,
    )

"""Interactive agent API. Turns propose. Confirm is a separate request.

Screenshot and voice routes return the unimplemented contract. They do not
accept image or audio bytes.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.core.dependencies import SessionDep, SettingsDep
from app.evidence_pipeline.service import CanonicalEvidenceService
from app.interactive_agent.canonical_market import CanonicalPerpetualQuoteReader
from app.interactive_agent.contracts import (
    AgentCapabilityCatalog,
    AgentTurnRequest,
    AgentTurnResult,
    ProposalDecisionRequest,
    ScreenshotAnalysisContract,
    ScreenshotAnalysisRequest,
    StructuredActionProposal,
    VoiceInputRequest,
    VoiceIoContract,
    VoiceOutputRequest,
)
from app.interactive_agent.conversation import ModelConversationalResponder
from app.interactive_agent.service import InteractiveAgentService
from app.security.rbac import TraderDep

router = APIRouter(prefix="/agent", tags=["agent"])


def _service(
    session: SessionDep,
    settings: SettingsDep,
    organization_id: uuid.UUID,
) -> InteractiveAgentService:
    """Wire canonical evidence and the existing model. Neither path confirms."""
    return InteractiveAgentService(
        session,
        settings=settings,
        market_reader=CanonicalPerpetualQuoteReader(
            CanonicalEvidenceService(settings, session=session),
            organization_id,
        ),
        responder=ModelConversationalResponder(session, settings),
    )


@router.get("/capabilities", response_model=AgentCapabilityCatalog, summary="Agent capabilities")
async def agent_capabilities(
    tenant: TraderDep,
    session: SessionDep,
    settings: SettingsDep,
) -> AgentCapabilityCatalog:
    del tenant
    return InteractiveAgentService(session, settings=settings).catalog()


@router.post("/turns", response_model=AgentTurnResult, summary="Run one agent turn")
async def agent_turn(
    body: AgentTurnRequest,
    tenant: TraderDep,
    session: SessionDep,
    settings: SettingsDep,
) -> AgentTurnResult:
    result = _service(session, settings, tenant.organization_id).handle_turn(
        body,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
    )
    session.commit()
    return result


@router.post(
    "/proposals/{proposal_id}/confirm",
    response_model=StructuredActionProposal,
    summary="Confirm one structured agent proposal",
)
async def confirm_agent_proposal(
    proposal_id: uuid.UUID,
    body: ProposalDecisionRequest,
    tenant: TraderDep,
    session: SessionDep,
    settings: SettingsDep,
) -> StructuredActionProposal:
    result = _service(session, settings, tenant.organization_id).confirm(
        proposal_id,
        body,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
    )
    session.commit()
    return result


@router.post(
    "/proposals/{proposal_id}/reject",
    response_model=StructuredActionProposal,
    summary="Reject one structured agent proposal",
)
async def reject_agent_proposal(
    proposal_id: uuid.UUID,
    body: ProposalDecisionRequest,
    tenant: TraderDep,
    session: SessionDep,
    settings: SettingsDep,
) -> StructuredActionProposal:
    result = _service(session, settings, tenant.organization_id).reject(
        proposal_id,
        body,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
    )
    session.commit()
    return result


@router.post(
    "/screenshots/analyze",
    response_model=ScreenshotAnalysisContract,
    summary="Screenshot analysis contract",
)
async def analyze_screenshot(
    body: ScreenshotAnalysisRequest,
    tenant: TraderDep,
    session: SessionDep,
    settings: SettingsDep,
) -> ScreenshotAnalysisContract:
    result = _service(session, settings, tenant.organization_id).screenshot_contract(
        body,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
    )
    session.commit()
    return result


@router.post(
    "/voice/transcribe",
    response_model=VoiceIoContract,
    summary="Voice input contract",
)
async def transcribe_voice(
    body: VoiceInputRequest,
    tenant: TraderDep,
    session: SessionDep,
    settings: SettingsDep,
) -> VoiceIoContract:
    result = _service(session, settings, tenant.organization_id).voice_input_contract(
        body,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
    )
    session.commit()
    return result


@router.post("/voice/speak", response_model=VoiceIoContract, summary="Voice output contract")
async def speak_voice(
    body: VoiceOutputRequest,
    tenant: TraderDep,
    session: SessionDep,
    settings: SettingsDep,
) -> VoiceIoContract:
    result = _service(session, settings, tenant.organization_id).voice_output_contract(
        body,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
    )
    session.commit()
    return result

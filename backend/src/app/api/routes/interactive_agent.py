"""Interactive agent API. Turns propose. Confirm is a separate request.

Screenshot and voice routes return the unimplemented contract. They do not
accept image or audio bytes.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.core.dependencies import MarketDataServiceDep, SessionDep, SettingsDep
from app.interactive_agent.contracts import (
    AgentCapabilityCatalog,
    AgentTurnRequest,
    AgentTurnResult,
    MarketQuoteView,
    ProposalDecisionRequest,
    ScreenshotAnalysisContract,
    ScreenshotAnalysisRequest,
    StructuredActionProposal,
    VoiceInputRequest,
    VoiceIoContract,
    VoiceOutputRequest,
)
from app.interactive_agent.service import InteractiveAgentService
from app.security.rbac import TraderDep
from app.services.market_data_service import MarketDataService

router = APIRouter(prefix="/agent", tags=["agent"])


class _MarketQuoteAdapter:
    """Copy a ticker into the agent quote contract without hiding freshness."""

    def __init__(self, market_data: MarketDataService) -> None:
        self._market_data = market_data

    def quote(self, symbol: str) -> MarketQuoteView:
        ticker = self._market_data.get_ticker(symbol)
        meta = ticker.meta
        return MarketQuoteView(
            symbol=str(meta.symbol),
            last_price=str(ticker.last_price),
            source=meta.source,
            is_live=meta.is_live,
            is_stale=meta.is_stale,
            fallback_used=meta.fallback_used,
            provider_name=meta.provider_name,
        )


def _service(
    session: SessionDep,
    settings: SettingsDep,
    market_data: MarketDataServiceDep,
) -> InteractiveAgentService:
    return InteractiveAgentService(
        session,
        settings=settings,
        market_reader=_MarketQuoteAdapter(market_data),
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
    market_data: MarketDataServiceDep,
) -> AgentTurnResult:
    result = _service(session, settings, market_data).handle_turn(
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
    market_data: MarketDataServiceDep,
) -> StructuredActionProposal:
    result = _service(session, settings, market_data).confirm(
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
    market_data: MarketDataServiceDep,
) -> StructuredActionProposal:
    result = _service(session, settings, market_data).reject(
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
    market_data: MarketDataServiceDep,
) -> ScreenshotAnalysisContract:
    result = _service(session, settings, market_data).screenshot_contract(
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
    market_data: MarketDataServiceDep,
) -> VoiceIoContract:
    result = _service(session, settings, market_data).voice_input_contract(
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
    market_data: MarketDataServiceDep,
) -> VoiceIoContract:
    result = _service(session, settings, market_data).voice_output_contract(
        body,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
    )
    session.commit()
    return result

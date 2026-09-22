"""Optional webhook router. ``create_app`` does not mount it."""

from __future__ import annotations

from fastapi import FastAPI, Request, Response
from fastapi.routing import APIRouter

from app.core.config import TelegramInboundMode
from app.telegram_activation.controller import TelegramPaperActivation
from app.telegram_activation.errors import TelegramActivationError


def build_telegram_webhook_router(controller: TelegramPaperActivation) -> APIRouter:
    router = APIRouter(tags=["telegram-paper-activation"])

    @router.post("/webhooks/telegram/paper")
    async def telegram_paper_webhook(request: Request) -> Response:
        raw = await request.body()
        header = request.headers.get("x-telegram-bot-api-secret-token")
        result = controller.accept_webhook(raw_body=raw, secret_header=header)
        return Response(status_code=result.status_code)

    return router


def mount_paper_telegram_webhook(app: FastAPI, controller: TelegramPaperActivation) -> None:
    """Mount the paper webhook only after a passing local preflight.

    The application factory does not call this.
    """
    if controller.settings.telegram_inbound_mode is not TelegramInboundMode.WEBHOOK:
        raise TelegramActivationError(
            "Webhook mount requires TELEGRAM_INBOUND_MODE=webhook.",
            reason="inbound_mode",
        )
    if not controller.armed:
        raise TelegramActivationError(
            "Webhook mount requires an armed paper controller.",
            reason="not_armed",
        )
    report = controller.preflight()
    if not report.runtime_armable:
        raise TelegramActivationError(
            "Webhook mount blocked by preflight.",
            reason="preflight_blocked",
        )
    app.include_router(build_telegram_webhook_router(controller))
    controller.mark_webhook_mounted()
    app.state.telegram_webhook_mounted = True
    app.state.telegram_paper_activation = controller

"""
WhatsApp integration.

Uses WhatsApp Web (https://web.whatsapp.com) in the browser via
Playwright. Requires the user to be signed in to WhatsApp Web once.

Tools:
    - whatsapp_open_chat       (opens Web)
    - whatsapp_send_message    (opens Web with a prefilled message to a number)
"""
from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus

from app.core.logger import get_logger
from app.tools.base import ToolResult, RiskLevel
from app.tools.integrations.integration_base import AppIntegrationTool

logger = get_logger(__name__)

WHATSAPP_WEB = "https://web.whatsapp.com"


# ---------------------------------------------------------------------- #
# Tool: whatsapp_open_chat
# ---------------------------------------------------------------------- #
class WhatsAppOpenChatTool(AppIntegrationTool):
    APP_KEY = "whatsapp"
    CONFIG_SECTION = "integrations.social_media"

    name = "whatsapp_open_chat"
    description = "Open WhatsApp Web in the EVA browser."
    parameters = {"type": "object", "properties": {}, "required": []}
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        try:
            from app.tools.registry import ToolRegistry
            r = await ToolRegistry.execute("open_url", {"url": WHATSAPP_WEB})
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "OPEN_FAILED", "message": str(exc)},
            )
        return ToolResult(
            success=r.success,
            tool=self.name,
            data={"url": WHATSAPP_WEB},
        )


# ---------------------------------------------------------------------- #
# Tool: whatsapp_send_message
# ---------------------------------------------------------------------- #
class WhatsAppSendMessageTool(AppIntegrationTool):
    APP_KEY = "whatsapp"
    CONFIG_SECTION = "integrations.social_media"

    name = "whatsapp_send_message"
    description = (
        "Open WhatsApp Web with a prefilled message to a phone number. "
        "The user must press Enter to actually send."
    )
    parameters = {
        "type": "object",
        "properties": {
            "phone": {"type": "string"},
            "message": {"type": "string"},
        },
        "required": ["phone", "message"],
    }
    risk_level = RiskLevel.HIGH
    requires_confirmation = True

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        phone = str(kwargs.get("phone", "")).strip().replace(" ", "").lstrip("+")
        message = str(kwargs.get("message") or "").strip()
        if not phone or not message:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "phone + message required"},
            )

        url = f"https://wa.me/{phone}?text={quote_plus(message)}"
        try:
            from app.tools.registry import ToolRegistry
            r = await ToolRegistry.execute("open_url", {"url": url})
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "OPEN_FAILED", "message": str(exc)},
            )
        return ToolResult(
            success=r.success,
            tool=self.name,
            data={
                "phone": phone,
                "url": url,
                "note": "Press Enter in WhatsApp Web to send.",
            },
        )
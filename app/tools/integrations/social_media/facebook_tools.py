"""
Facebook & Messenger integration.

Opens Facebook Messenger Web. Message sending requires the user to
authenticate once; we prefill the message URL.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus

from app.core.logger import get_logger
from app.tools.base import ToolResult, RiskLevel
from app.tools.integrations.integration_base import AppIntegrationTool

logger = get_logger(__name__)

MESSENGER_WEB = "https://www.messenger.com"


# ---------------------------------------------------------------------- #
# Tool: facebook_open_messenger
# ---------------------------------------------------------------------- #
class FacebookOpenMessengerTool(AppIntegrationTool):
    APP_KEY = "facebook"
    CONFIG_SECTION = "integrations.social_media"

    name = "facebook_open_messenger"
    description = "Open Facebook Messenger Web in the EVA browser."
    parameters = {"type": "object", "properties": {}, "required": []}
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        try:
            from app.tools.registry import ToolRegistry
            r = await ToolRegistry.execute("open_url", {"url": MESSENGER_WEB})
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "OPEN_FAILED", "message": str(exc)},
            )
        return ToolResult(success=r.success, tool=self.name, data={"url": MESSENGER_WEB})


# ---------------------------------------------------------------------- #
# Tool: facebook_send_message
# ---------------------------------------------------------------------- #
class FacebookSendMessageTool(AppIntegrationTool):
    APP_KEY = "facebook"
    CONFIG_SECTION = "integrations.social_media"

    name = "facebook_send_message"
    description = (
        "Open Messenger with a prefilled message. "
        "The user must select the recipient and press Enter."
    )
    parameters = {
        "type": "object",
        "properties": {
            "username": {"type": "string"},
            "message": {"type": "string"},
        },
        "required": ["message"],
    }
    risk_level = RiskLevel.HIGH
    requires_confirmation = True

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        message = str(kwargs.get("message") or "").strip()
        username = str(kwargs.get("username") or "").strip()
        if not message:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "message required"},
            )

        if username:
            url = f"https://www.messenger.com/t/{quote_plus(username)}"
        else:
            url = MESSENGER_WEB

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
                "url": url,
                "prefilled_message": message,
                "note": "Paste the message in Messenger and press Enter.",
            },
        )
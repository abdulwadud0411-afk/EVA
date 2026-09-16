"""
Instagram integration.

Opens Instagram Web. No API for posting (Meta requires business APIs);
direct post automation is not supported here.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus

from app.core.logger import get_logger
from app.tools.base import ToolResult, RiskLevel
from app.tools.integrations.integration_base import AppIntegrationTool

logger = get_logger(__name__)

INSTAGRAM_WEB = "https://www.instagram.com"


# ---------------------------------------------------------------------- #
# Tool: instagram_open
# ---------------------------------------------------------------------- #
class InstagramOpenTool(AppIntegrationTool):
    APP_KEY = "instagram"
    CONFIG_SECTION = "integrations.social_media"

    name = "instagram_open"
    description = "Open Instagram Web in the EVA browser."
    parameters = {"type": "object", "properties": {}, "required": []}
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        try:
            from app.tools.registry import ToolRegistry
            r = await ToolRegistry.execute("open_url", {"url": INSTAGRAM_WEB})
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "OPEN_FAILED", "message": str(exc)},
            )
        return ToolResult(success=r.success, tool=self.name, data={"url": INSTAGRAM_WEB})


# ---------------------------------------------------------------------- #
# Tool: instagram_open_profile
# ---------------------------------------------------------------------- #
class InstagramOpenProfileTool(AppIntegrationTool):
    APP_KEY = "instagram"
    CONFIG_SECTION = "integrations.social_media"

    name = "instagram_open_profile"
    description = "Open a specific Instagram profile in the browser."
    parameters = {
        "type": "object",
        "properties": {"username": {"type": "string"}},
        "required": ["username"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        username = str(kwargs.get("username") or "").strip().lstrip("@")
        if not username:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "username required"},
            )
        url = f"{INSTAGRAM_WEB}/{quote_plus(username)}/"
        try:
            from app.tools.registry import ToolRegistry
            r = await ToolRegistry.execute("open_url", {"url": url})
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "OPEN_FAILED", "message": str(exc)},
            )
        return ToolResult(success=r.success, tool=self.name, data={"url": url})
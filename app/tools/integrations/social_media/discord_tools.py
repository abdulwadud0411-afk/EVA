"""
Discord integration.

Uses Discord's public webhooks (free) for sending messages to a
server channel. For opening the app, uses the discord:// URI.

Tools:
    - discord_open_channel
    - discord_send_message    (requires DISCORD_WEBHOOK_URL)
"""
from __future__ import annotations

import os
import subprocess
from typing import Any

import httpx

from app.core.logger import get_logger
from app.tools.base import ToolResult, RiskLevel
from app.tools.integrations.integration_base import AppIntegrationTool

logger = get_logger(__name__)


# ---------------------------------------------------------------------- #
# Tool: discord_open_channel
# ---------------------------------------------------------------------- #
class DiscordOpenChannelTool(AppIntegrationTool):
    APP_KEY = "discord"
    CONFIG_SECTION = "integrations.social_media"

    name = "discord_open_channel"
    description = "Open the Discord desktop app to the home screen."
    parameters = {"type": "object", "properties": {}, "required": []}
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        try:
            subprocess.Popen(["start", "", "discord://"], shell=True)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "LAUNCH_FAILED", "message": str(exc)},
            )
        return ToolResult(success=True, tool=self.name, data={"launched": True})


# ---------------------------------------------------------------------- #
# Tool: discord_send_message
# ---------------------------------------------------------------------- #
class DiscordSendMessageTool(AppIntegrationTool):
    APP_KEY = "discord"
    CONFIG_SECTION = "integrations.social_media"

    name = "discord_send_message"
    description = (
        "Send a message to a Discord channel via webhook. "
        "Requires DISCORD_WEBHOOK_URL in .env."
    )
    parameters = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }
    risk_level = RiskLevel.HIGH
    requires_confirmation = True

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        text = str(kwargs.get("text") or "").strip()
        if not text:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "text required"},
            )

        url = os.getenv("DISCORD_WEBHOOK_URL")
        if not url:
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "NO_WEBHOOK",
                    "message": "Set DISCORD_WEBHOOK_URL in .env.",
                },
            )

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.post(url, json={"content": text})
                r.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "DISCORD_SEND_FAILED", "message": str(exc)},
            )

        return ToolResult(success=True, tool=self.name, data={"sent": True})
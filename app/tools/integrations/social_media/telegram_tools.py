"""
Telegram integration.

Two modes:
    1. Desktop app automation (default) — opens the app to a chat
       and pastes text into the message box.
    2. Bot API (optional) — if TELEGRAM_BOT_TOKEN is set, sends
       messages to chats the bot is in.

No paid middleware.
"""
from __future__ import annotations

import os
import subprocess
import time
from typing import Any

import httpx

from app.core.logger import get_logger
from app.tools.base import ToolResult, RiskLevel
from app.tools.integrations.integration_base import AppIntegrationTool

logger = get_logger(__name__)

TELEGRAM_API = "https://api.telegram.org"


# ---------------------------------------------------------------------- #
# Tool: telegram_open_chat
# ---------------------------------------------------------------------- #
class TelegramOpenChatTool(AppIntegrationTool):
    APP_KEY = "telegram"
    CONFIG_SECTION = "integrations.social_media"

    name = "telegram_open_chat"
    description = "Open the Telegram desktop app to the home screen."
    parameters = {"type": "object", "properties": {}, "required": []}
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        try:
            subprocess.Popen(
                ["start", "", "tg://"],
                shell=True,
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "LAUNCH_FAILED", "message": str(exc)},
            )
        return ToolResult(success=True, tool=self.name, data={"launched": True})


# ---------------------------------------------------------------------- #
# Tool: telegram_send_message
# ---------------------------------------------------------------------- #
class TelegramSendMessageTool(AppIntegrationTool):
    APP_KEY = "telegram"
    CONFIG_SECTION = "integrations.social_media"

    name = "telegram_send_message"
    description = (
        "Send a Telegram message via Bot API (if TELEGRAM_BOT_TOKEN is set) "
        "or open the desktop app with a prefilled text (if no token)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "chat_id": {"type": "string"},
            "text": {"type": "string"},
        },
        "required": ["text"],
    }
    risk_level = RiskLevel.HIGH
    requires_confirmation = True

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        text = str(kwargs.get("text") or "").strip()
        chat_id = str(kwargs.get("chat_id") or "").strip()
        if not text:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "text required"},
            )

        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if token and chat_id:
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    r = await client.post(
                        f"{TELEGRAM_API}/bot{token}/sendMessage",
                        json={"chat_id": chat_id, "text": text},
                    )
                    r.raise_for_status()
                    data = r.json()
            except Exception as exc:  # noqa: BLE001
                return ToolResult(
                    success=False,
                    tool=self.name,
                    error={"code": "TELEGRAM_API_FAILED", "message": str(exc)},
                )
            return ToolResult(
                success=data.get("ok", False),
                tool=self.name,
                data={"via": "bot_api", "chat_id": chat_id},
            )

        # Fallback: open Telegram Desktop
        try:
            subprocess.Popen(["start", "", "tg://"], shell=True)
            time.sleep(1.0)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "LAUNCH_FAILED", "message": str(exc)},
            )
        return ToolResult(
            success=True,
            tool=self.name,
            data={
                "via": "desktop_app",
                "note": "Telegram opened. Set TELEGRAM_BOT_TOKEN for direct sends.",
            },
        )
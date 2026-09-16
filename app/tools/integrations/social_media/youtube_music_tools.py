"""
YouTube Music integration.

Opens YouTube Music with a search query. No API key needed —
uses the browser or the installed app.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus

from app.core.logger import get_logger
from app.tools.base import ToolResult, RiskLevel
from app.tools.integrations.integration_base import AppIntegrationTool

logger = get_logger(__name__)


# ---------------------------------------------------------------------- #
# Tool: youtube_music_search
# ---------------------------------------------------------------------- #
class YouTubeMusicSearchTool(AppIntegrationTool):
    APP_KEY = "youtube_music"
    CONFIG_SECTION = "integrations.social_media"

    name = "youtube_music_search"
    description = "Open YouTube Music search for a query in the browser."
    parameters = {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        query = str(kwargs.get("query") or "").strip()
        if not query:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "query required"},
            )

        url = f"https://music.youtube.com/search?q={quote_plus(query)}"
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
            data={"query": query, "url": url},
        )


# ---------------------------------------------------------------------- #
# Tool: youtube_music_play
# ---------------------------------------------------------------------- #
class YouTubeMusicPlayTool(AppIntegrationTool):
    APP_KEY = "youtube_music"
    CONFIG_SECTION = "integrations.social_media"

    name = "youtube_music_play"
    description = "Open a YouTube Music song or video by search query."
    parameters = {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        query = str(kwargs.get("query") or "").strip()
        if not query:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "query required"},
            )

        # Direct to regular YouTube which auto-plays on click-friendly URLs
        url = f"https://music.youtube.com/search?q={quote_plus(query)}"
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
            data={"query": query, "url": url, "note": "Click the top result in YouTube Music."},
        )
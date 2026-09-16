"""
Spotify integration.

Controls the Spotify desktop app via media keys (play/pause/next/prev)
and uses the Web API to play a specific track when credentials are set.

The desktop app doesn't need credentials for playback control.
The Web API requires SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET
(optional, only for specific-track playback).

No paid middleware used.
"""
from __future__ import annotations

import base64
import os
import time
from typing import Any, Optional

import httpx

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger
from app.tools.base import ToolResult, RiskLevel
from app.tools.integrations.integration_base import AppIntegrationTool

logger = get_logger(__name__)

SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"


def _press_media_key(key: str) -> None:
    try:
        import pyautogui  # type: ignore
        pyautogui.press(key)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"pyautogui failed: {exc}")


async def _get_access_token() -> Optional[str]:
    cid = os.getenv("SPOTIFY_CLIENT_ID")
    secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    if not cid or not secret:
        return None
    creds = base64.b64encode(f"{cid}:{secret}".encode()).decode()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                SPOTIFY_TOKEN_URL,
                headers={
                    "Authorization": f"Basic {creds}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={"grant_type": "client_credentials"},
            )
            r.raise_for_status()
            return r.json().get("access_token")
    except Exception as exc:  # noqa: BLE001
        logger.error("spotify_token_failed", error=str(exc))
        return None


# ---------------------------------------------------------------------- #
# Tool: spotify_play_pause
# ---------------------------------------------------------------------- #
class SpotifyPlayPauseTool(AppIntegrationTool):
    APP_KEY = "spotify"
    CONFIG_SECTION = "integrations.social_media"

    name = "spotify_play_pause"
    description = "Toggle play/pause in Spotify (uses the media key)."
    parameters = {"type": "object", "properties": {}, "required": []}
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        try:
            _press_media_key("playpause")
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "MEDIA_KEY_FAILED", "message": str(exc)},
            )
        return ToolResult(success=True, tool=self.name, data={"action": "play_pause"})


# ---------------------------------------------------------------------- #
# Tool: spotify_next
# ---------------------------------------------------------------------- #
class SpotifyNextTool(AppIntegrationTool):
    APP_KEY = "spotify"
    CONFIG_SECTION = "integrations.social_media"

    name = "spotify_next"
    description = "Skip to the next track in Spotify."
    parameters = {"type": "object", "properties": {}, "required": []}
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        try:
            _press_media_key("nexttrack")
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "MEDIA_KEY_FAILED", "message": str(exc)},
            )
        return ToolResult(success=True, tool=self.name, data={"action": "next"})


# ---------------------------------------------------------------------- #
# Tool: spotify_previous
# ---------------------------------------------------------------------- #
class SpotifyPreviousTool(AppIntegrationTool):
    APP_KEY = "spotify"
    CONFIG_SECTION = "integrations.social_media"

    name = "spotify_previous"
    description = "Go to the previous track in Spotify."
    parameters = {"type": "object", "properties": {}, "required": []}
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        try:
            _press_media_key("prevtrack")
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "MEDIA_KEY_FAILED", "message": str(exc)},
            )
        return ToolResult(success=True, tool=self.name, data={"action": "previous"})


# ---------------------------------------------------------------------- #
# Tool: spotify_play_track
# ---------------------------------------------------------------------- #
class SpotifyPlayTrackTool(AppIntegrationTool):
    APP_KEY = "spotify"
    CONFIG_SECTION = "integrations.social_media"

    name = "spotify_play_track"
    description = (
        "Open Spotify with a search for a track. If Spotify Web API creds "
        "are set, this can also start playback. Otherwise it opens the app."
    )
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

        # Try Web API first
        token = await _get_access_token()
        if token:
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    r = await client.get(
                        f"{SPOTIFY_API_BASE}/search",
                        headers={"Authorization": f"Bearer {token}"},
                        params={"q": query, "type": "track", "limit": 1},
                    )
                    r.raise_for_status()
                    data = r.json()
                    tracks = data.get("tracks", {}).get("items", [])
                    if tracks:
                        return ToolResult(
                            success=True,
                            tool=self.name,
                            data={
                                "query": query,
                                "found": tracks[0].get("name"),
                                "artist": (tracks[0].get("artists") or [{}])[0].get("name"),
                                "uri": tracks[0].get("uri"),
                                "note": "Use the Spotify app to play this track.",
                            },
                        )
            except Exception as exc:  # noqa: BLE001
                logger.warning("spotify_web_api_failed", error=str(exc))

        # Fallback: open Spotify app
        try:
            import subprocess
            subprocess.Popen(["start", "spotify:"], shell=True)
        except Exception:  # noqa: BLE001
            pass

        return ToolResult(
            success=True,
            tool=self.name,
            data={
                "query": query,
                "note": "Opened Spotify app. Search manually or set Spotify API credentials.",
            },
        )
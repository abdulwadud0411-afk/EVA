"""
Zoom integration.

Uses Zoom's `zoommtg://` URI scheme to launch the desktop app with
a meeting ID or personal link. No API key required for basic join/start.

Tools:
    - zoom_start_meeting   (needs Zoom signed in)
    - zoom_join_meeting
"""
from __future__ import annotations

import subprocess
import time
from typing import Any
from urllib.parse import quote_plus

from app.core.logger import get_logger
from app.tools.base import ToolResult, RiskLevel
from app.tools.integrations.integration_base import AppIntegrationTool

logger = get_logger(__name__)


# ---------------------------------------------------------------------- #
# Tool: zoom_start_meeting
# ---------------------------------------------------------------------- #
class ZoomStartMeetingTool(AppIntegrationTool):
    APP_KEY = "zoom"
    CONFIG_SECTION = "integrations.social_media"

    name = "zoom_start_meeting"
    description = "Open the Zoom app to start a new meeting (requires sign-in)."
    parameters = {"type": "object", "properties": {}, "required": []}
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        try:
            subprocess.Popen(["start", "", "zoommtg://zoom.us/start"], shell=True)
            time.sleep(1.5)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "LAUNCH_FAILED", "message": str(exc)},
            )
        return ToolResult(
            success=True,
            tool=self.name,
            data={"note": "Zoom opening — confirm meeting details in the app."},
        )


# ---------------------------------------------------------------------- #
# Tool: zoom_join_meeting
# ---------------------------------------------------------------------- #
class ZoomJoinMeetingTool(AppIntegrationTool):
    APP_KEY = "zoom"
    CONFIG_SECTION = "integrations.social_media"

    name = "zoom_join_meeting"
    description = "Join a Zoom meeting by ID or personal link name."
    parameters = {
        "type": "object",
        "properties": {
            "meeting_id": {"type": "string"},
            "passcode": {"type": "string"},
        },
        "required": ["meeting_id"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        meeting_id = str(kwargs.get("meeting_id", "")).strip().replace(" ", "")
        if not meeting_id:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "meeting_id required"},
            )
        passcode = str(kwargs.get("passcode") or "").strip()

        url = f"zoommtg://zoom.us/join?action=join&confno={meeting_id}"
        if passcode:
            url += f"&pwd={quote_plus(passcode)}"

        try:
            subprocess.Popen(["start", "", url], shell=True)
            time.sleep(1.5)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "LAUNCH_FAILED", "message": str(exc)},
            )
        return ToolResult(
            success=True,
            tool=self.name,
            data={"meeting_id": meeting_id, "passcode_provided": bool(passcode)},
        )
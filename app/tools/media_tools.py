"""
Media control tools (Phase 5).

Tools:
    - volume_up
    - volume_down
    - mute
    - media_control  (play/pause/next/prev/stop)

Volume control uses pycaw (Windows Core Audio). Media keys are
sent via pyautogui.press().
"""
from __future__ import annotations

from typing import Any, Optional

from app.core.logger import get_logger
from app.tools.base import Tool, ToolResult, RiskLevel

logger = get_logger(__name__)

try:
    import pyautogui  # type: ignore
    _PYAUTOGUI_AVAILABLE = True
except Exception:  # noqa: BLE001
    pyautogui = None  # type: ignore
    _PYAUTOGUI_AVAILABLE = False

try:
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL  # type: ignore
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume  # type: ignore
    _PYCAW_AVAILABLE = True
except Exception:  # noqa: BLE001
    _PYCAW_AVAILABLE = False


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #
def _get_volume_interface():
    """Return an IAudioEndpointVolume wrapper, or None on failure."""
    if not _PYCAW_AVAILABLE:
        return None
    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return cast(interface, POINTER(IAudioEndpointVolume))
    except Exception as exc:  # noqa: BLE001
        logger.error("volume_interface_failed", error=str(exc))
        return None


def _ensure_volume_available(tool_name: str) -> Optional[ToolResult]:
    if not _PYCAW_AVAILABLE:
        return ToolResult(
            success=False,
            tool=tool_name,
            error={
                "code": "PLATFORM_UNSUPPORTED",
                "message": "Volume control requires pycaw and comtypes.",
            },
        )
    return None


def _ensure_media_available(tool_name: str) -> Optional[ToolResult]:
    if not _PYAUTOGUI_AVAILABLE:
        return ToolResult(
            success=False,
            tool=tool_name,
            error={
                "code": "PLATFORM_UNSUPPORTED",
                "message": "Media key control requires pyautogui.",
            },
        )
    return None


# ---------------------------------------------------------------------- #
# Tool: volume_up
# ---------------------------------------------------------------------- #
class VolumeUpTool(Tool):
    name = "volume_up"
    description = "Increase the system volume by a step (default 10%)."
    parameters = {
        "type": "object",
        "properties": {
            "step": {
                "type": "integer",
                "description": "Percentage step to add (default 10).",
            },
        },
        "required": [],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        err = _ensure_volume_available(self.name)
        if err is not None:
            return err

        vol = _get_volume_interface()
        if vol is None:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "VOLUME_INTERFACE_FAILED", "message": "Cannot access volume control."},
            )

        try:
            step = int(kwargs.get("step", 10))
        except (TypeError, ValueError):
            step = 10
        if step <= 0 or step > 100:
            step = 10

        try:
            current = vol.GetMasterVolumeLevelScalar()
            new_level = min(1.0, current + step / 100.0)
            vol.SetMasterVolumeLevelScalar(new_level, None)
        except Exception as exc:  # noqa: BLE001
            logger.error("volume_up_failed", error=str(exc))
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "VOLUME_CHANGE_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"new_level_percent": int(new_level * 100)},
        )


# ---------------------------------------------------------------------- #
# Tool: volume_down
# ---------------------------------------------------------------------- #
class VolumeDownTool(Tool):
    name = "volume_down"
    description = "Decrease the system volume by a step (default 10%)."
    parameters = {
        "type": "object",
        "properties": {
            "step": {
                "type": "integer",
                "description": "Percentage step to subtract (default 10).",
            },
        },
        "required": [],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        err = _ensure_volume_available(self.name)
        if err is not None:
            return err

        vol = _get_volume_interface()
        if vol is None:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "VOLUME_INTERFACE_FAILED", "message": "Cannot access volume control."},
            )

        try:
            step = int(kwargs.get("step", 10))
        except (TypeError, ValueError):
            step = 10
        if step <= 0 or step > 100:
            step = 10

        try:
            current = vol.GetMasterVolumeLevelScalar()
            new_level = max(0.0, current - step / 100.0)
            vol.SetMasterVolumeLevelScalar(new_level, None)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "VOLUME_CHANGE_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"new_level_percent": int(new_level * 100)},
        )


# ---------------------------------------------------------------------- #
# Tool: mute
# ---------------------------------------------------------------------- #
class MuteTool(Tool):
    name = "mute"
    description = "Mute or unmute the system speakers."
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "'on', 'off', or 'toggle' (default 'toggle').",
            },
        },
        "required": [],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        err = _ensure_volume_available(self.name)
        if err is not None:
            return err

        vol = _get_volume_interface()
        if vol is None:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "VOLUME_INTERFACE_FAILED", "message": "Cannot access volume control."},
            )

        action = str(kwargs.get("action", "toggle")).strip().lower()
        try:
            current_mute = bool(vol.GetMute())
            if action == "on":
                new_mute = True
            elif action == "off":
                new_mute = False
            else:  # toggle
                new_mute = not current_mute
            vol.SetMute(new_mute, None)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "MUTE_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"muted": new_mute},
        )


# ---------------------------------------------------------------------- #
# Tool: media_control
# ---------------------------------------------------------------------- #
class MediaControlTool(Tool):
    name = "media_control"
    description = (
        "Send a media key. Supported actions: play_pause, next, prev, stop."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "One of: play_pause, next, prev, stop.",
            },
        },
        "required": ["action"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    _KEY_MAP = {
        "play_pause": "playpause",
        "next": "nexttrack",
        "prev": "prevtrack",
        "stop": "stop",
    }

    async def run(self, **kwargs: Any) -> ToolResult:
        err = _ensure_media_available(self.name)
        if err is not None:
            return err

        action = str(kwargs.get("action", "")).strip().lower()
        if action not in self._KEY_MAP:
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "INVALID_ARGUMENT",
                    "message": f"action must be one of {list(self._KEY_MAP.keys())}",
                },
            )

        key = self._KEY_MAP[action]
        try:
            pyautogui.press(key)  # type: ignore
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "MEDIA_KEY_FAILED", "message": str(exc)},
            )

        return ToolResult(success=True, tool=self.name, data={"action": action})
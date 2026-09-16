"""
Keyboard control tools (Phase 4).

Tools:
    - press_key      : press a single key
    - hotkey         : press a combination of keys together
    - type_text      : type a string
    - key_down       : hold a key down
    - key_up         : release a held key

Uses pyautogui for cross-platform keyboard control, but the platform
guard makes it clear that EVA targets Windows.
"""
from __future__ import annotations

import time
from typing import Any, List

from app.core.logger import get_logger
from app.tools.base import Tool, ToolResult, RiskLevel

logger = get_logger(__name__)

try:
    import pyautogui  # type: ignore
    _PYAUTOGUI_AVAILABLE = True
except Exception:  # noqa: BLE001
    pyautogui = None  # type: ignore
    _PYAUTOGUI_AVAILABLE = False


# Fail-safe: pyautogui's own failsafe (moving mouse to a corner aborts).
# We keep it enabled by default so the user always has an escape hatch.
if _PYAUTOGUI_AVAILABLE:
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.02


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #
def _ensure_pyautogui() -> Any:
    if not _PYAUTOGUI_AVAILABLE:
        return None
    return pyautogui


def _platform_error(tool_name: str) -> ToolResult:
    return ToolResult(
        success=False,
        tool=tool_name,
        error={
            "code": "PLATFORM_UNSUPPORTED",
            "message": "Keyboard control requires pyautogui and a GUI session.",
        },
    )


# ---------------------------------------------------------------------- #
# Tool: press_key
# ---------------------------------------------------------------------- #
class PressKeyTool(Tool):
    name = "press_key"
    description = (
        "Press a single keyboard key. Examples: 'enter', 'tab', 'escape', "
        "'f5', 'a', 'space'."
    )
    parameters = {
        "type": "object",
        "properties": {
            "key": {"type": "string", "description": "Key name to press."},
            "presses": {
                "type": "integer",
                "description": "How many times to press (default 1).",
            },
        },
        "required": ["key"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        gui = _ensure_pyautogui()
        if gui is None:
            return _platform_error(self.name)

        key = str(kwargs.get("key", "")).strip()
        if not key:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "key is required"},
            )
        try:
            presses = int(kwargs.get("presses", 1))
        except (TypeError, ValueError):
            presses = 1
        if presses <= 0 or presses > 100:
            presses = 1

        try:
            gui.press(key, presses=presses)
        except Exception as exc:  # noqa: BLE001
            logger.error("press_key_failed", key=key, error=str(exc))
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "KEY_PRESS_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"key": key, "presses": presses},
        )


# ---------------------------------------------------------------------- #
# Tool: hotkey
# ---------------------------------------------------------------------- #
class HotkeyTool(Tool):
    name = "hotkey"
    description = (
        "Press a combination of keys together, e.g. ctrl+c, ctrl+v, alt+tab. "
        "Pass keys as a list."
    )
    parameters = {
        "type": "object",
        "properties": {
            "keys": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Keys to press together, e.g. ['ctrl', 'c'].",
            },
        },
        "required": ["keys"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        gui = _ensure_pyautogui()
        if gui is None:
            return _platform_error(self.name)

        keys = kwargs.get("keys")
        if not keys or not isinstance(keys, list):
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "INVALID_ARGUMENT",
                    "message": "keys must be a non-empty list of strings",
                },
            )

        keys = [str(k).strip() for k in keys if str(k).strip()]
        if not keys:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "keys list is empty"},
            )

        try:
            gui.hotkey(*keys)
        except Exception as exc:  # noqa: BLE001
            logger.error("hotkey_failed", keys=keys, error=str(exc))
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "HOTKEY_FAILED", "message": str(exc)},
            )

        return ToolResult(success=True, tool=self.name, data={"keys": keys})


# ---------------------------------------------------------------------- #
# Tool: type_text
# ---------------------------------------------------------------------- #
class TypeTextTool(Tool):
    name = "type_text"
    description = (
        "Type a string of text as if the user typed it. "
        "Works with English, Bangla and Banglish text."
    )
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "The text to type."},
            "interval": {
                "type": "number",
                "description": "Delay between keypresses in seconds (default 0.02).",
            },
        },
        "required": ["text"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        gui = _ensure_pyautogui()
        if gui is None:
            return _platform_error(self.name)

        text = kwargs.get("text")
        if text is None:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "text is required"},
            )
        text = str(text)
        if not text:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "text is empty"},
            )

        try:
            interval = float(kwargs.get("interval", 0.02))
        except (TypeError, ValueError):
            interval = 0.02
        if interval < 0 or interval > 1.0:
            interval = 0.02

        try:
            gui.typewrite(text, interval=interval)
        except Exception as exc:  # noqa: BLE001
            logger.error("type_text_failed", error=str(exc))
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "TYPE_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"typed_length": len(text)},
        )


# ---------------------------------------------------------------------- #
# Tool: key_down
# ---------------------------------------------------------------------- #
class KeyDownTool(Tool):
    name = "key_down"
    description = "Hold a key down (until key_up is called)."
    parameters = {
        "type": "object",
        "properties": {
            "key": {"type": "string"},
        },
        "required": ["key"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        gui = _ensure_pyautogui()
        if gui is None:
            return _platform_error(self.name)

        key = str(kwargs.get("key", "")).strip()
        if not key:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "key is required"},
            )

        try:
            gui.keyDown(key)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "KEY_DOWN_FAILED", "message": str(exc)},
            )

        return ToolResult(success=True, tool=self.name, data={"key": key})


# ---------------------------------------------------------------------- #
# Tool: key_up
# ---------------------------------------------------------------------- #
class KeyUpTool(Tool):
    name = "key_up"
    description = "Release a key previously held with key_down."
    parameters = {
        "type": "object",
        "properties": {
            "key": {"type": "string"},
        },
        "required": ["key"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        gui = _ensure_pyautogui()
        if gui is None:
            return _platform_error(self.name)

        key = str(kwargs.get("key", "")).strip()
        if not key:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "key is required"},
            )

        try:
            gui.keyUp(key)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "KEY_UP_FAILED", "message": str(exc)},
            )

        return ToolResult(success=True, tool=self.name, data={"key": key})
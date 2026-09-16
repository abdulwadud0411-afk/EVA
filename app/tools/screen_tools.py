"""
Screen capture tools (Phase 5 + Phase 6).

Tools:
    - take_screenshot
    - get_screen_size
    - get_active_window_screenshot
    - crop_screenshot

Phase 6 adds an internal helper used by vision tools:
    - capture_for_vision()  (not registered as a tool)

Screenshots are saved as PNG under data/screenshots/.
"""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.config_manager import ConfigManager
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
    from PIL import Image  # type: ignore
    _PIL_AVAILABLE = True
except Exception:  # noqa: BLE001
    Image = None  # type: ignore
    _PIL_AVAILABLE = False


# ---------------------------------------------------------------------- #
# Internal helpers
# ---------------------------------------------------------------------- #
def _ensure_available(tool_name: str) -> Optional[ToolResult]:
    if not _PYAUTOGUI_AVAILABLE or not _PIL_AVAILABLE:
        return ToolResult(
            success=False,
            tool=tool_name,
            error={
                "code": "PLATFORM_UNSUPPORTED",
                "message": "Screenshot requires pyautogui and Pillow.",
            },
        )
    return None


def _screenshots_dir() -> Path:
    base = ConfigManager.get_data_dir()
    d = base / "screenshots"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _timestamped_filename(prefix: str = "shot") -> Path:
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")[:-3]
    return _screenshots_dir() / f"{prefix}_{ts}.png"


def capture_for_vision() -> Path:
    """
    Take a full-screen screenshot and return its path.

    Used by vision tools (Phase 6). Raises RuntimeError if capture
    is not possible. The caller is responsible for cleanup if needed.
    """
    if not _PYAUTOGUI_AVAILABLE or not _PIL_AVAILABLE:
        raise RuntimeError("Screenshot unavailable (pyautogui/Pillow missing).")
    image = pyautogui.screenshot()  # type: ignore
    path = _timestamped_filename("vision")
    image.save(str(path))
    return path


# ---------------------------------------------------------------------- #
# Tool: take_screenshot
# ---------------------------------------------------------------------- #
class TakeScreenshotTool(Tool):
    name = "take_screenshot"
    description = (
        "Capture the entire primary screen and save it as a PNG file. "
        "Returns the absolute path of the saved screenshot."
    )
    parameters = {"type": "object", "properties": {}, "required": []}
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        err = _ensure_available(self.name)
        if err is not None:
            return err

        try:
            image = pyautogui.screenshot()  # type: ignore
        except Exception as exc:  # noqa: BLE001
            logger.error("screenshot_failed", error=str(exc))
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "CAPTURE_FAILED", "message": str(exc)},
            )

        path = _timestamped_filename("shot")
        try:
            image.save(str(path))
        except Exception as exc:  # noqa: BLE001
            logger.error("screenshot_save_failed", error=str(exc))
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "SAVE_FAILED", "message": str(exc)},
            )

        width, height = image.size
        return ToolResult(
            success=True,
            tool=self.name,
            data={"path": str(path), "width": width, "height": height},
        )


# ---------------------------------------------------------------------- #
# Tool: get_screen_size
# ---------------------------------------------------------------------- #
class GetScreenSizeTool(Tool):
    name = "get_screen_size"
    description = "Return the primary screen resolution (width, height)."
    parameters = {"type": "object", "properties": {}, "required": []}
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        err = _ensure_available(self.name)
        if err is not None:
            return err

        try:
            size = pyautogui.size()  # type: ignore
            w, h = int(size[0]), int(size[1])
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "QUERY_FAILED", "message": str(exc)},
            )

        return ToolResult(success=True, tool=self.name, data={"width": w, "height": h})


# ---------------------------------------------------------------------- #
# Tool: get_active_window_screenshot
# ---------------------------------------------------------------------- #
class GetActiveWindowScreenshotTool(Tool):
    name = "get_active_window_screenshot"
    description = (
        "Capture only the currently active window (or full screen "
        "if the region cannot be determined)."
    )
    parameters = {"type": "object", "properties": {}, "required": []}
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        err = _ensure_available(self.name)
        if err is not None:
            return err

        region = None
        try:
            import win32gui  # type: ignore
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                rect = win32gui.GetWindowRect(hwnd)
                x1, y1, x2, y2 = rect
                if x2 > x1 and y2 > y1:
                    region = (x1, y1, x2 - x1, y2 - y1)
        except Exception:  # noqa: BLE001
            region = None

        try:
            if region is not None:
                image = pyautogui.screenshot(region=region)  # type: ignore
            else:
                image = pyautogui.screenshot()  # type: ignore
        except Exception as exc:  # noqa: BLE001
            logger.error("active_window_screenshot_failed", error=str(exc))
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "CAPTURE_FAILED", "message": str(exc)},
            )

        path = _timestamped_filename("window")
        try:
            image.save(str(path))
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "SAVE_FAILED", "message": str(exc)},
            )

        width, height = image.size
        return ToolResult(
            success=True,
            tool=self.name,
            data={
                "path": str(path),
                "width": width,
                "height": height,
                "used_region": region is not None,
            },
        )


# ---------------------------------------------------------------------- #
# Tool: crop_screenshot
# ---------------------------------------------------------------------- #
class CropScreenshotTool(Tool):
    name = "crop_screenshot"
    description = (
        "Capture a rectangular region of the screen. "
        "Coordinates are absolute pixels (x, y, width, height)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "x": {"type": "integer"},
            "y": {"type": "integer"},
            "width": {"type": "integer"},
            "height": {"type": "integer"},
        },
        "required": ["x", "y", "width", "height"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        err = _ensure_available(self.name)
        if err is not None:
            return err

        try:
            x = int(kwargs.get("x"))
            y = int(kwargs.get("y"))
            w = int(kwargs.get("width"))
            h = int(kwargs.get("height"))
        except (TypeError, ValueError):
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "INVALID_ARGUMENT",
                    "message": "x, y, width, height must be integers",
                },
            )

        if w <= 0 or h <= 0:
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "INVALID_ARGUMENT",
                    "message": "width and height must be positive",
                },
            )

        try:
            image = pyautogui.screenshot(region=(x, y, w, h))  # type: ignore
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "CAPTURE_FAILED", "message": str(exc)},
            )

        path = _timestamped_filename("crop")
        try:
            image.save(str(path))
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "SAVE_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"path": str(path), "region": {"x": x, "y": y, "width": w, "height": h}},
        )
"""
Mouse control tools (Phase 4).

Tools:
    - move_mouse
    - click
    - double_click
    - right_click
    - scroll

Uses pyautogui. Coordinates are absolute screen pixels. For
deterministic targets (buttons, DOM elements), prefer browser or
window APIs over raw coordinates — mouse tools are a fallback.
"""
from __future__ import annotations

from typing import Any

from app.core.logger import get_logger
from app.tools.base import Tool, ToolResult, RiskLevel

logger = get_logger(__name__)

try:
    import pyautogui  # type: ignore
    _PYAUTOGUI_AVAILABLE = True
except Exception:  # noqa: BLE001
    pyautogui = None  # type: ignore
    _PYAUTOGUI_AVAILABLE = False


if _PYAUTOGUI_AVAILABLE:
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.02


def _ensure_pyautogui() -> Any:
    return pyautogui if _PYAUTOGUI_AVAILABLE else None


def _platform_error(tool_name: str) -> ToolResult:
    return ToolResult(
        success=False,
        tool=tool_name,
        error={
            "code": "PLATFORM_UNSUPPORTED",
            "message": "Mouse control requires pyautogui and a GUI session.",
        },
    )


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _screen_bounds(gui: Any) -> tuple[int, int]:
    try:
        size = gui.size()
        return int(size[0]), int(size[1])
    except Exception:  # noqa: BLE001
        return 1920, 1080


# ---------------------------------------------------------------------- #
# Tool: move_mouse
# ---------------------------------------------------------------------- #
class MoveMouseTool(Tool):
    name = "move_mouse"
    description = "Move the mouse cursor to (x, y) on screen."
    parameters = {
        "type": "object",
        "properties": {
            "x": {"type": "integer"},
            "y": {"type": "integer"},
            "duration": {
                "type": "number",
                "description": "Seconds to take for the move (default 0.2).",
            },
        },
        "required": ["x", "y"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        gui = _ensure_pyautogui()
        if gui is None:
            return _platform_error(self.name)

        x = _safe_int(kwargs.get("x"), None)  # type: ignore
        y = _safe_int(kwargs.get("y"), None)  # type: ignore
        if x is None or y is None:
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "INVALID_ARGUMENT",
                    "message": "x and y must be integers",
                },
            )

        try:
            duration = float(kwargs.get("duration", 0.2))
        except (TypeError, ValueError):
            duration = 0.2
        if duration < 0 or duration > 2.0:
            duration = 0.2

        w, h = _screen_bounds(gui)
        if x < 0 or y < 0 or x >= w or y >= h:
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "OUT_OF_BOUNDS",
                    "message": f"({x},{y}) is outside the screen ({w}x{h}).",
                },
            )

        try:
            gui.moveTo(x, y, duration=duration)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "MOVE_FAILED", "message": str(exc)},
            )

        return ToolResult(success=True, tool=self.name, data={"x": x, "y": y})


# ---------------------------------------------------------------------- #
# Tool: click
# ---------------------------------------------------------------------- #
class ClickTool(Tool):
    name = "click"
    description = "Move the mouse to (x, y) and left-click."
    parameters = {
        "type": "object",
        "properties": {
            "x": {"type": "integer"},
            "y": {"type": "integer"},
        },
        "required": ["x", "y"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        gui = _ensure_pyautogui()
        if gui is None:
            return _platform_error(self.name)

        x = _safe_int(kwargs.get("x"), None)  # type: ignore
        y = _safe_int(kwargs.get("y"), None)  # type: ignore
        if x is None or y is None:
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "INVALID_ARGUMENT",
                    "message": "x and y must be integers",
                },
            )

        w, h = _screen_bounds(gui)
        if x < 0 or y < 0 or x >= w or y >= h:
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "OUT_OF_BOUNDS",
                    "message": f"({x},{y}) is outside the screen ({w}x{h}).",
                },
            )

        try:
            gui.click(x=x, y=y)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "CLICK_FAILED", "message": str(exc)},
            )

        return ToolResult(success=True, tool=self.name, data={"x": x, "y": y})


# ---------------------------------------------------------------------- #
# Tool: double_click
# ---------------------------------------------------------------------- #
class DoubleClickTool(Tool):
    name = "double_click"
    description = "Move the mouse to (x, y) and double-click."
    parameters = {
        "type": "object",
        "properties": {
            "x": {"type": "integer"},
            "y": {"type": "integer"},
        },
        "required": ["x", "y"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        gui = _ensure_pyautogui()
        if gui is None:
            return _platform_error(self.name)

        x = _safe_int(kwargs.get("x"), None)  # type: ignore
        y = _safe_int(kwargs.get("y"), None)  # type: ignore
        if x is None or y is None:
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "INVALID_ARGUMENT",
                    "message": "x and y must be integers",
                },
            )

        w, h = _screen_bounds(gui)
        if x < 0 or y < 0 or x >= w or y >= h:
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "OUT_OF_BOUNDS",
                    "message": f"({x},{y}) is outside the screen ({w}x{h}).",
                },
            )

        try:
            gui.doubleClick(x=x, y=y)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "DOUBLE_CLICK_FAILED", "message": str(exc)},
            )

        return ToolResult(success=True, tool=self.name, data={"x": x, "y": y})


# ---------------------------------------------------------------------- #
# Tool: right_click
# ---------------------------------------------------------------------- #
class RightClickTool(Tool):
    name = "right_click"
    description = "Move the mouse to (x, y) and right-click."
    parameters = {
        "type": "object",
        "properties": {
            "x": {"type": "integer"},
            "y": {"type": "integer"},
        },
        "required": ["x", "y"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        gui = _ensure_pyautogui()
        if gui is None:
            return _platform_error(self.name)

        x = _safe_int(kwargs.get("x"), None)  # type: ignore
        y = _safe_int(kwargs.get("y"), None)  # type: ignore
        if x is None or y is None:
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "INVALID_ARGUMENT",
                    "message": "x and y must be integers",
                },
            )

        w, h = _screen_bounds(gui)
        if x < 0 or y < 0 or x >= w or y >= h:
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "OUT_OF_BOUNDS",
                    "message": f"({x},{y}) is outside the screen ({w}x{h}).",
                },
            )

        try:
            gui.rightClick(x=x, y=y)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "RIGHT_CLICK_FAILED", "message": str(exc)},
            )

        return ToolResult(success=True, tool=self.name, data={"x": x, "y": y})


# ---------------------------------------------------------------------- #
# Tool: scroll
# ---------------------------------------------------------------------- #
class ScrollTool(Tool):
    name = "scroll"
    description = (
        "Scroll vertically (positive = up, negative = down). "
        "Optionally move the mouse to (x, y) first."
    )
    parameters = {
        "type": "object",
        "properties": {
            "amount": {
                "type": "integer",
                "description": "Scroll clicks; positive=up, negative=down.",
            },
            "x": {"type": "integer"},
            "y": {"type": "integer"},
        },
        "required": ["amount"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        gui = _ensure_pyautogui()
        if gui is None:
            return _platform_error(self.name)

        amount = _safe_int(kwargs.get("amount"), None)  # type: ignore
        if amount is None:
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "INVALID_ARGUMENT",
                    "message": "amount must be an integer",
                },
            )
        if amount == 0 or abs(amount) > 1000:
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "INVALID_ARGUMENT",
                    "message": "amount must be non-zero and within ±1000",
                },
            )

        # Optional coordinates
        x = kwargs.get("x")
        y = kwargs.get("y")
        if x is not None and y is not None:
            x_i = _safe_int(x, None)  # type: ignore
            y_i = _safe_int(y, None)  # type: ignore
            if x_i is None or y_i is None:
                return ToolResult(
                    success=False,
                    tool=self.name,
                    error={
                        "code": "INVALID_ARGUMENT",
                        "message": "x and y must be integers when provided",
                    },
                )
            w, h = _screen_bounds(gui)
            if x_i < 0 or y_i < 0 or x_i >= w or y_i >= h:
                return ToolResult(
                    success=False,
                    tool=self.name,
                    error={
                        "code": "OUT_OF_BOUNDS",
                        "message": f"({x_i},{y_i}) is outside the screen ({w}x{h}).",
                    },
                )
            gui.moveTo(x_i, y_i, duration=0.1)

        try:
            gui.scroll(amount)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "SCROLL_FAILED", "message": str(exc)},
            )

        return ToolResult(success=True, tool=self.name, data={"amount": amount})
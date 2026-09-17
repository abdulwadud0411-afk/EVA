"""
Window management tools (Phase 3).

Tools:
    - list_windows
    - get_active_window
    - focus_window
    - minimize_window
    - maximize_window
    - restore_window
    - close_window
    - move_window
    - resize_window

Uses pywin32 (win32gui, win32con, win32process) to talk to the
Windows window manager. All operations are window-level only —
no files, no shell, no registry.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from app.core.logger import get_logger
from app.tools.base import Tool, ToolResult, RiskLevel

logger = get_logger(__name__)

# ---- pywin32 imports are optional at import time -------------------------
# On non-Windows dev machines (or if pywin32 is missing), the module still
# imports cleanly and tools return a clear error when executed.
try:
    import win32gui  # type: ignore
    import win32con  # type: ignore
    _WIN32_AVAILABLE = True
except Exception:  # noqa: BLE001
    win32gui = None  # type: ignore
    win32con = None  # type: ignore
    _WIN32_AVAILABLE = False


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #
def _ensure_windows() -> Optional[ToolResult]:
    if not _WIN32_AVAILABLE:
        return ToolResult(
            success=False,
            tool="",
            error={
                "code": "PLATFORM_UNSUPPORTED",
                "message": "Window tools require Windows and pywin32.",
            },
        )
    return None


def _enum_windows() -> List[Dict[str, Any]]:
    """Return a list of visible top-level windows."""
    windows: List[Dict[str, Any]] = []

    def _cb(hwnd: int, _extra: Any) -> bool:
        if not win32gui.IsWindowVisible(hwnd):  # type: ignore
            return True
        title = win32gui.GetWindowText(hwnd)  # type: ignore
        if not title:
            return True
        try:
            rect = win32gui.GetWindowRect(hwnd)  # type: ignore
        except Exception:  # noqa: BLE001
            rect = (0, 0, 0, 0)
        windows.append(
            {
                "hwnd": int(hwnd),
                "title": title,
                "x": rect[0],
                "y": rect[1],
                "width": rect[2] - rect[0],
                "height": rect[3] - rect[1],
                "is_minimized": bool(win32gui.IsIconic(hwnd)),  # type: ignore
                "is_maximized": bool(win32gui.IsZoomed(hwnd)),  # type: ignore
            }
        )
        return True

    win32gui.EnumWindows(_cb, None)  # type: ignore
    return windows


def _find_window_by_title(title_query: str) -> Optional[int]:
    """Find a window whose title contains `title_query` (case-insensitive)."""
    if not title_query:
        return None
    q = title_query.lower()
    for w in _enum_windows():
        if q in w["title"].lower():
            return w["hwnd"]
    return None


# ---------------------------------------------------------------------- #
# Tool: list_windows
# ---------------------------------------------------------------------- #
class ListWindowsTool(Tool):
    name = "list_windows"
    description = (
        "List all visible top-level windows on the PC. "
        "Returns hwnd, title, position, size, and state."
    )
    parameters = {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Maximum number of windows to return (default 50).",
            },
        },
        "required": [],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        err = _ensure_windows()
        if err is not None:
            err.tool = self.name
            return err

        try:
            limit = int(kwargs.get("limit", 50))
        except (TypeError, ValueError):
            limit = 50
        if limit <= 0 or limit > 500:
            limit = 50

        try:
            windows = _enum_windows()[:limit]
        except Exception as exc:  # noqa: BLE001
            logger.error("list_windows_failed", error=str(exc))
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "ENUM_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"count": len(windows), "windows": windows},
        )


# ---------------------------------------------------------------------- #
# Tool: get_active_window
# ---------------------------------------------------------------------- #
class GetActiveWindowTool(Tool):
    name = "get_active_window"
    description = "Return the currently focused (active) window."
    parameters = {"type": "object", "properties": {}, "required": []}
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        err = _ensure_windows()
        if err is not None:
            err.tool = self.name
            return err

        try:
            hwnd = win32gui.GetForegroundWindow()  # type: ignore
            if not hwnd:
                return ToolResult(
                    success=False,
                    tool=self.name,
                    error={"code": "NO_ACTIVE_WINDOW", "message": "No active window."},
                )
            title = win32gui.GetWindowText(hwnd)  # type: ignore
            rect = win32gui.GetWindowRect(hwnd)  # type: ignore
            return ToolResult(
                success=True,
                tool=self.name,
                data={
                    "hwnd": int(hwnd),
                    "title": title,
                    "x": rect[0],
                    "y": rect[1],
                    "width": rect[2] - rect[0],
                    "height": rect[3] - rect[1],
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("get_active_window_failed", error=str(exc))
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "QUERY_FAILED", "message": str(exc)},
            )


# ---------------------------------------------------------------------- #
# Tool: focus_window
# ---------------------------------------------------------------------- #
class FocusWindowTool(Tool):
    name = "focus_window"
    description = "Bring a window to the foreground by title substring."
    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Window title substring."},
            "title_contains": {"type": "string", "description": "Alias for `title`."},
        },
        "required": [],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        err = _ensure_windows()
        if err is not None:
            err.tool = self.name
            return err

        title = str(kwargs.get("title") or kwargs.get("title_contains") or "").strip()
        if not title:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "title is required"},
            )

        hwnd = _find_window_by_title(title)
        if hwnd is None:
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "WINDOW_NOT_FOUND",
                    "message": f"No window matching '{title}'.",
                },
            )

        try:
            # Restore if minimized, then bring to front.
            if win32gui.IsIconic(hwnd):  # type: ignore
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)  # type: ignore
            win32gui.SetForegroundWindow(hwnd)  # type: ignore
        except Exception as exc:  # noqa: BLE001
            logger.error("focus_window_failed", error=str(exc))
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "FOCUS_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"hwnd": hwnd, "title": win32gui.GetWindowText(hwnd)},  # type: ignore
        )


# ---------------------------------------------------------------------- #
# Tool: minimize_window
# ---------------------------------------------------------------------- #
class MinimizeWindowTool(Tool):
    name = "minimize_window"
    description = "Minimize a window by title substring."
    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
        },
        "required": ["title"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        err = _ensure_windows()
        if err is not None:
            err.tool = self.name
            return err

        title = str(kwargs.get("title", "")).strip()
        if not title:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "title is required"},
            )

        hwnd = _find_window_by_title(title)
        if hwnd is None:
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "WINDOW_NOT_FOUND",
                    "message": f"No window matching '{title}'.",
                },
            )

        try:
            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)  # type: ignore
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "MINIMIZE_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"hwnd": hwnd, "state": "minimized"},
        )


# ---------------------------------------------------------------------- #
# Tool: maximize_window
# ---------------------------------------------------------------------- #
class MaximizeWindowTool(Tool):
    name = "maximize_window"
    description = "Maximize a window by title substring."
    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
        },
        "required": ["title"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        err = _ensure_windows()
        if err is not None:
            err.tool = self.name
            return err

        title = str(kwargs.get("title", "")).strip()
        if not title:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "title is required"},
            )

        hwnd = _find_window_by_title(title)
        if hwnd is None:
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "WINDOW_NOT_FOUND",
                    "message": f"No window matching '{title}'.",
                },
            )

        try:
            win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)  # type: ignore
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "MAXIMIZE_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"hwnd": hwnd, "state": "maximized"},
        )


# ---------------------------------------------------------------------- #
# Tool: restore_window
# ---------------------------------------------------------------------- #
class RestoreWindowTool(Tool):
    name = "restore_window"
    description = "Restore a minimized or maximized window to normal size."
    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
        },
        "required": ["title"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        err = _ensure_windows()
        if err is not None:
            err.tool = self.name
            return err

        title = str(kwargs.get("title", "")).strip()
        if not title:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "title is required"},
            )

        hwnd = _find_window_by_title(title)
        if hwnd is None:
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "WINDOW_NOT_FOUND",
                    "message": f"No window matching '{title}'.",
                },
            )

        try:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)  # type: ignore
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "RESTORE_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"hwnd": hwnd, "state": "normal"},
        )


# ---------------------------------------------------------------------- #
# Tool: close_window
# ---------------------------------------------------------------------- #
class CloseWindowTool(Tool):
    name = "close_window"
    description = (
        "Close a window by title substring. This sends a normal close "
        "request (as if the user clicked the X button)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
        },
        "required": ["title"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = True

    async def run(self, **kwargs: Any) -> ToolResult:
        err = _ensure_windows()
        if err is not None:
            err.tool = self.name
            return err

        title = str(kwargs.get("title", "")).strip()
        if not title:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "title is required"},
            )

        hwnd = _find_window_by_title(title)
        if hwnd is None:
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "WINDOW_NOT_FOUND",
                    "message": f"No window matching '{title}'.",
                },
            )

        try:
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)  # type: ignore
            time.sleep(0.3)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "CLOSE_FAILED", "message": str(exc)},
            )

        still_open = win32gui.IsWindow(hwnd)  # type: ignore
        return ToolResult(
            success=True,
            tool=self.name,
            data={
                "hwnd": hwnd,
                "still_open": bool(still_open),
                "note": (
                    "Close request sent."
                    if not still_open
                    else "Close request sent; window may prompt to save."
                ),
            },
        )


# ---------------------------------------------------------------------- #
# Tool: move_window
# ---------------------------------------------------------------------- #
class MoveWindowTool(Tool):
    name = "move_window"
    description = "Move a window to the given (x, y) position."
    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "x": {"type": "integer"},
            "y": {"type": "integer"},
        },
        "required": ["title", "x", "y"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        err = _ensure_windows()
        if err is not None:
            err.tool = self.name
            return err

        title = str(kwargs.get("title", "")).strip()
        try:
            x = int(kwargs.get("x"))
            y = int(kwargs.get("y"))
        except (TypeError, ValueError):
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "INVALID_ARGUMENT",
                    "message": "x and y must be integers",
                },
            )

        hwnd = _find_window_by_title(title)
        if hwnd is None:
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "WINDOW_NOT_FOUND",
                    "message": f"No window matching '{title}'.",
                },
            )

        try:
            rect = win32gui.GetWindowRect(hwnd)  # type: ignore
            width = rect[2] - rect[0]
            height = rect[3] - rect[1]
            win32gui.MoveWindow(hwnd, x, y, width, height, True)  # type: ignore
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "MOVE_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"hwnd": hwnd, "x": x, "y": y},
        )


# ---------------------------------------------------------------------- #
# Tool: resize_window
# ---------------------------------------------------------------------- #
class ResizeWindowTool(Tool):
    name = "resize_window"
    description = "Resize a window to the given width and height."
    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "width": {"type": "integer"},
            "height": {"type": "integer"},
        },
        "required": ["title", "width", "height"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        err = _ensure_windows()
        if err is not None:
            err.tool = self.name
            return err

        title = str(kwargs.get("title", "")).strip()
        try:
            width = int(kwargs.get("width"))
            height = int(kwargs.get("height"))
        except (TypeError, ValueError):
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "INVALID_ARGUMENT",
                    "message": "width and height must be integers",
                },
            )

        if width <= 0 or height <= 0:
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "INVALID_ARGUMENT",
                    "message": "width and height must be positive",
                },
            )

        hwnd = _find_window_by_title(title)
        if hwnd is None:
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "WINDOW_NOT_FOUND",
                    "message": f"No window matching '{title}'.",
                },
            )

        try:
            rect = win32gui.GetWindowRect(hwnd)  # type: ignore
            win32gui.MoveWindow(hwnd, rect[0], rect[1], width, height, True)  # type: ignore
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "RESIZE_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"hwnd": hwnd, "width": width, "height": height},
        )
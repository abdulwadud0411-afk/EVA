"""
Tests for Phase 3 window tools.

We mock pywin32 (win32gui, win32con) so the tests are fully offline
and platform-independent. On real Windows they exercise the same
code paths that the live tools use.
"""
from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

from app.tools.base import ToolResult
from app.tools.registry import ToolRegistry


# ---------------------------------------------------------------------- #
# Fixtures
# ---------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def clean_registry():
    ToolRegistry.clear()
    yield
    ToolRegistry.clear()


@pytest.fixture
def fake_windows() -> List[Dict[str, Any]]:
    """Two visible windows with distinct titles."""
    return [
        {
            "hwnd": 1001,
            "title": "Notepad - Untitled",
            "x": 100, "y": 100, "width": 800, "height": 600,
            "is_minimized": False, "is_maximized": False,
        },
        {
            "hwnd": 1002,
            "title": "Chrome - YouTube",
            "x": 200, "y": 200, "width": 1200, "height": 800,
            "is_minimized": False, "is_maximized": True,
        },
    ]


@pytest.fixture
def mock_win32(fake_windows, monkeypatch):
    """
    Patch the module-level pywin32 handles used by window_tools.

    We also patch the helpers `_enum_windows` and `_find_window_by_title`
    implicitly by mocking win32gui.EnumWindows etc. But since our code
    calls those helpers directly, mocking them is simpler and faster.
    """
    import app.tools.window_tools as wt

    monkeypatch.setattr(wt, "_WIN32_AVAILABLE", True)

    # _enum_windows returns our fake list
    monkeypatch.setattr(wt, "_enum_windows", lambda: list(fake_windows))

    # _find_window_by_title: match substring
    def _find(query: str):
        q = query.lower()
        for w in fake_windows:
            if q in w["title"].lower():
                return w["hwnd"]
        return None
    monkeypatch.setattr(wt, "_find_window_by_title", _find)

    # Build a fake win32gui module
    fake_gui = MagicMock()
    fake_gui.IsWindowVisible.return_value = True
    fake_gui.GetWindowText.side_effect = lambda hwnd: {
        1001: "Notepad - Untitled",
        1002: "Chrome - YouTube",
    }.get(hwnd, "")
    fake_gui.GetWindowRect.side_effect = lambda hwnd: {
        1001: (100, 100, 900, 700),
        1002: (200, 200, 1400, 1000),
    }.get(hwnd, (0, 0, 0, 0))
    fake_gui.IsIconic.return_value = False
    fake_gui.IsZoomed.side_effect = lambda hwnd: hwnd == 1002
    fake_gui.GetForegroundWindow.return_value = 1001
    fake_gui.IsWindow.return_value = False
    fake_gui.ShowWindow.return_value = None
    fake_gui.SetForegroundWindow.return_value = None
    fake_gui.MoveWindow.return_value = None
    fake_gui.PostMessage.return_value = None

    fake_con = MagicMock()
    fake_con.SW_MINIMIZE = 6
    fake_con.SW_MAXIMIZE = 3
    fake_con.SW_RESTORE = 9
    fake_con.WM_CLOSE = 16

    monkeypatch.setattr(wt, "win32gui", fake_gui)
    monkeypatch.setattr(wt, "win32con", fake_con)
    return wt


# ---------------------------------------------------------------------- #
# list_windows
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_list_windows(mock_win32):
    from app.tools.window_tools import ListWindowsTool
    result = await ListWindowsTool().run()
    assert result.success is True
    assert result.data["count"] == 2
    titles = [w["title"] for w in result.data["windows"]]
    assert "Notepad - Untitled" in titles
    assert "Chrome - YouTube" in titles


@pytest.mark.asyncio
async def test_list_windows_respects_limit(mock_win32):
    from app.tools.window_tools import ListWindowsTool
    result = await ListWindowsTool().run(limit=1)
    assert result.success is True
    assert result.data["count"] == 1


# ---------------------------------------------------------------------- #
# get_active_window
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_get_active_window(mock_win32):
    from app.tools.window_tools import GetActiveWindowTool
    result = await GetActiveWindowTool().run()
    assert result.success is True
    assert result.data["hwnd"] == 1001
    assert "Notepad" in result.data["title"]


# ---------------------------------------------------------------------- #
# focus_window
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_focus_window_success(mock_win32):
    from app.tools.window_tools import FocusWindowTool
    result = await FocusWindowTool().run(title="chrome")
    assert result.success is True
    assert result.data["hwnd"] == 1002


@pytest.mark.asyncio
async def test_focus_window_not_found(mock_win32):
    from app.tools.window_tools import FocusWindowTool
    result = await FocusWindowTool().run(title="does-not-exist")
    assert result.success is False
    assert result.error["code"] == "WINDOW_NOT_FOUND"


# ---------------------------------------------------------------------- #
# minimize / maximize / restore
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_minimize_window(mock_win32):
    from app.tools.window_tools import MinimizeWindowTool
    result = await MinimizeWindowTool().run(title="notepad")
    assert result.success is True
    assert result.data["state"] == "minimized"


@pytest.mark.asyncio
async def test_maximize_window(mock_win32):
    from app.tools.window_tools import MaximizeWindowTool
    result = await MaximizeWindowTool().run(title="notepad")
    assert result.success is True
    assert result.data["state"] == "maximized"


@pytest.mark.asyncio
async def test_restore_window(mock_win32):
    from app.tools.window_tools import RestoreWindowTool
    result = await RestoreWindowTool().run(title="chrome")
    assert result.success is True
    assert result.data["state"] == "normal"


# ---------------------------------------------------------------------- #
# close_window
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_close_window(mock_win32):
    from app.tools.window_tools import CloseWindowTool
    result = await CloseWindowTool().run(title="notepad")
    assert result.success is True
    assert "still_open" in result.data


# ---------------------------------------------------------------------- #
# move_window
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_move_window(mock_win32):
    from app.tools.window_tools import MoveWindowTool
    result = await MoveWindowTool().run(title="notepad", x=50, y=50)
    assert result.success is True
    assert result.data["x"] == 50
    assert result.data["y"] == 50


@pytest.mark.asyncio
async def test_move_window_bad_args(mock_win32):
    from app.tools.window_tools import MoveWindowTool
    result = await MoveWindowTool().run(title="notepad", x="abc", y=50)
    assert result.success is False
    assert result.error["code"] == "INVALID_ARGUMENT"


# ---------------------------------------------------------------------- #
# resize_window
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_resize_window(mock_win32):
    from app.tools.window_tools import ResizeWindowTool
    result = await ResizeWindowTool().run(title="notepad", width=640, height=480)
    assert result.success is True
    assert result.data["width"] == 640
    assert result.data["height"] == 480


@pytest.mark.asyncio
async def test_resize_window_negative(mock_win32):
    from app.tools.window_tools import ResizeWindowTool
    result = await ResizeWindowTool().run(title="notepad", width=-10, height=100)
    assert result.success is False
    assert result.error["code"] == "INVALID_ARGUMENT"


# ---------------------------------------------------------------------- #
# Platform guard
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_window_tools_require_windows(monkeypatch):
    import app.tools.window_tools as wt
    monkeypatch.setattr(wt, "_WIN32_AVAILABLE", False)
    from app.tools.window_tools import ListWindowsTool
    result = await ListWindowsTool().run()
    assert result.success is False
    assert result.error["code"] == "PLATFORM_UNSUPPORTED"


# ---------------------------------------------------------------------- #
# Registration
# ---------------------------------------------------------------------- #
def test_all_phase3_tools_registered():
    import importlib
    import app.tools as tools_pkg
    importlib.reload(tools_pkg)

    names = set(ToolRegistry.list_tools())
    expected_phase3 = {
        "list_windows",
        "get_active_window",
        "focus_window",
        "minimize_window",
        "maximize_window",
        "restore_window",
        "close_window",
        "move_window",
        "resize_window",
    }
    missing = expected_phase3 - names
    assert not missing, f"Missing tools: {missing}"
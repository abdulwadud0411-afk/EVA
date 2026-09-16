"""Tests for dynamic tool selection (Optimization Patch)."""
from __future__ import annotations

import pytest

# Ensure all tools are registered
import app.tools  # noqa: F401

from app.agent.tool_selector import select_tool_schemas
from app.tools.registry import ToolRegistry


@pytest.fixture(autouse=True)
def ensure_tools_registered():
    """Re-register all tools before each test (isolation-safe)."""
    # Clear then reload the tools package so registration runs fresh
    import importlib
    import app.tools as tools_pkg
    ToolRegistry.clear()
    importlib.reload(tools_pkg)
    yield
    ToolRegistry.clear()


def _names(schemas):
    return {s["function"]["name"] for s in schemas}


def test_youtube_selects_browser_tools():
    schemas = select_tool_schemas("open youtube and search for gta 6")
    names = _names(schemas)
    assert "open_url" in names or "search_web" in names
    assert "browser_open" in names
    assert len(names) < len(ToolRegistry.list_tools())


def test_volume_selects_media_tools():
    schemas = select_tool_schemas("increase volume")
    names = _names(schemas)
    assert "volume_up" in names


def test_screenshot_selects_screen_tools():
    schemas = select_tool_schemas("take a screenshot of my screen")
    names = _names(schemas)
    assert "take_screenshot" in names


def test_window_selects_window_tools():
    schemas = select_tool_schemas("minimize the chrome window")
    names = _names(schemas)
    assert "minimize_window" in names


def test_clipboard_selects_clipboard_tools():
    schemas = select_tool_schemas("copy this to clipboard")
    names = _names(schemas)
    assert "get_clipboard_text" in names or "set_clipboard_text" in names


def test_keyboard_selects_keyboard_tools():
    schemas = select_tool_schemas("press ctrl+s")
    names = _names(schemas)
    assert "hotkey" in names or "press_key" in names


def test_mouse_selects_mouse_tools():
    schemas = select_tool_schemas("click the button at 500 300")
    names = _names(schemas)
    assert "click" in names


def test_unknown_command_falls_back_to_all():
    schemas = select_tool_schemas("what is the meaning of life")
    names = _names(schemas)
    all_names = set(ToolRegistry.list_tools())
    assert names == all_names


def test_complex_command_includes_multiple_groups():
    schemas = select_tool_schemas("open youtube then take a screenshot")
    names = _names(schemas)
    assert "open_url" in names or "browser_open" in names
    assert "take_screenshot" in names


def test_empty_input_falls_back_to_all():
    schemas = select_tool_schemas("")
    all_names = set(ToolRegistry.list_tools())
    assert _names(schemas) == all_names
"""
Tests for Phase 4 keyboard and mouse tools.

All pyautogui calls are mocked — the tests run fully offline and
on any platform.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.tools.registry import ToolRegistry


@pytest.fixture(autouse=True)
def clean_registry():
    ToolRegistry.clear()
    yield
    ToolRegistry.clear()


@pytest.fixture
def mock_keyboard(monkeypatch):
    """Patch pyautogui in keyboard_tools."""
    import app.tools.keyboard_tools as kt

    fake = MagicMock()
    fake.FAILSAFE = True
    fake.PAUSE = 0.0
    monkeypatch.setattr(kt, "_PYAUTOGUI_AVAILABLE", True)
    monkeypatch.setattr(kt, "pyautogui", fake)
    return kt, fake


@pytest.fixture
def mock_mouse(monkeypatch):
    """Patch pyautogui in mouse_tools."""
    import app.tools.mouse_tools as mt

    fake = MagicMock()
    fake.FAILSAFE = True
    fake.PAUSE = 0.0
    fake.size.return_value = (1920, 1080)
    monkeypatch.setattr(mt, "_PYAUTOGUI_AVAILABLE", True)
    monkeypatch.setattr(mt, "pyautogui", fake)
    return mt, fake


# ---------------------------------------------------------------------- #
# Keyboard tools
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_press_key_success(mock_keyboard):
    kt, fake = mock_keyboard
    result = await kt.PressKeyTool().run(key="enter")
    assert result.success is True
    fake.press.assert_called_once_with("enter", presses=1)


@pytest.mark.asyncio
async def test_press_key_with_count(mock_keyboard):
    kt, fake = mock_keyboard
    result = await kt.PressKeyTool().run(key="tab", presses=3)
    assert result.success is True
    fake.press.assert_called_once_with("tab", presses=3)


@pytest.mark.asyncio
async def test_press_key_missing(mock_keyboard):
    kt, _ = mock_keyboard
    result = await kt.PressKeyTool().run()
    assert result.success is False
    assert result.error["code"] == "INVALID_ARGUMENT"


@pytest.mark.asyncio
async def test_hotkey_success(mock_keyboard):
    kt, fake = mock_keyboard
    result = await kt.HotkeyTool().run(keys=["ctrl", "c"])
    assert result.success is True
    fake.hotkey.assert_called_once_with("ctrl", "c")


@pytest.mark.asyncio
async def test_hotkey_bad_args(mock_keyboard):
    kt, _ = mock_keyboard
    result = await kt.HotkeyTool().run(keys="not-a-list")
    assert result.success is False
    assert result.error["code"] == "INVALID_ARGUMENT"


@pytest.mark.asyncio
async def test_type_text_success(mock_keyboard):
    kt, fake = mock_keyboard
    result = await kt.TypeTextTool().run(text="Hello world")
    assert result.success is True
    assert result.data["typed_length"] == 11
    assert fake.typewrite.called


@pytest.mark.asyncio
async def test_type_text_empty(mock_keyboard):
    kt, _ = mock_keyboard
    result = await kt.TypeTextTool().run(text="")
    assert result.success is False


@pytest.mark.asyncio
async def test_key_down_up(mock_keyboard):
    kt, fake = mock_keyboard
    r1 = await kt.KeyDownTool().run(key="shift")
    r2 = await kt.KeyUpTool().run(key="shift")
    assert r1.success is True
    assert r2.success is True
    fake.keyDown.assert_called_once_with("shift")
    fake.keyUp.assert_called_once_with("shift")


@pytest.mark.asyncio
async def test_keyboard_platform_guard(monkeypatch):
    import app.tools.keyboard_tools as kt
    monkeypatch.setattr(kt, "_PYAUTOGUI_AVAILABLE", False)
    result = await kt.PressKeyTool().run(key="enter")
    assert result.success is False
    assert result.error["code"] == "PLATFORM_UNSUPPORTED"


# ---------------------------------------------------------------------- #
# Mouse tools
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_move_mouse_success(mock_mouse):
    mt, fake = mock_mouse
    result = await mt.MoveMouseTool().run(x=500, y=300)
    assert result.success is True
    assert result.data == {"x": 500, "y": 300}
    fake.moveTo.assert_called_once()


@pytest.mark.asyncio
async def test_move_mouse_out_of_bounds(mock_mouse):
    mt, _ = mock_mouse
    result = await mt.MoveMouseTool().run(x=9999, y=300)
    assert result.success is False
    assert result.error["code"] == "OUT_OF_BOUNDS"


@pytest.mark.asyncio
async def test_move_mouse_bad_args(mock_mouse):
    mt, _ = mock_mouse
    result = await mt.MoveMouseTool().run(x="abc", y=300)
    assert result.success is False
    assert result.error["code"] == "INVALID_ARGUMENT"


@pytest.mark.asyncio
async def test_click_success(mock_mouse):
    mt, fake = mock_mouse
    result = await mt.ClickTool().run(x=100, y=200)
    assert result.success is True
    fake.click.assert_called_once_with(x=100, y=200)


@pytest.mark.asyncio
async def test_double_click_success(mock_mouse):
    mt, fake = mock_mouse
    result = await mt.DoubleClickTool().run(x=50, y=50)
    assert result.success is True
    fake.doubleClick.assert_called_once_with(x=50, y=50)


@pytest.mark.asyncio
async def test_right_click_success(mock_mouse):
    mt, fake = mock_mouse
    result = await mt.RightClickTool().run(x=50, y=50)
    assert result.success is True
    fake.rightClick.assert_called_once_with(x=50, y=50)


@pytest.mark.asyncio
async def test_scroll_success(mock_mouse):
    mt, fake = mock_mouse
    result = await mt.ScrollTool().run(amount=-5)
    assert result.success is True
    fake.scroll.assert_called_once_with(-5)


@pytest.mark.asyncio
async def test_scroll_with_coords(mock_mouse):
    mt, fake = mock_mouse
    result = await mt.ScrollTool().run(amount=3, x=400, y=300)
    assert result.success is True
    assert fake.moveTo.called
    assert fake.scroll.called


@pytest.mark.asyncio
async def test_scroll_zero_rejected(mock_mouse):
    mt, _ = mock_mouse
    result = await mt.ScrollTool().run(amount=0)
    assert result.success is False


@pytest.mark.asyncio
async def test_mouse_platform_guard(monkeypatch):
    import app.tools.mouse_tools as mt
    monkeypatch.setattr(mt, "_PYAUTOGUI_AVAILABLE", False)
    result = await mt.ClickTool().run(x=100, y=100)
    assert result.success is False
    assert result.error["code"] == "PLATFORM_UNSUPPORTED"


# ---------------------------------------------------------------------- #
# Registration
# ---------------------------------------------------------------------- #
def test_all_phase4_tools_registered():
    import importlib
    import app.tools as tools_pkg
    importlib.reload(tools_pkg)

    names = set(ToolRegistry.list_tools())
    expected = {
        "press_key", "hotkey", "type_text", "key_down", "key_up",
        "move_mouse", "click", "double_click", "right_click", "scroll",
    }
    missing = expected - names
    assert not missing, f"Missing Phase 4 tools: {missing}"
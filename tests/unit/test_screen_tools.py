"""Tests for Phase 5 screen tools."""
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
def mock_screen(monkeypatch, tmp_path):
    """Patch pyautogui + ConfigManager.get_data_dir for isolation."""
    import app.tools.screen_tools as st

    fake_img = MagicMock()
    fake_img.size = (1920, 1080)
    fake_img.save = MagicMock()

    fake_gui = MagicMock()
    fake_gui.screenshot.return_value = fake_img
    fake_gui.size.return_value = (1920, 1080)

    monkeypatch.setattr(st, "_PYAUTOGUI_AVAILABLE", True)
    monkeypatch.setattr(st, "_PIL_AVAILABLE", True)
    monkeypatch.setattr(st, "pyautogui", fake_gui)
    monkeypatch.setattr(st.ConfigManager, "get_data_dir", classmethod(lambda cls: tmp_path))

    return st, fake_gui, fake_img, tmp_path


@pytest.mark.asyncio
async def test_take_screenshot_saves_png(mock_screen):
    st, gui, img, tmp = mock_screen
    result = await st.TakeScreenshotTool().run()
    assert result.success is True
    assert result.data["width"] == 1920
    assert result.data["height"] == 1080
    assert result.data["path"].endswith(".png")
    assert img.save.called


@pytest.mark.asyncio
async def test_get_screen_size(mock_screen):
    st, _, _, _ = mock_screen
    result = await st.GetScreenSizeTool().run()
    assert result.success is True
    assert result.data == {"width": 1920, "height": 1080}


@pytest.mark.asyncio
async def test_crop_screenshot_success(mock_screen):
    st, _, _, _ = mock_screen
    result = await st.CropScreenshotTool().run(x=100, y=100, width=400, height=300)
    assert result.success is True
    assert result.data["region"] == {"x": 100, "y": 100, "width": 400, "height": 300}


@pytest.mark.asyncio
async def test_crop_screenshot_invalid_args(mock_screen):
    st, _, _, _ = mock_screen
    result = await st.CropScreenshotTool().run(x="a", y=100, width=400, height=300)
    assert result.success is False
    assert result.error["code"] == "INVALID_ARGUMENT"


@pytest.mark.asyncio
async def test_crop_screenshot_negative_size(mock_screen):
    st, _, _, _ = mock_screen
    result = await st.CropScreenshotTool().run(x=0, y=0, width=-10, height=100)
    assert result.success is False


@pytest.mark.asyncio
async def test_platform_guard(monkeypatch):
    import app.tools.screen_tools as st
    monkeypatch.setattr(st, "_PYAUTOGUI_AVAILABLE", False)
    result = await st.TakeScreenshotTool().run()
    assert result.success is False
    assert result.error["code"] == "PLATFORM_UNSUPPORTED"
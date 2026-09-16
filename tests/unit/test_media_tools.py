"""Tests for Phase 5 media tools."""
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
def mock_media(monkeypatch):
    import app.tools.media_tools as mt

    # Mock pyautogui
    fake_gui = MagicMock()
    monkeypatch.setattr(mt, "_PYAUTOGUI_AVAILABLE", True)
    monkeypatch.setattr(mt, "pyautogui", fake_gui)

    # Mock pycaw path by faking _get_volume_interface
    fake_vol = MagicMock()
    fake_vol.GetMasterVolumeLevelScalar.return_value = 0.5
    fake_vol.GetMute.return_value = False
    fake_vol.SetMasterVolumeLevelScalar = MagicMock()
    fake_vol.SetMute = MagicMock()

    monkeypatch.setattr(mt, "_PYCAW_AVAILABLE", True)
    monkeypatch.setattr(mt, "_get_volume_interface", lambda: fake_vol)

    return mt, fake_gui, fake_vol


@pytest.mark.asyncio
async def test_volume_up(mock_media):
    mt, _, vol = mock_media
    result = await mt.VolumeUpTool().run()
    assert result.success is True
    assert vol.SetMasterVolumeLevelScalar.called
    assert result.data["new_level_percent"] == 60


@pytest.mark.asyncio
async def test_volume_up_step(mock_media):
    mt, _, vol = mock_media
    result = await mt.VolumeUpTool().run(step=25)
    assert result.success is True
    assert result.data["new_level_percent"] == 75


@pytest.mark.asyncio
async def test_volume_down(mock_media):
    mt, _, vol = mock_media
    result = await mt.VolumeDownTool().run()
    assert result.success is True
    assert result.data["new_level_percent"] == 40


@pytest.mark.asyncio
async def test_mute_toggle(mock_media):
    mt, _, vol = mock_media
    vol.GetMute.return_value = False
    result = await mt.MuteTool().run(action="toggle")
    assert result.success is True
    assert result.data["muted"] is True


@pytest.mark.asyncio
async def test_mute_on(mock_media):
    mt, _, vol = mock_media
    result = await mt.MuteTool().run(action="on")
    assert result.success is True
    assert result.data["muted"] is True


@pytest.mark.asyncio
async def test_media_control_play_pause(mock_media):
    mt, gui, _ = mock_media
    result = await mt.MediaControlTool().run(action="play_pause")
    assert result.success is True
    gui.press.assert_called_once_with("playpause")


@pytest.mark.asyncio
async def test_media_control_next(mock_media):
    mt, gui, _ = mock_media
    result = await mt.MediaControlTool().run(action="next")
    assert result.success is True
    gui.press.assert_called_once_with("nexttrack")


@pytest.mark.asyncio
async def test_media_control_invalid(mock_media):
    mt, _, _ = mock_media
    result = await mt.MediaControlTool().run(action="dance")
    assert result.success is False
    assert result.error["code"] == "INVALID_ARGUMENT"


@pytest.mark.asyncio
async def test_volume_platform_guard(monkeypatch):
    import app.tools.media_tools as mt
    monkeypatch.setattr(mt, "_PYCAW_AVAILABLE", False)
    result = await mt.VolumeUpTool().run()
    assert result.success is False
    assert result.error["code"] == "PLATFORM_UNSUPPORTED"


@pytest.mark.asyncio
async def test_media_key_platform_guard(monkeypatch):
    import app.tools.media_tools as mt
    monkeypatch.setattr(mt, "_PYAUTOGUI_AVAILABLE", False)
    result = await mt.MediaControlTool().run(action="play_pause")
    assert result.success is False
    assert result.error["code"] == "PLATFORM_UNSUPPORTED"
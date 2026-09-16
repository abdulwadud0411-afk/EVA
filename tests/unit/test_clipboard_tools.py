"""Tests for Phase 5 clipboard tools."""
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
def mock_clipboard(monkeypatch):
    import app.tools.clipboard_tools as ct

    fake = MagicMock()
    fake.paste.return_value = "hello clipboard"
    fake.copy = MagicMock()

    monkeypatch.setattr(ct, "_PYPERCLIP_AVAILABLE", True)
    monkeypatch.setattr(ct, "pyperclip", fake)
    return ct, fake


@pytest.mark.asyncio
async def test_get_clipboard_text(mock_clipboard):
    ct, fake = mock_clipboard
    result = await ct.GetClipboardTextTool().run()
    assert result.success is True
    assert result.data["text"] == "hello clipboard"
    assert result.data["length"] == 15


@pytest.mark.asyncio
async def test_set_clipboard_text(mock_clipboard):
    ct, fake = mock_clipboard
    result = await ct.SetClipboardTextTool().run(text="new content")
    assert result.success is True
    assert result.data["length"] == 11
    fake.copy.assert_called_once_with("new content")


@pytest.mark.asyncio
async def test_set_clipboard_text_missing(mock_clipboard):
    ct, _ = mock_clipboard
    result = await ct.SetClipboardTextTool().run()
    assert result.success is False
    assert result.error["code"] == "INVALID_ARGUMENT"


@pytest.mark.asyncio
async def test_clear_clipboard(mock_clipboard):
    ct, fake = mock_clipboard
    result = await ct.ClearClipboardTool().run()
    assert result.success is True
    fake.copy.assert_called_once_with("")


@pytest.mark.asyncio
async def test_get_clipboard_info_with_text(mock_clipboard):
    ct, _ = mock_clipboard
    result = await ct.GetClipboardInfoTool().run()
    assert result.success is True
    assert result.data["has_text"] is True
    assert result.data["empty"] is False


@pytest.mark.asyncio
async def test_get_clipboard_info_empty(monkeypatch):
    import app.tools.clipboard_tools as ct
    fake = MagicMock()
    fake.paste.return_value = ""
    monkeypatch.setattr(ct, "_PYPERCLIP_AVAILABLE", True)
    monkeypatch.setattr(ct, "pyperclip", fake)
    result = await ct.GetClipboardInfoTool().run()
    assert result.success is True
    assert result.data["has_text"] is False
    assert result.data["empty"] is True


@pytest.mark.asyncio
async def test_platform_guard(monkeypatch):
    import app.tools.clipboard_tools as ct
    monkeypatch.setattr(ct, "_PYPERCLIP_AVAILABLE", False)
    result = await ct.GetClipboardTextTool().run()
    assert result.success is False
    assert result.error["code"] == "PLATFORM_UNSUPPORTED"
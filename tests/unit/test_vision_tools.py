"""Tests for Phase 6 vision tools."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tools.registry import ToolRegistry


@pytest.fixture(autouse=True)
def clean_registry():
    ToolRegistry.clear()
    yield
    ToolRegistry.clear()


@pytest.fixture
def fake_screenshot(tmp_path, monkeypatch):
    """Patch capture_for_vision in vision_tools to return a temp PNG."""
    import app.tools.vision_tools as vt
    p = tmp_path / "fake.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x")
    monkeypatch.setattr(vt, "capture_for_vision", lambda: p)
    return p


# ---------------------------------------------------------------------- #
# analyze_screen
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_analyze_screen_success(fake_screenshot, monkeypatch):
    import app.tools.vision_tools as vt

    fake_client = MagicMock()
    fake_client.analyze_image = AsyncMock(return_value={
        "text": "A browser with a YouTube tab.",
        "model_used": "deepseek-v4-flash-vision-exp",
    })
    monkeypatch.setattr(vt, "VisionClient", lambda *a, **kw: fake_client)

    from app.tools.vision_tools import AnalyzeScreenTool
    result = await AnalyzeScreenTool().run()
    assert result.success is True
    assert "browser" in result.data["text"]


@pytest.mark.asyncio
async def test_analyze_screen_with_prompt(fake_screenshot, monkeypatch):
    import app.tools.vision_tools as vt

    fake_client = MagicMock()
    fake_client.analyze_image = AsyncMock(return_value={
        "text": "Chrome", "model_used": "x",
    })
    monkeypatch.setattr(vt, "VisionClient", lambda *a, **kw: fake_client)

    from app.tools.vision_tools import AnalyzeScreenTool
    result = await AnalyzeScreenTool().run(prompt="Which app is open?")
    assert result.success is True
    call_args = fake_client.analyze_image.call_args
    # second positional or keyword prompt
    assert call_args.kwargs.get("prompt") == "Which app is open?"


@pytest.mark.asyncio
async def test_analyze_screen_capture_failure(monkeypatch):
    import app.tools.vision_tools as vt
    monkeypatch.setattr(
        vt, "capture_for_vision",
        lambda: (_ for _ in ()).throw(RuntimeError("no display")),
    )

    from app.tools.vision_tools import AnalyzeScreenTool
    result = await AnalyzeScreenTool().run()
    assert result.success is False
    assert result.error["code"] == "CAPTURE_FAILED"


# ---------------------------------------------------------------------- #
# find_ui_element
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_find_ui_element_success(fake_screenshot, monkeypatch):
    import app.tools.vision_tools as vt

    fake_client = MagicMock()
    fake_client.find_element = AsyncMock(return_value={
        "found": True, "element": "Settings", "x": 1742, "y": 86,
        "confidence": 0.94, "reason": "",
    })
    monkeypatch.setattr(vt, "VisionClient", lambda *a, **kw: fake_client)

    from app.tools.vision_tools import FindUiElementTool
    result = await FindUiElementTool().run(element="Settings icon")
    assert result.success is True
    assert result.data["found"] is True
    assert result.data["x"] == 1742
    assert result.data["y"] == 86


@pytest.mark.asyncio
async def test_find_ui_element_not_found(fake_screenshot, monkeypatch):
    import app.tools.vision_tools as vt

    fake_client = MagicMock()
    fake_client.find_element = AsyncMock(return_value={
        "found": False, "element": "Ghost", "x": None, "y": None,
        "confidence": 0.0, "reason": "not visible",
    })
    monkeypatch.setattr(vt, "VisionClient", lambda *a, **kw: fake_client)

    from app.tools.vision_tools import FindUiElementTool
    result = await FindUiElementTool().run(element="Ghost")
    assert result.success is True
    assert result.data["found"] is False


@pytest.mark.asyncio
async def test_find_ui_element_empty_arg(fake_screenshot):
    from app.tools.vision_tools import FindUiElementTool
    result = await FindUiElementTool().run(element="")
    assert result.success is False
    assert result.error["code"] == "INVALID_ARGUMENT"


# ---------------------------------------------------------------------- #
# Registration
# ---------------------------------------------------------------------- #
def test_phase6_tools_registered():
    import importlib
    import app.tools as tools_pkg
    importlib.reload(tools_pkg)

    names = set(ToolRegistry.list_tools())
    assert "analyze_screen" in names
    assert "find_ui_element" in names
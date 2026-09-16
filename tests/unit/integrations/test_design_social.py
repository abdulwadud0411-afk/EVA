"""
Tests for app.tools.integrations.design_social.
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.tools.registry import ToolRegistry
from app.tools.integrations.design_social.figma_tools import (
    FigmaGetFileTool,
    FigmaGetNodeTool,
    FigmaExportImageTool,
    FigmaListProjectsTool,
)
from app.tools.integrations.design_social.capcut_tools import (
    CapCutOpenTool,
    CapCutImportMediaTool,
    CapCutClickTool,
)


def test_design_social_registered():
    names = set(ToolRegistry.list_tools())
    expected = {
        "figma_get_file", "figma_get_node", "figma_export_image",
        "figma_list_projects",
        "capcut_open", "capcut_import_media", "capcut_click",
    }
    missing = expected - names
    assert not missing, f"missing: {missing}"


# ---------------------------------------------------------------------- #
# Figma
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_figma_no_token(monkeypatch):
    monkeypatch.delenv("FIGMA_ACCESS_TOKEN", raising=False)
    r = await FigmaGetFileTool().run(file_key="abc")
    assert r.success is False
    assert r.error["code"] == "NO_TOKEN"


@pytest.mark.asyncio
async def test_figma_get_file_missing_key(monkeypatch):
    monkeypatch.setenv("FIGMA_ACCESS_TOKEN", "test_token")
    r = await FigmaGetFileTool().run(file_key="")
    assert r.success is False


@pytest.mark.asyncio
async def test_figma_get_file_success(monkeypatch):
    monkeypatch.setenv("FIGMA_ACCESS_TOKEN", "test_token")
    fake = MagicMock()
    fake.status_code = 200
    fake.raise_for_status = lambda: None
    fake.json = lambda: {
        "name": "My Design",
        "lastModified": "2026-01-01",
        "version": "123",
    }
    with patch("httpx.AsyncClient.get", return_value=fake):
        r = await FigmaGetFileTool().run(file_key="abc")
    assert r.success is True
    assert r.data["name"] == "My Design"


# ---------------------------------------------------------------------- #
# CapCut
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_capcut_open_no_exe():
    with patch.object(CapCutOpenTool, "_discover_path", return_value=None):
        r = await CapCutOpenTool().run()
    assert r.success is False


@pytest.mark.asyncio
async def test_capcut_import_missing_media(tmp_path):
    r = await CapCutImportMediaTool().run(
        media_paths=[str(tmp_path / "no.mp4")])
    assert r.success is False


@pytest.mark.asyncio
async def test_capcut_click_bad_coords():
    r = await CapCutClickTool().run(x="abc", y=100)
    assert r.success is False
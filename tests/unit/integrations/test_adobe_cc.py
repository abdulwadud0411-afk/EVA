"""
Tests for app.tools.integrations.adobe_cc.

All COM calls mocked via patch('win32com.client').
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.tools.registry import ToolRegistry
from app.tools.integrations.adobe_cc.photoshop_tools import (
    PhotoshopOpenTool,
    PhotoshopRunActionTool,
    PhotoshopExportTool,
)
from app.tools.integrations.adobe_cc.illustrator_tools import (
    IllustratorOpenTool,
    IllustratorExportTool,
    IllustratorRunScriptTool,
)
from app.tools.integrations.adobe_cc.premiere_tools import (
    PremiereOpenProjectTool,
    PremiereImportMediaTool,
    PremiereExportTool,
)
from app.tools.integrations.adobe_cc.after_effects_tools import (
    AfterEffectsOpenProjectTool,
    AfterEffectsAddToRenderQueueTool,
    AfterEffectsRunScriptTool,
)


def test_adobe_cc_registered():
    names = set(ToolRegistry.list_tegistry if False else ToolRegistry.list_tools())
    expected = {
        "photoshop_open", "photoshop_run_action", "photoshop_export",
        "illustrator_open", "illustrator_export", "illustrator_run_script",
        "premiere_open_project", "premiere_import_media", "premiere_export",
        "after_effects_open_project", "after_effects_add_to_render_queue",
        "after_effects_run_script",
    }
    missing = expected - names
    assert not missing, f"missing: {missing}"


# ---------------------------------------------------------------------- #
# Photoshop
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_photoshop_open_missing_file(tmp_path):
    r = await PhotoshopOpenTool().run(file_path=str(tmp_path / "no.psd"))
    assert r.success is False


@pytest.mark.asyncio
async def test_photoshop_open_no_com(tmp_path):
    f = tmp_path / "a.psd"
    f.write_bytes(b"fake")
    with patch("app.tools.integrations.adobe_cc.photoshop_tools._get_photoshop",
               return_value=None):
        r = await PhotoshopOpenTool().run(file_path=str(f))
    assert r.success is False


@pytest.mark.asyncio
async def test_photoshop_open_success(tmp_path):
    f = tmp_path / "a.psd"
    f.write_bytes(b"fake")
    fake_ps = MagicMock()
    with patch("app.tools.integrations.adobe_cc.photoshop_tools._get_photoshop",
               return_value=fake_ps):
        r = await PhotoshopOpenTool().run(file_path=str(f))
    assert r.success is True
    fake_ps.Open.assert_called_once()


@pytest.mark.asyncio
async def test_photoshop_run_action_missing_args():
    r = await PhotoshopRunActionTool().run(action_set="", action_name="")
    assert r.success is False


# ---------------------------------------------------------------------- #
# Illustrator
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_illustrator_open_no_com(tmp_path):
    f = tmp_path / "a.ai"
    f.write_bytes(b"fake")
    with patch("app.tools.integrations.adobe_cc.illustrator_tools._get_illustrator",
               return_value=None):
        r = await IllustratorOpenTool().run(file_path=str(f))
    assert r.success is False


# ---------------------------------------------------------------------- #
# Premiere
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_premiere_open_project_missing(tmp_path):
    r = await PremiereOpenProjectTool().run(
        project_path=str(tmp_path / "no.prproj"))
    assert r.success is False


# ---------------------------------------------------------------------- #
# After Effects
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_after_effects_open_missing(tmp_path):
    r = await AfterEffectsOpenProjectTool().run(
        project_path=str(tmp_path / "no.aep"))
    assert r.success is False


@pytest.mark.asyncio
async def test_after_effects_render_queue_no_com(tmp_path):
    out = tmp_path / "out.mov"
    with patch("app.tools.integrations.adobe_cc.after_effects_tools._get_after_effects",
               return_value=None):
        r = await AfterEffectsAddToRenderQueueTool().run(output_path=str(out))
    assert r.success is False


@pytest.mark.asyncio
async def test_after_effects_run_script_missing(tmp_path):
    r = await AfterEffectsRunScriptTool().run(
        script_path=str(tmp_path / "no.jsx"))
    assert r.success is False
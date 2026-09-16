"""
Tests for design_cad and media_extended integration groups.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.tools.registry import ToolRegistry
from app.tools.integrations.design_cad.autocad_tools import (
    AutoCADOpenTool,
    AutoCADRunScriptTool,
    AutoCADExportPdfTool,
)
from app.tools.integrations.design_cad.fusion360_tools import (
    Fusion360OpenTool,
    Fusion360RunScriptTool,
)
from app.tools.integrations.design_cad.sketchup_tools import (
    SketchUpOpenTool,
    SketchUpExportTool,
)
from app.tools.integrations.media_extended.davinci_resolve_tools import (
    DaVinciOpenProjectTool,
    DaVinciImportMediaTool,
    DaVinciRenderTool,
)
from app.tools.integrations.media_extended.obs_studio_tools import (
    OBSStartRecordingTool,
    OBSStopRecordingTool,
    OBSStartStreamingTool,
    OBSStopStreamingTool,
)


def test_cad_and_media_registered():
    names = set(ToolRegistry.list_tools())
    expected = {
        "autocad_open", "autocad_run_script", "autocad_export_pdf",
        "fusion360_open", "fusion360_run_script",
        "sketchup_open", "sketchup_export",
        "davinci_open_project", "davinci_import_media", "davinci_render",
        "obs_start_recording", "obs_stop_recording",
        "obs_start_streaming", "obs_stop_streaming",
    }
    missing = expected - names
    assert not missing, f"missing: {missing}"


# ---------------------------------------------------------------------- #
# AutoCAD
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_autocad_open_missing_file(tmp_path):
    r = await AutoCADOpenTool().run(drawing_path=str(tmp_path / "no.dwg"))
    assert r.success is False


@pytest.mark.asyncio
async def test_autocad_open_no_com(tmp_path):
    f = tmp_path / "a.dwg"
    f.write_bytes(b"fake")
    with patch("app.tools.integrations.design_cad.autocad_tools._get_autocad",
               return_value=None):
        r = await AutoCADOpenTool().run(drawing_path=str(f))
    assert r.success is False


@pytest.mark.asyncio
async def test_autocad_run_script_missing_commands():
    r = await AutoCADRunScriptTool().run(commands="")
    assert r.success is False


@pytest.mark.asyncio
async def test_autocad_export_no_com(tmp_path):
    out = tmp_path / "out.pdf"
    with patch("app.tools.integrations.design_cad.autocad_tools._get_autocad",
               return_value=None):
        r = await AutoCADExportPdfTool().run(output_path=str(out))
    assert r.success is False


# ---------------------------------------------------------------------- #
# Fusion 360
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_fusion360_open_no_exe():
    with patch.object(Fusion360OpenTool, "_discover_path", return_value=None), \
         patch("app.tools.integrations.design_cad.fusion360_tools._fusion_exe",
               return_value=None):
        r = await Fusion360OpenTool().run()
    assert r.success is False


@pytest.mark.asyncio
async def test_fusion360_run_script_missing(tmp_path):
    r = await Fusion360RunScriptTool().run(
        script_path=str(tmp_path / "no.py"))
    assert r.success is False


# ---------------------------------------------------------------------- #
# SketchUp
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_sketchup_open_no_exe():
    with patch.object(SketchUpOpenTool, "_discover_path", return_value=None), \
         patch("app.tools.integrations.design_cad.sketchup_tools._sketchup_exe",
               return_value=None):
        r = await SketchUpOpenTool().run(file_path="x.skp")
    assert r.success is False


@pytest.mark.asyncio
async def test_sketchup_export_missing(tmp_path):
    r = await SketchUpExportTool().run(
        skp_file=str(tmp_path / "no.skp"),
        ruby_script=str(tmp_path / "no.rb"),
        output_path=str(tmp_path / "out.obj"),
    )
    assert r.success is False


# ---------------------------------------------------------------------- #
# DaVinci Resolve
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_davinci_open_project_missing_name():
    r = await DaVinciOpenProjectTool().run(project_name="")
    assert r.success is False


@pytest.mark.asyncio
async def test_davinci_open_no_module():
    with patch("app.tools.integrations.media_extended.davinci_resolve_tools._get_resolve",
               return_value=None):
        r = await DaVinciOpenProjectTool().run(project_name="Test")
    assert r.success is False


@pytest.mark.asyncio
async def test_davinci_import_missing():
    r = await DaVinciImportMediaTool().run(media_paths=[])
    assert r.success is False


@pytest.mark.asyncio
async def test_davinci_render_no_resolve(tmp_path):
    with patch("app.tools.integrations.media_extended.davinci_resolve_tools._get_resolve",
               return_value=None):
        r = await DaVinciRenderTool().run(output_dir=str(tmp_path))
    assert r.success is False


# ---------------------------------------------------------------------- #
# OBS Studio
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_obs_start_recording_offline():
    with patch("app.tools.integrations.media_extended.obs_studio_tools._obs_request",
               side_effect=RuntimeError("offline")):
        r = await OBSStartRecordingTool().run()
    assert r.success is False


@pytest.mark.asyncio
async def test_obs_stop_recording_offline():
    with patch("app.tools.integrations.media_extended.obs_studio_tools._obs_request",
               side_effect=RuntimeError("offline")):
        r = await OBSStopRecordingTool().run()
    assert r.success is False


@pytest.mark.asyncio
async def test_obs_start_streaming_offline():
    with patch("app.tools.integrations.media_extended.obs_studio_tools._obs_request",
               side_effect=RuntimeError("offline")):
        r = await OBSStartStreamingTool().run()
    assert r.success is False


@pytest.mark.asyncio
async def test_obs_stop_streaming_offline():
    with patch("app.tools.integrations.media_extended.obs_studio_tools._obs_request",
               side_effect=RuntimeError("offline")):
        r = await OBSStopStreamingTool().run()
    assert r.success is False
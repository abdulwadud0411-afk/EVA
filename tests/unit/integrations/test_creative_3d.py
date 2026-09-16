"""
Tests for app.tools.integrations.creative_3d.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.tools.registry import ToolRegistry
from app.tools.integrations.creative_3d.blender_tools import (
    BlenderRunScriptTool,
    BlenderRenderTool,
    BlenderOpenFileTool,
)
from app.tools.integrations.creative_3d.unreal_tools import (
    UnrealPingTool,
    UnrealRunConsoleCommandTool,
    UnrealListActorsTool,
)
from app.tools.integrations.creative_3d.cinema4d_tools import (
    Cinema4DRunScriptTool,
    Cinema4DRenderTool,
)
from app.tools.integrations.creative_3d.comfyui_tools import (
    ComfyUIPingTool,
    ComfyUIListModelsTool,
    ComfyUIListWorkflowsTool,
    ComfyUIRunWorkflowTool,
    ComfyUIQueueStatusTool,
    ComfyUIGetOutputTool,
)


def test_creative_3d_registered():
    names = set(ToolRegistry.list_tools())
    expected = {
        "blender_run_script", "blender_render", "blender_open_file",
        "unreal_ping", "unreal_run_console_command", "unreal_list_actors",
        "cinema4d_run_script", "cinema4d_render",
        "comfyui_ping", "comfyui_list_models", "comfyui_list_workflows",
        "comfyui_run_workflow", "comfyui_queue_status", "comfyui_get_output",
    }
    missing = expected - names
    assert not missing, f"missing: {missing}"


# ---------------------------------------------------------------------- #
# Blender
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_blender_run_script_missing_exe():
    with patch.object(BlenderRunScriptTool, "_discover_path", return_value=None):
        r = await BlenderRunScriptTool().run(script_path="x.py")
    assert r.success is False
    assert r.error["code"] == "APP_NOT_FOUND"


@pytest.mark.asyncio
async def test_blender_run_script_missing_script(tmp_path):
    with patch.object(BlenderRunScriptTool, "_discover_path",
                      return_value="C:/blender.exe"):
        r = await BlenderRunScriptTool().run(script_path=str(tmp_path / "no.py"))
    assert r.success is False


@pytest.mark.asyncio
async def test_blender_run_script_success(tmp_path):
    script = tmp_path / "s.py"
    script.write_text("print('hi')")
    fake = MagicMock(returncode=0, stdout="hi\n", stderr="")
    with patch.object(BlenderRunScriptTool, "_discover_path",
                      return_value="C:/blender.exe"), \
         patch("subprocess.run", return_value=fake):
        r = await BlenderRunScriptTool().run(script_path=str(script))
    assert r.success is True


# ---------------------------------------------------------------------- #
# Unreal
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_unreal_ping_unreachable():
    with patch("httpx.AsyncClient.get", side_effect=Exception("net fail")):
        r = await UnrealPingTool().run()
    assert r.success is False


@pytest.mark.asyncio
async def test_unreal_ping_ok():
    fake = MagicMock()
    fake.status_code = 200
    with patch("httpx.AsyncClient.get", return_value=fake):
        r = await UnrealPingTool().run()
    assert r.success is True


@pytest.mark.asyncio
async def test_unreal_run_console_missing_command():
    r = await UnrealRunConsoleCommandTool().run(command="")
    assert r.success is False


# ---------------------------------------------------------------------- #
# Cinema 4D
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_cinema4d_run_script_missing_exe(tmp_path):
    script = tmp_path / "s.py"
    script.write_text("x")
    with patch.object(Cinema4DRunScriptTool, "_discover_path", return_value=None):
        r = await Cinema4DRunScriptTool().run(script_path=str(script))
    assert r.success is False


# ---------------------------------------------------------------------- #
# ComfyUI
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_comfyui_ping_unreachable():
    with patch("httpx.AsyncClient.get", side_effect=Exception("offline")):
        r = await ComfyUIPingTool().run()
    assert r.success is False
    assert r.error["code"] == "COMFYUI_UNREACHABLE"


@pytest.mark.asyncio
async def test_comfyui_ping_ok():
    fake = MagicMock()
    fake.status_code = 200
    fake.json = lambda: {"system": {"os": "nt"}}
    with patch("httpx.AsyncClient.get", return_value=fake):
        r = await ComfyUIPingTool().run()
    assert r.success is True


@pytest.mark.asyncio
async def test_comfyui_list_workflows(tmp_path):
    from app.core.config_manager import ConfigManager
    workflows_dir = tmp_path / "wf"
    workflows_dir.mkdir()
    (workflows_dir / "a.json").write_text("{}")
    (workflows_dir / "b.json").write_text("{}")

    ConfigManager.load()
    ConfigManager.set("integrations.comfyui.workflows_dir",
                      str(workflows_dir), persist=False)

    r = await ComfyUIListWorkflowsTool().run()
    assert r.success is True
    assert r.data["count"] == 2


@pytest.mark.asyncio
async def test_comfyui_queue_status_offline():
    with patch("httpx.AsyncClient.get", side_effect=Exception("net")):
        r = await ComfyUIQueueStatusTool().run()
    assert r.success is False


@pytest.mark.asyncio
async def test_comfyui_run_workflow_missing_args():
    r = await ComfyUIRunWorkflowTool().run()
    assert r.success is False
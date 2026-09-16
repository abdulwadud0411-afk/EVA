"""
Tests for app.tools.integrations.dev_tools.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.tools.registry import ToolRegistry
from app.tools.integrations.dev_tools.vscode_tools import (
    VSCodeOpenTool,
    VSCodeOpenFolderTool,
    VSCodeInstallExtensionTool,
    VSCodeRunCommandTool,
)
from app.tools.integrations.dev_tools.visual_studio_tools import (
    VisualStudioOpenSolutionTool,
    VisualStudioBuildTool,
)
from app.tools.integrations.dev_tools.android_studio_tools import (
    AndroidStudioOpenProjectTool,
    AndroidStudioRunGradleTool,
)
from app.tools.integrations.dev_tools.xcode_tools import (
    XcodeOpenProjectTool,
    XcodeBuildTool,
)
from app.tools.integrations.dev_tools.unity_tools import (
    UnityOpenProjectTool,
    UnityRunBatchMethodTool,
)
from app.tools.integrations.dev_tools.webstorm_tools import (
    WebStormOpenProjectTool,
)
from app.tools.integrations.dev_tools.flutter_tools import (
    FlutterCreateProjectTool,
    FlutterRunTool,
    FlutterBuildTool,
)
from app.tools.integrations.dev_tools.react_native_tools import (
    ReactNativeInitTool,
    ReactNativeRunAndroidTool,
    ReactNativeRunIosTool,
)
from app.tools.integrations.dev_tools.server_stack_tools import (
    XamppStartTool,
    XamppStopTool,
    WampStartTool,
    WampStopTool,
)
from app.tools.integrations.dev_tools.python_env_tools import (
    PythonCreateVenvTool,
    PythonPipInstallTool,
    PythonRunScriptTool,
)


def test_dev_tools_registered():
    names = set(ToolRegistry.list_tools())
    expected = {
        # VS Code
        "vscode_open", "vscode_open_folder",
        "vscode_install_extension", "vscode_run_command",
        # Visual Studio
        "visual_studio_open_solution", "visual_studio_build",
        # Android Studio
        "android_studio_open_project", "android_studio_run_gradle",
        # Xcode
        "xcode_open_project", "xcode_build",
        # Unity
        "unity_open_project", "unity_run_batch_method",
        # WebStorm
        "webstorm_open_project",
        # Flutter
        "flutter_create_project", "flutter_run", "flutter_build",
        # React Native
        "react_native_init", "react_native_run_android", "react_native_run_ios",
        # XAMPP / WAMP
        "xampp_start", "xampp_stop", "wamp_start", "wamp_stop",
        # Python
        "python_create_venv", "python_pip_install", "python_run_script",
    }
    missing = expected - names
    assert not missing, f"missing: {missing}"


# ---------------------------------------------------------------------- #
# VS Code
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_vscode_open_missing_path(tmp_path):
    r = await VSCodeOpenTool().run(path=str(tmp_path / "no"))
    assert r.success is False


@pytest.mark.asyncio
async def test_vscode_open_no_cli(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("x")
    with patch("app.tools.integrations.dev_tools.vscode_tools._code_cli",
               return_value=None):
        r = await VSCodeOpenTool().run(path=str(f))
    assert r.success is False


@pytest.mark.asyncio
async def test_vscode_open_success(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("x")
    with patch("app.tools.integrations.dev_tools.vscode_tools._run_code",
               return_value=MagicMock(returncode=0)):
        r = await VSCodeOpenTool().run(path=str(f))
    assert r.success is True


@pytest.mark.asyncio
async def test_vscode_open_folder_missing(tmp_path):
    r = await VSCodeOpenFolderTool().run(folder=str(tmp_path / "no"))
    assert r.success is False


@pytest.mark.asyncio
async def test_vscode_open_folder_success(tmp_path):
    d = tmp_path / "proj"
    d.mkdir()
    with patch("app.tools.integrations.dev_tools.vscode_tools._run_code",
               return_value=MagicMock(returncode=0)):
        r = await VSCodeOpenFolderTool().run(folder=str(d))
    assert r.success is True


@pytest.mark.asyncio
async def test_vscode_install_extension_missing():
    r = await VSCodeInstallExtensionTool().run(extension_id="")
    assert r.success is False


@pytest.mark.asyncio
async def test_vscode_run_command_missing():
    r = await VSCodeRunCommandTool().run(args=[])
    assert r.success is False


# ---------------------------------------------------------------------- #
# Visual Studio
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_visual_studio_open_missing_exe():
    with patch.object(VisualStudioOpenSolutionTool, "_discover_path",
                      return_value=None):
        r = await VisualStudioOpenSolutionTool().run(
            solution_path="C:/fake.sln")
    assert r.success is False


@pytest.mark.asyncio
async def test_visual_studio_build_missing_exe(tmp_path):
    sln = tmp_path / "fake.sln"
    sln.write_text("x")
    with patch.object(VisualStudioBuildTool, "_discover_path", return_value=None):
        r = await VisualStudioBuildTool().run(solution_path=str(sln))
    assert r.success is False


# ---------------------------------------------------------------------- #
# Android Studio
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_android_studio_open_no_exe(tmp_path):
    d = tmp_path / "proj"
    d.mkdir()
    with patch.object(AndroidStudioOpenProjectTool, "_discover_path",
                      return_value=None):
        r = await AndroidStudioOpenProjectTool().run(project_dir=str(d))
    assert r.success is False


@pytest.mark.asyncio
async def test_android_studio_gradle_missing_project(tmp_path):
    r = await AndroidStudioRunGradleTool().run(
        project_dir=str(tmp_path / "no"), task="build")
    assert r.success is False


# ---------------------------------------------------------------------- #
# Xcode (Windows-only runner)
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_xcode_open_on_windows_rejected(tmp_path):
    # Only meaningful on Windows
    if sys.platform == "darwin":
        pytest.skip("Xcode supported on macOS")
    r = await XcodeOpenProjectTool().run(project_path="x.xcodeproj")
    assert r.success is False
    assert r.error["code"] == "PLATFORM_UNSUPPORTED"


@pytest.mark.asyncio
async def test_xcode_build_on_windows_rejected():
    if sys.platform == "darwin":
        pytest.skip("Xcode supported on macOS")
    r = await XcodeBuildTool().run(project_dir=".", scheme="App")
    assert r.success is False


# ---------------------------------------------------------------------- #
# Unity
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_unity_open_no_exe(tmp_path):
    d = tmp_path / "proj"
    d.mkdir()
    with patch.object(UnityOpenProjectTool, "_discover_path", return_value=None):
        r = await UnityOpenProjectTool().run(project_path=str(d))
    assert r.success is False


@pytest.mark.asyncio
async def test_unity_batch_missing_args(tmp_path):
    r = await UnityRunBatchMethodTool().run(project_path=".", method="")
    assert r.success is False


# ---------------------------------------------------------------------- #
# WebStorm
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_webstorm_open_no_exe(tmp_path):
    d = tmp_path / "proj"
    d.mkdir()
    with patch.object(WebStormOpenProjectTool, "_discover_path", return_value=None), \
         patch("app.tools.integrations.dev_tools.webstorm_tools._webstorm_cli",
               return_value=None):
        r = await WebStormOpenProjectTool().run(project_dir=str(d))
    assert r.success is False


# ---------------------------------------------------------------------- #
# Flutter
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_flutter_create_missing_args():
    r = await FlutterCreateProjectTool().run(project_name="", output_dir=".")
    assert r.success is False


@pytest.mark.asyncio
async def test_flutter_run_missing_project(tmp_path):
    r = await FlutterRunTool().run(project_dir=str(tmp_path / "no"))
    assert r.success is False


@pytest.mark.asyncio
async def test_flutter_build_missing_project(tmp_path):
    r = await FlutterBuildTool().run(project_dir=str(tmp_path / "no"), target="apk")
    assert r.success is False


# ---------------------------------------------------------------------- #
# React Native
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_react_native_init_missing_args():
    r = await ReactNativeInitTool().run(project_name="", output_dir=".")
    assert r.success is False


@pytest.mark.asyncio
async def test_react_native_run_android_missing(tmp_path):
    r = await ReactNativeRunAndroidTool().run(project_dir=str(tmp_path / "no"))
    assert r.success is False


@pytest.mark.asyncio
async def test_react_native_run_ios_on_windows(tmp_path):
    if sys.platform == "darwin":
        pytest.skip("iOS build works on macOS")
    d = tmp_path / "proj"
    d.mkdir()
    r = await ReactNativeRunIosTool().run(project_dir=str(d))
    assert r.success is False
    assert r.error["code"] == "PLATFORM_UNSUPPORTED"


# ---------------------------------------------------------------------- #
# XAMPP / WAMP
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_xampp_start_no_root():
    with patch("app.tools.integrations.dev_tools.server_stack_tools._xampp_root",
               return_value=None):
        r = await XamppStartTool().run()
    assert r.success is False


@pytest.mark.asyncio
async def test_xampp_stop_noop():
    with patch("subprocess.run", return_value=MagicMock(returncode=1)):
        r = await XamppStopTool().run()
    assert r.success is True


@pytest.mark.asyncio
async def test_wamp_start_no_root():
    with patch("app.tools.integrations.dev_tools.server_stack_tools._wamp_root",
               return_value=None):
        r = await WampStartTool().run()
    assert r.success is False


@pytest.mark.asyncio
async def test_wamp_stop_noop():
    with patch("subprocess.run", return_value=MagicMock(returncode=1)):
        r = await WampStopTool().run()
    assert r.success is True


# ---------------------------------------------------------------------- #
# Python
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_python_create_venv_missing_path():
    r = await PythonCreateVenvTool().run(venv_path="")
    assert r.success is False, f"Expected failure but got: {r.data}"

@pytest.mark.asyncio
async def test_python_create_venv_empty_string():
    """An empty string should not create a venv at cwd."""
    r = await PythonCreateVenvTool().run(venv_path="   ")
    assert r.success is False


@pytest.mark.asyncio
async def test_python_create_venv_no_python(tmp_path):
    with patch("app.tools.integrations.dev_tools.python_env_tools._python_cli",
               return_value=None):
        r = await PythonCreateVenvTool().run(venv_path=str(tmp_path / "venv"))
    assert r.success is False


@pytest.mark.asyncio
async def test_python_pip_install_missing_packages():
    r = await PythonPipInstallTool().run(packages=[])
    assert r.success is False


@pytest.mark.asyncio
async def test_python_pip_install_no_python(tmp_path):
    with patch("app.tools.integrations.dev_tools.python_env_tools._python_cli",
               return_value=None):
        r = await PythonPipInstallTool().run(packages=["requests"])
    assert r.success is False


@pytest.mark.asyncio
async def test_python_run_script_missing(tmp_path):
    r = await PythonRunScriptTool().run(
        script_path=str(tmp_path / "no.py"))
    assert r.success is False


@pytest.mark.asyncio
async def test_python_run_script_success(tmp_path):
    script = tmp_path / "s.py"
    script.write_text("print('hi')")

    def fake_run(*args, **kw):
        return MagicMock(returncode=0, stdout="hi\n", stderr="")

    with patch("subprocess.run", side_effect=fake_run):
        r = await PythonRunScriptTool().run(script_path=str(script))
    assert r.success is True
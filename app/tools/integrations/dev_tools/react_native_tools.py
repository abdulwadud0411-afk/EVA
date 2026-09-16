"""
React Native integration.

Uses the `npx react-native` CLI (free, open-source).
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, List, Optional

from app.core.logger import get_logger
from app.tools.base import ToolResult, RiskLevel
from app.tools.integrations.integration_base import AppIntegrationTool

logger = get_logger(__name__)


def _npx_cli() -> Optional[str]:
    for name in ("npx", "npx.cmd", "npx.exe"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _run_npx(args: List[str], cwd: Optional[str] = None, timeout: int = 3600) -> subprocess.CompletedProcess:
    cli = _npx_cli()
    if not cli:
        raise RuntimeError("npx not found on PATH. Install Node.js.")
    return subprocess.run(
        [cli] + args,
        cwd=cwd,
        capture_output=True, text=True, timeout=timeout,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )


# ---------------------------------------------------------------------- #
# Tool: react_native_init
# ---------------------------------------------------------------------- #
class ReactNativeInitTool(AppIntegrationTool):
    APP_KEY = "react_native"
    CONFIG_SECTION = "integrations.dev_tools"

    name = "react_native_init"
    description = "Create a new React Native project."
    parameters = {
        "type": "object",
        "properties": {
            "project_name": {"type": "string"},
            "output_dir": {"type": "string"},
        },
        "required": ["project_name", "output_dir"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        name = str(kwargs.get("project_name", "")).strip()
        out_dir = Path(str(kwargs.get("output_dir", ""))).expanduser()
        if not name or not out_dir:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "project_name + output_dir required"},
            )
        out_dir.mkdir(parents=True, exist_ok=True)

        args = ["@react-native-community/cli@latest", "init", name, "--skip-install"]
        try:
            r = _run_npx(args, cwd=str(out_dir))
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "REACT_NATIVE_FAILED", "message": str(exc)},
            )
        return ToolResult(
            success=r.returncode == 0,
            tool=self.name,
            data={
                "project": str(out_dir / name),
                "stdout_tail": (r.stdout or "")[-800:],
            },
        )


# ---------------------------------------------------------------------- #
# Tool: react_native_run_android
# ---------------------------------------------------------------------- #
class ReactNativeRunAndroidTool(AppIntegrationTool):
    APP_KEY = "react_native"
    CONFIG_SECTION = "integrations.dev_tools"

    name = "react_native_run_android"
    description = "Run the Android app in a React Native project."
    parameters = {
        "type": "object",
        "properties": {"project_dir": {"type": "string"}},
        "required": ["project_dir"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        project = Path(str(kwargs.get("project_dir", ""))).expanduser()
        if not project.is_dir():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "PROJECT_NOT_FOUND", "message": str(project)},
            )
        try:
            cli = _npx_cli()
            if not cli:
                raise RuntimeError("npx not found")
            subprocess.Popen(
                [cli, "react-native", "run-android"],
                cwd=str(project),
                creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0,
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "REACT_NATIVE_FAILED", "message": str(exc)},
            )
        return ToolResult(
            success=True,
            tool=self.name,
            data={"project": str(project), "detached": True},
        )


# ---------------------------------------------------------------------- #
# Tool: react_native_run_ios
# ---------------------------------------------------------------------- #
class ReactNativeRunIosTool(AppIntegrationTool):
    APP_KEY = "react_native"
    CONFIG_SECTION = "integrations.dev_tools"

    name = "react_native_run_ios"
    description = "Run the iOS app in a React Native project (macOS only)."
    parameters = {
        "type": "object",
        "properties": {"project_dir": {"type": "string"}},
        "required": ["project_dir"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        import sys
        if sys.platform != "darwin":
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "PLATFORM_UNSUPPORTED",
                    "message": "iOS builds require macOS + Xcode.",
                },
            )
        project = Path(str(kwargs.get("project_dir", ""))).expanduser()
        if not project.is_dir():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "PROJECT_NOT_FOUND", "message": str(project)},
            )
        try:
            cli = _npx_cli()
            if not cli:
                raise RuntimeError("npx not found")
            subprocess.Popen(
                [cli, "react-native", "run-ios"],
                cwd=str(project),
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "REACT_NATIVE_FAILED", "message": str(exc)},
            )
        return ToolResult(
            success=True,
            tool=self.name,
            data={"project": str(project), "detached": True},
        )
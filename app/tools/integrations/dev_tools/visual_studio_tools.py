"""
Visual Studio integration.

Uses devenv.exe CLI (COM-free). Requires Visual Studio installed.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from app.core.logger import get_logger
from app.tools.base import ToolResult, RiskLevel
from app.tools.integrations.integration_base import AppIntegrationTool

logger = get_logger(__name__)


def _run_devenv(devenv: str, args: list, timeout: int = 1800) -> subprocess.CompletedProcess:
    return subprocess.run(
        [devenv] + args,
        capture_output=True, text=True, timeout=timeout,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )


# ---------------------------------------------------------------------- #
# Tool: visual_studio_open_solution
# ---------------------------------------------------------------------- #
class VisualStudioOpenSolutionTool(AppIntegrationTool):
    APP_KEY = "visual_studio"
    CONFIG_SECTION = "integrations.dev_tools"

    name = "visual_studio_open_solution"
    description = "Open a Visual Studio solution (.sln) in the VS GUI."
    parameters = {
        "type": "object",
        "properties": {"solution_path": {"type": "string"}},
        "required": ["solution_path"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        devenv = self._discover_path()
        if not devenv:
            return self._not_installed_result()
        path = Path(str(kwargs.get("solution_path", ""))).expanduser()
        if not path.exists():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "SOLUTION_NOT_FOUND", "message": str(path)},
            )
        try:
            subprocess.Popen(
                [devenv, str(path)],
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "LAUNCH_FAILED", "message": str(exc)},
            )
        return ToolResult(success=True, tool=self.name, data={"solution": str(path)})


# ---------------------------------------------------------------------- #
# Tool: visual_studio_build
# ---------------------------------------------------------------------- #
class VisualStudioBuildTool(AppIntegrationTool):
    APP_KEY = "visual_studio"
    CONFIG_SECTION = "integrations.dev_tools"

    name = "visual_studio_build"
    description = "Build a VS solution headlessly using devenv.com."
    parameters = {
        "type": "object",
        "properties": {
            "solution_path": {"type": "string"},
            "configuration": {"type": "string"},
        },
        "required": ["solution_path"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        devenv = self._discover_path()
        if not devenv:
            return self._not_installed_result()
        # devenv.com is the CLI counterpart of devenv.exe
        devenv_com = devenv.replace("devenv.exe", "devenv.com")
        path = Path(str(kwargs.get("solution_path", ""))).expanduser()
        if not path.exists():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "SOLUTION_NOT_FOUND", "message": str(path)},
            )
        config = str(kwargs.get("configuration") or "Debug")
        try:
            r = _run_devenv(devenv_com, ["-build", config, str(path)], timeout=3600)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "BUILD_FAILED", "message": str(exc)},
            )
        return ToolResult(
            success=r.returncode == 0,
            tool=self.name,
            data={
                "returncode": r.returncode,
                "stdout_tail": (r.stdout or "")[-2000:],
                "stderr_tail": (r.stderr or "")[-2000:],
            },
        )
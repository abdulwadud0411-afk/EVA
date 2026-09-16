"""
Unity integration.

Uses Unity's command-line interface (-batchmode, -executeMethod).
Requires Unity Editor installed.
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


# ---------------------------------------------------------------------- #
# Tool: unity_open_project
# ---------------------------------------------------------------------- #
class UnityOpenProjectTool(AppIntegrationTool):
    APP_KEY = "unity"
    CONFIG_SECTION = "integrations.dev_tools"

    name = "unity_open_project"
    description = "Open a Unity project in the Unity Editor GUI."
    parameters = {
        "type": "object",
        "properties": {"project_path": {"type": "string"}},
        "required": ["project_path"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        exe = self._discover_path()
        if not exe:
            return self._not_installed_result()
        project = Path(str(kwargs.get("project_path", ""))).expanduser()
        if not project.is_dir():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "PROJECT_NOT_FOUND", "message": str(project)},
            )
        try:
            subprocess.Popen(
                [exe, "-projectPath", str(project)],
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "LAUNCH_FAILED", "message": str(exc)},
            )
        return ToolResult(success=True, tool=self.name, data={"project": str(project)})


# ---------------------------------------------------------------------- #
# Tool: unity_run_batch_method
# ---------------------------------------------------------------------- #
class UnityRunBatchMethodTool(AppIntegrationTool):
    APP_KEY = "unity"
    CONFIG_SECTION = "integrations.dev_tools"

    name = "unity_run_batch_method"
    description = "Run a static Editor method in a Unity project (headless)."
    parameters = {
        "type": "object",
        "properties": {
            "project_path": {"type": "string"},
            "method": {"type": "string"},
            "log_path": {"type": "string"},
        },
        "required": ["project_path", "method"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        exe = self._discover_path()
        if not exe:
            return self._not_installed_result()
        project = Path(str(kwargs.get("project_path", ""))).expanduser()
        method = str(kwargs.get("method", "")).strip()
        if not project.is_dir() or not method:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "project_path + method required"},
            )
        log_path = str(kwargs.get("log_path") or project / "unity_batch.log")
        try:
            r = subprocess.run(
                [
                    exe,
                    "-batchmode", "-quit",
                    "-projectPath", str(project),
                    "-executeMethod", method,
                    "-logFile", log_path,
                ],
                capture_output=True, text=True, timeout=7200,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "UNITY_FAILED", "message": str(exc)},
            )
        return ToolResult(
            success=r.returncode == 0,
            tool=self.name,
            data={
                "returncode": r.returncode,
                "log_path": log_path,
                "stdout_tail": (r.stdout or "")[-1000:],
                "stderr_tail": (r.stderr or "")[-1000:],
            },
        )
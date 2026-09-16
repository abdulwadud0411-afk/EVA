"""
Android Studio integration.

Launch Studio + run Gradle tasks in a project.
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


def _gradlew(project_dir: Path) -> str:
    for name in ("gradlew.bat", "gradlew"):
        p = project_dir / name
        if p.exists():
            return str(p)
    raise RuntimeError(f"gradlew not found in {project_dir}")


# ---------------------------------------------------------------------- #
# Tool: android_studio_open_project
# ---------------------------------------------------------------------- #
class AndroidStudioOpenProjectTool(AppIntegrationTool):
    APP_KEY = "android_studio"
    CONFIG_SECTION = "integrations.dev_tools"

    name = "android_studio_open_project"
    description = "Open an Android project in Android Studio."
    parameters = {
        "type": "object",
        "properties": {"project_dir": {"type": "string"}},
        "required": ["project_dir"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        exe = self._discover_path()
        if not exe:
            return self._not_installed_result()
        project_dir = Path(str(kwargs.get("project_dir", ""))).expanduser()
        if not project_dir.is_dir():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "PROJECT_NOT_FOUND", "message": str(project_dir)},
            )
        try:
            subprocess.Popen(
                [exe, str(project_dir)],
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "LAUNCH_FAILED", "message": str(exc)},
            )
        return ToolResult(success=True, tool=self.name, data={"project": str(project_dir)})


# ---------------------------------------------------------------------- #
# Tool: android_studio_run_gradle
# ---------------------------------------------------------------------- #
class AndroidStudioRunGradleTool(AppIntegrationTool):
    APP_KEY = "android_studio"
    CONFIG_SECTION = "integrations.dev_tools"

    name = "android_studio_run_gradle"
    description = "Run a Gradle task inside an Android project (uses gradlew)."
    parameters = {
        "type": "object",
        "properties": {
            "project_dir": {"type": "string"},
            "task": {"type": "string"},
            "args": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["project_dir", "task"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        project_dir = Path(str(kwargs.get("project_dir", ""))).expanduser()
        if not project_dir.is_dir():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "PROJECT_NOT_FOUND", "message": str(project_dir)},
            )
        task = str(kwargs.get("task", "")).strip()
        if not task:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "task required"},
            )
        extra = [str(a) for a in (kwargs.get("args") or [])]
        try:
            gw = _gradlew(project_dir)
            r = subprocess.run(
                [gw, task] + extra,
                cwd=str(project_dir),
                capture_output=True, text=True, timeout=1800,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "GRADLE_FAILED", "message": str(exc)},
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
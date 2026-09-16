"""
Xcode integration (macOS only).

On Windows these tools return a clear "macOS only" error.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from app.core.logger import get_logger
from app.tools.base import ToolResult, RiskLevel
from app.tools.integrations.integration_base import AppIntegrationTool

logger = get_logger(__name__)


def _is_macos() -> bool:
    return sys.platform == "darwin"


# ---------------------------------------------------------------------- #
# Tool: xcode_open_project
# ---------------------------------------------------------------------- #
class XcodeOpenProjectTool(AppIntegrationTool):
    APP_KEY = "xcode"
    CONFIG_SECTION = "integrations.dev_tools"

    name = "xcode_open_project"
    description = "Open an Xcode project/workspace (macOS only)."
    parameters = {
        "type": "object",
        "properties": {"project_path": {"type": "string"}},
        "required": ["project_path"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        if not _is_macos():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "PLATFORM_UNSUPPORTED", "message": "Xcode is macOS only."},
            )
        path = Path(str(kwargs.get("project_path", ""))).expanduser()
        if not path.exists():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "PROJECT_NOT_FOUND", "message": str(path)},
            )
        try:
            subprocess.Popen(["open", "-a", "Xcode", str(path)])
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "OPEN_FAILED", "message": str(exc)},
            )
        return ToolResult(success=True, tool=self.name, data={"project": str(path)})


# ---------------------------------------------------------------------- #
# Tool: xcode_build
# ---------------------------------------------------------------------- #
class XcodeBuildTool(AppIntegrationTool):
    APP_KEY = "xcode"
    CONFIG_SECTION = "integrations.dev_tools"

    name = "xcode_build"
    description = "Run `xcodebuild` on a project (macOS only)."
    parameters = {
        "type": "object",
        "properties": {
            "project_dir": {"type": "string"},
            "scheme": {"type": "string"},
        },
        "required": ["project_dir", "scheme"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        if not _is_macos():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "PLATFORM_UNSUPPORTED", "message": "xcodebuild is macOS only."},
            )
        project_dir = Path(str(kwargs.get("project_dir", ""))).expanduser()
        scheme = str(kwargs.get("scheme", "")).strip()
        if not project_dir.is_dir() or not scheme:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "project_dir + scheme required"},
            )
        try:
            r = subprocess.run(
                ["xcodebuild", "-scheme", scheme, "build"],
                cwd=str(project_dir),
                capture_output=True, text=True, timeout=1800,
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "XCODEBUILD_FAILED", "message": str(exc)},
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
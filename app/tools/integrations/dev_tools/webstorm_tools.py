"""
WebStorm (JetBrains) integration.

Opens projects in WebStorm via its CLI launcher (webstorm64.exe or the
`webstorm` command from JetBrains Toolbox).
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


def _webstorm_cli() -> str | None:
    # Try PATH first
    from shutil import which
    for name in ("webstorm", "webstorm64.exe", "webstorm.bat"):
        found = which(name)
        if found:
            return found
    # Common install locations
    candidates = [
        r"C:\Program Files\JetBrains\WebStorm 2024.3\bin\webstorm64.exe",
        r"C:\Program Files\JetBrains\WebStorm 2024.2\bin\webstorm64.exe",
        r"C:\Program Files\JetBrains\WebStorm 2024.1\bin\webstorm64.exe",
        r"C:\Program Files\JetBrains\WebStorm 2023.3\bin\webstorm64.exe",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return None


# ---------------------------------------------------------------------- #
# Tool: webstorm_open_project
# ---------------------------------------------------------------------- #
class WebStormOpenProjectTool(AppIntegrationTool):
    APP_KEY = "webstorm"
    CONFIG_SECTION = "integrations.dev_tools"

    name = "webstorm_open_project"
    description = "Open a project folder in WebStorm."
    parameters = {
        "type": "object",
        "properties": {"project_dir": {"type": "string"}},
        "required": ["project_dir"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        exe = self._discover_path() or _webstorm_cli()
        if not exe:
            return self._not_installed_result(
                hint="Install WebStorm or set integrations.dev_tools.executable_path."
            )
        project = Path(str(kwargs.get("project_dir", ""))).expanduser()
        if not project.is_dir():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "PROJECT_NOT_FOUND", "message": str(project)},
            )
        try:
            subprocess.Popen(
                [exe, str(project)],
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "LAUNCH_FAILED", "message": str(exc)},
            )
        return ToolResult(success=True, tool=self.name, data={"project": str(project)})
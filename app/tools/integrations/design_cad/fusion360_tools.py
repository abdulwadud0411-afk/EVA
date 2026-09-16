"""
Autodesk Fusion 360 integration (Design & CAD).

Fusion 360 exposes a Python API usable from the application's own
Scripts/Add-Ins panel. There is no public COM automation, so this
tool controls Fusion via its CLI launch and file operations.

Note: deeper automation requires a Fusion Add-In (future phase).
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, List

from app.core.logger import get_logger
from app.tools.base import ToolResult, RiskLevel
from app.tools.integrations.integration_base import AppIntegrationTool

logger = get_logger(__name__)


def _fusion_exe() -> str | None:
    # Common install locations
    import os as _os
    candidates = [
        _os.path.expandvars(r"%LOCALAPPDATA%\Autodesk\webdeploy\production"),
        r"C:\Program Files\Autodesk\Fusion 360",
    ]
    for root in candidates:
        p = Path(root)
        if not p.exists():
            continue
        for f in p.glob("**/Fusion360.exe"):
            return str(f)
    return None


# ---------------------------------------------------------------------- #
# Tool: fusion360_open
# ---------------------------------------------------------------------- #
class Fusion360OpenTool(AppIntegrationTool):
    APP_KEY = "fusion360"
    CONFIG_SECTION = "integrations.design_cad"

    name = "fusion360_open"
    description = "Launch Autodesk Fusion 360 (optionally open a file)."
    parameters = {
        "type": "object",
        "properties": {"file_path": {"type": "string"}},
        "required": [],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        exe = self._discover_path() or _fusion_exe()
        if not exe:
            return self._not_installed_result(
                hint="Install Fusion 360 or set integrations.design_cad.executable_path."
            )
        args: List[str] = []
        file_path = kwargs.get("file_path")
        if file_path:
            p = Path(str(file_path)).expanduser()
            if not p.exists():
                return ToolResult(
                    success=False,
                    tool=self.name,
                    error={"code": "FILE_NOT_FOUND", "message": str(p)},
                )
            args.append(str(p))
        try:
            subprocess.Popen(
                [exe] + args,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "LAUNCH_FAILED", "message": str(exc)},
            )
        return ToolResult(success=True, tool=self.name, data={"launched": True})


# ---------------------------------------------------------------------- #
# Tool: fusion360_run_script
# ---------------------------------------------------------------------- #
class Fusion360RunScriptTool(AppIntegrationTool):
    APP_KEY = "fusion360"
    CONFIG_SECTION = "integrations.design_cad"

    name = "fusion360_run_script"
    description = (
        "Open a Python script path inside Fusion 360's Scripts folder. "
        "The user must run it from Fusion's UI (no official headless CLI)."
    )
    parameters = {
        "type": "object",
        "properties": {"script_path": {"type": "string"}},
        "required": ["script_path"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        script_path = Path(str(kwargs.get("script_path", ""))).expanduser()
        if not script_path.exists():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "SCRIPT_NOT_FOUND", "message": str(script_path)},
            )
        # Copy into Fusion's default scripts folder for convenience
        import os as _os
        fusion_scripts = Path(_os.path.expandvars(
            r"%APPDATA%\Autodesk\Autodesk Fusion 360\API\Scripts"
        ))
        if not fusion_scripts.exists():
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "FUSION_NOT_CONFIGURED",
                    "message": "Fusion 360 scripts folder not found.",
                },
            )
        target = fusion_scripts / script_path.parent.name / script_path.name
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(script_path.read_bytes())
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "COPY_FAILED", "message": str(exc)},
            )
        return ToolResult(
            success=True,
            tool=self.name,
            data={
                "installed_to": str(target),
                "note": "Open Fusion 360 → Utilities → Add-Ins → Scripts to run it.",
            },
        )
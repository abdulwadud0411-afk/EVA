"""
SketchUp integration (Design & CAD).

Uses SketchUp's Ruby script runner via command-line when available.
Requires SketchUp Pro (for full Ruby API) or SketchUp Make.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, List

from app.core.logger import get_logger
from app.tools.base import ToolResult, RiskLevel
from app.tools.integrations.integration_base import AppIntegrationTool
from app.tools.verifier import file_exists

logger = get_logger(__name__)


def _sketchup_exe() -> str | None:
    import os as _os
    roots = [
        r"C:\Program Files\SketchUp",
        r"C:\Program Files (x86)\SketchUp",
    ]
    for root in roots:
        p = Path(root)
        if not p.exists():
            continue
        for f in p.glob("**/SketchUp.exe"):
            return str(f)
    return None


# ---------------------------------------------------------------------- #
# Tool: sketchup_open
# ---------------------------------------------------------------------- #
class SketchUpOpenTool(AppIntegrationTool):
    APP_KEY = "sketchup"
    CONFIG_SECTION = "integrations.design_cad"

    name = "sketchup_open"
    description = "Open a .skp file in SketchUp."
    parameters = {
        "type": "object",
        "properties": {"file_path": {"type": "string"}},
        "required": ["file_path"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        exe = self._discover_path() or _sketchup_exe()
        if not exe:
            return self._not_installed_result()
        path = Path(str(kwargs.get("file_path", ""))).expanduser()
        if not path.exists():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "FILE_NOT_FOUND", "message": str(path)},
            )
        try:
            subprocess.Popen(
                [exe, str(path)],
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "LAUNCH_FAILED", "message": str(exc)},
            )
        return ToolResult(success=True, tool=self.name, data={"file": str(path)})


# ---------------------------------------------------------------------- #
# Tool: sketchup_export
# ---------------------------------------------------------------------- #
class SketchUpExportTool(AppIntegrationTool):
    APP_KEY = "sketchup"
    CONFIG_SECTION = "integrations.design_cad"

    name = "sketchup_export"
    description = (
        "Export a .skp file to another format via a SketchUp Ruby script. "
        "Requires SketchUp Pro. Provide a .rb script that performs the export."
    )
    parameters = {
        "type": "object",
        "properties": {
            "skp_file": {"type": "string"},
            "ruby_script": {"type": "string"},
            "output_path": {"type": "string"},
        },
        "required": ["skp_file", "ruby_script", "output_path"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        skp = Path(str(kwargs.get("skp_file", ""))).expanduser()
        rb = Path(str(kwargs.get("ruby_script", ""))).expanduser()
        out = Path(str(kwargs.get("output_path", ""))).expanduser()
        for p in (skp, rb):
            if not p.exists():
                return ToolResult(
                    success=False,
                    tool=self.name,
                    error={"code": "INPUT_NOT_FOUND", "message": str(p)},
                )
        out.parent.mkdir(parents=True, exist_ok=True)

        exe = self._discover_path() or _sketchup_exe()
        if not exe:
            return self._not_installed_result()

        # SketchUp Pro accepts a Ruby script as an argument
        try:
            r = subprocess.run(
                [exe, str(skp), "-RubyStartup", str(rb)],
                capture_output=True, text=True, timeout=1800,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "EXPORT_FAILED", "message": str(exc)},
            )
        check = file_exists(str(out), min_size_bytes=1)
        return ToolResult(
            success=check["verified"],
            tool=self.name,
            data={
                "output": str(out),
                "returncode": r.returncode,
                "verified": check,
            },
        )
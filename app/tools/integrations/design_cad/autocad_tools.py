"""
AutoCAD integration (Design & CAD).

COM automation via pywin32. Requires AutoCAD installed (any version
with COM API — 2016+ recommended).
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from app.core.logger import get_logger
from app.tools.base import ToolResult, RiskLevel
from app.tools.integrations.integration_base import AppIntegrationTool
from app.tools.verifier import file_exists

logger = get_logger(__name__)


def _get_autocad():
    try:
        import win32com.client  # type: ignore
    except Exception as exc:  # noqa: BLE001
        logger.error("pywin32_not_available", error=str(exc))
        return None

    try:
        return win32com.client.GetActiveObject("AutoCAD.Application")
    except Exception:  # noqa: BLE001
        pass

    try:
        app = win32com.client.Dispatch("AutoCAD.Application")
        app.Visible = True
        return app
    except Exception as exc:  # noqa: BLE001
        logger.error("autocad_com_failed", error=str(exc))
        return None


# ---------------------------------------------------------------------- #
# Tool: autocad_open
# ---------------------------------------------------------------------- #
class AutoCADOpenTool(AppIntegrationTool):
    APP_KEY = "autocad"
    CONFIG_SECTION = "integrations.design_cad"

    name = "autocad_open"
    description = "Open a DWG/DXF drawing in AutoCAD."
    parameters = {
        "type": "object",
        "properties": {"drawing_path": {"type": "string"}},
        "required": ["drawing_path"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        path = Path(str(kwargs.get("drawing_path", ""))).expanduser()
        if not path.exists():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "DRAWING_NOT_FOUND", "message": str(path)},
            )

        acad = _get_autocad()
        if acad is None:
            return self._not_installed_result(
                hint="Install AutoCAD and ensure pywin32 is available."
            )

        try:
            doc = acad.Documents.Open(str(path))
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "OPEN_FAILED", "message": str(exc)},
            )

        return ToolResult(success=True, tool=self.name, data={"drawing": str(path)})


# ---------------------------------------------------------------------- #
# Tool: autocad_run_script
# ---------------------------------------------------------------------- #
class AutoCADRunScriptTool(AppIntegrationTool):
    APP_KEY = "autocad"
    CONFIG_SECTION = "integrations.design_cad"

    name = "autocad_run_script"
    description = (
        "Run a set of AutoCAD commands (LISP or command string) in the "
        "active drawing. Use the CAD-native command language."
    )
    parameters = {
        "type": "object",
        "properties": {
            "commands": {"type": "string"},
        },
        "required": ["commands"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        commands = str(kwargs.get("commands") or "").strip()
        if not commands:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "commands required"},
            )

        acad = _get_autocad()
        if acad is None:
            return self._not_installed_result()

        try:
            doc = acad.ActiveDocument
            # AutoCAD's SendCommand accepts a command string terminated by \n
            doc.SendCommand(commands + "\n")
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "SCRIPT_FAILED", "message": str(exc)},
            )

        return ToolResult(success=True, tool=self.name, data={"commands_sent": True})


# ---------------------------------------------------------------------- #
# Tool: autocad_export_pdf
# ---------------------------------------------------------------------- #
class AutoCADExportPdfTool(AppIntegrationTool):
    APP_KEY = "autocad"
    CONFIG_SECTION = "integrations.design_cad"

    name = "autocad_export_pdf"
    description = "Export the active AutoCAD drawing to PDF."
    parameters = {
        "type": "object",
        "properties": {"output_path": {"type": "string"}},
        "required": ["output_path"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        out = Path(str(kwargs.get("output_path", ""))).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)

        acad = _get_autocad()
        if acad is None:
            return self._not_installed_result()

        try:
            doc = acad.ActiveDocument
            # Use AutoCAD's built-in PLOT or Export command
            doc.SendCommand(f'_-PLOT\nY\n\n\n\n\n\n\n{out.as_posix()}\n')
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "EXPORT_FAILED", "message": str(exc)},
            )

        time.sleep(1.0)
        check = file_exists(str(out), min_size_bytes=1000)
        return ToolResult(
            success=check["verified"],
            tool=self.name,
            data={"output": str(out), "verified": check},
        )
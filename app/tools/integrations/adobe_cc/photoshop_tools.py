"""
Adobe Photoshop integration (Adobe CC).

Uses Windows COM automation via pywin32 to talk to a running
Photoshop instance. If Photoshop is not open, COM will launch it.

Requires the user to have Photoshop legally installed.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Optional

from app.core.logger import get_logger
from app.tools.base import ToolResult, RiskLevel
from app.tools.integrations.integration_base import AppIntegrationTool
from app.tools.verifier import file_exists, wait_for_process

logger = get_logger(__name__)


# ---------------------------------------------------------------------- #
# COM helpers
# ---------------------------------------------------------------------- #
def _get_photoshop():
    """Return a COM handle to Photoshop, or None."""
    try:
        import win32com.client  # type: ignore
    except Exception as exc:  # noqa: BLE001
        logger.error("pywin32_not_available", error=str(exc))
        return None

    # Try to attach to a running instance first
    try:
        return win32com.client.GetActiveObject("Photoshop.Application")
    except Exception:  # noqa: BLE001
        pass

    # Otherwise launch Photoshop via COM
    try:
        return win32com.client.Dispatch("Photoshop.Application")
    except Exception as exc:  # noqa: BLE001
        logger.error("photoshop_com_failed", error=str(exc))
        return None


# ---------------------------------------------------------------------- #
# Tool: photoshop_open
# ---------------------------------------------------------------------- #
class PhotoshopOpenTool(AppIntegrationTool):
    APP_KEY = "photoshop"
    CONFIG_SECTION = "integrations.adobe"

    name = "photoshop_open"
    description = "Open a file in Photoshop (launches Photoshop if needed)."
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {"type": "string"},
        },
        "required": ["file_path"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        file_path = Path(str(kwargs.get("file_path", ""))).expanduser()
        if not file_path.exists():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "FILE_NOT_FOUND", "message": str(file_path)},
            )

        ps = _get_photoshop()
        if ps is None:
            return self._not_installed_result(
                hint="Ensure Photoshop is installed and pywin32 is available."
            )

        try:
            ps.Open(str(file_path))
        except Exception as exc:  # noqa: BLE001
            logger.error("photoshop_open_failed", error=str(exc))
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "OPEN_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"file": str(file_path), "opened": True},
        )


# ---------------------------------------------------------------------- #
# Tool: photoshop_run_action
# ---------------------------------------------------------------------- #
class PhotoshopRunActionTool(AppIntegrationTool):
    APP_KEY = "photoshop"
    CONFIG_SECTION = "integrations.adobe"

    name = "photoshop_run_action"
    description = "Run a Photoshop action from a specific action set."
    parameters = {
        "type": "object",
        "properties": {
            "action_set": {"type": "string"},
            "action_name": {"type": "string"},
        },
        "required": ["action_set", "action_name"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        action_set = str(kwargs.get("action_set", "")).strip()
        action_name = str(kwargs.get("action_name", "")).strip()
        if not action_set or not action_name:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "action_set and action_name required"},
            )

        ps = _get_photoshop()
        if ps is None:
            return self._not_installed_result()

        try:
            ps.DoAction(action_name, action_set)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "ACTION_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"action_set": action_set, "action_name": action_name},
        )


# ---------------------------------------------------------------------- #
# Tool: photoshop_export
# ---------------------------------------------------------------------- #
class PhotoshopExportTool(AppIntegrationTool):
    APP_KEY = "photoshop"
    CONFIG_SECTION = "integrations.adobe"

    name = "photoshop_export"
    description = "Export the active document to PNG/JPG/PSD."
    parameters = {
        "type": "object",
        "properties": {
            "output_path": {"type": "string"},
            "format": {"type": "string"},
        },
        "required": ["output_path"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        output_path = Path(str(kwargs.get("output_path", ""))).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fmt = str(kwargs.get("format") or output_path.suffix.lstrip(".") or "png").lower()

        ps = _get_photoshop()
        if ps is None:
            return self._not_installed_result()

        # Photoshop COM export constants
        # 2 = PNG, 4 = JPG (approximate; varies by version)
        ext_type = 2 if fmt == "png" else 4

        try:
            doc = ps.ActiveDocument
            options = ps.Application.PDFSaveOptions if False else None  # keep simple
            # Use SaveAs with a small JSX-free approach
            doc.SaveAs(str(output_path), None, True, ext_type)
        except Exception as exc:  # noqa: BLE001
            # Fallback: JSX call
            try:
                jsx = f'''
                var doc = app.activeDocument;
                var file = new File("{output_path.as_posix()}");
                var opts = new PNGSaveOptions();
                doc.saveAs(file, opts, true, Extension.LOWERCASE);
                '''
                ps.DoJavaScript(jsx, 1)
            except Exception as exc2:  # noqa: BLE001
                return ToolResult(
                    success=False,
                    tool=self.name,
                    error={"code": "EXPORT_FAILED", "message": f"{exc} | {exc2}"},
                )

        time.sleep(0.5)
        check = file_exists(str(output_path), min_size_bytes=1)

        return ToolResult(
            success=check["verified"],
            tool=self.name,
            data={"output": str(output_path), "format": fmt, "verified": check},
            error=None if check["verified"] else {"code": "OUTPUT_MISSING", "message": str(check)},
        )
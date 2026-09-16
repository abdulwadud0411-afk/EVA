"""
Adobe Illustrator integration (Adobe CC).

COM automation via pywin32. Requires Illustrator installed.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from app.core.logger import get_logger
from app.tools.base import ToolResult, RiskLevel
from app.tools.integrations.integration_base import AppIntegrationTool
from app.tools.verifier import file_exists

logger = get_logger(__name__)


def _get_illustrator():
    try:
        import win32com.client  # type: ignore
    except Exception as exc:  # noqa: BLE001
        logger.error("pywin32_not_available", error=str(exc))
        return None

    try:
        return win32com.client.GetActiveObject("Illustrator.Application")
    except Exception:  # noqa: BLE001
        pass

    try:
        return win32com.client.Dispatch("Illustrator.Application")
    except Exception as exc:  # noqa: BLE001
        logger.error("illustrator_com_failed", error=str(exc))
        return None


# ---------------------------------------------------------------------- #
# Tool: illustrator_open
# ---------------------------------------------------------------------- #
class IllustratorOpenTool(AppIntegrationTool):
    APP_KEY = "illustrator"
    CONFIG_SECTION = "integrations.adobe"

    name = "illustrator_open"
    description = "Open a file in Illustrator."
    parameters = {
        "type": "object",
        "properties": {"file_path": {"type": "string"}},
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

        ai = _get_illustrator()
        if ai is None:
            return self._not_installed_result()

        try:
            ai.Open(str(file_path))
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "OPEN_FAILED", "message": str(exc)},
            )

        return ToolResult(success=True, tool=self.name, data={"file": str(file_path)})


# ---------------------------------------------------------------------- #
# Tool: illustrator_export
# ---------------------------------------------------------------------- #
class IllustratorExportTool(AppIntegrationTool):
    APP_KEY = "illustrator"
    CONFIG_SECTION = "integrations.adobe"

    name = "illustrator_export"
    description = "Export the active Illustrator document to PNG/JPG/SVG/PDF."
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

        ai = _get_illustrator()
        if ai is None:
            return self._not_installed_result()

        # Illustrator COM export type constants (approximate)
        # 1 = PNG24, 2 = PNG8, 3 = JPG, 4 = SVG, 5 = PDF
        type_map = {"png": 1, "jpg": 3, "jpeg": 3, "svg": 4, "pdf": 5}
        export_type = type_map.get(fmt, 1)

        try:
            doc = ai.ActiveDocument
            doc.Export(str(output_path), export_type)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "EXPORT_FAILED", "message": str(exc)},
            )

        time.sleep(0.5)
        check = file_exists(str(output_path), min_size_bytes=1)

        return ToolResult(
            success=check["verified"],
            tool=self.name,
            data={"output": str(output_path), "format": fmt, "verified": check},
        )


# ---------------------------------------------------------------------- #
# Tool: illustrator_run_script
# ---------------------------------------------------------------------- #
class IllustratorRunScriptTool(AppIntegrationTool):
    APP_KEY = "illustrator"
    CONFIG_SECTION = "integrations.adobe"

    name = "illustrator_run_script"
    description = "Run a JSX script in Illustrator."
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

        ai = _get_illustrator()
        if ai is None:
            return self._not_installed_result()

        try:
            code = script_path.read_text(encoding="utf-8")
            ai.DoJavaScript(code, None, 1)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "SCRIPT_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"script": str(script_path)},
        )
"""
Microsoft PowerPoint integration (Office 365).

COM automation via pywin32. Requires PowerPoint installed.
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


def _get_powerpoint():
    try:
        import win32com.client  # type: ignore
    except Exception as exc:  # noqa: BLE001
        logger.error("pywin32_not_available", error=str(exc))
        return None

    try:
        return win32com.client.GetActiveObject("PowerPoint.Application")
    except Exception:  # noqa: BLE001
        pass

    try:
        return win32com.client.Dispatch("PowerPoint.Application")
    except Exception as exc:  # noqa: BLE001
        logger.error("powerpoint_com_failed", error=str(exc))
        return None


# ---------------------------------------------------------------------- #
# Tool: powerpoint_open
# ---------------------------------------------------------------------- #
class PowerPointOpenTool(AppIntegrationTool):
    APP_KEY = "powerpoint"
    CONFIG_SECTION = "integrations.office"

    name = "powerpoint_open"
    description = "Open a PowerPoint presentation (.pptx/.ppt)."
    parameters = {
        "type": "object",
        "properties": {"file_path": {"type": "string"}},
        "required": ["file_path"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        file_path = Path(str(kwargs.get("file_path", ""))).expanduser()
        if not file_path.exists():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "FILE_NOT_FOUND", "message": str(file_path)},
            )

        ppt = _get_powerpoint()
        if ppt is None:
            return self._not_installed_result()

        try:
            ppt.Presentations.Open(str(file_path), WithWindow=False)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "OPEN_FAILED", "message": str(exc)},
            )

        return ToolResult(success=True, tool=self.name, data={"file": str(file_path)})


# ---------------------------------------------------------------------- #
# Tool: powerpoint_add_slide
# ---------------------------------------------------------------------- #
class PowerPointAddSlideTool(AppIntegrationTool):
    APP_KEY = "powerpoint"
    CONFIG_SECTION = "integrations.office"

    name = "powerpoint_add_slide"
    description = "Add a new slide to the active PowerPoint presentation with a title."
    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "body": {"type": "string"},
        },
        "required": ["title"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        title = str(kwargs.get("title") or "").strip()
        body = str(kwargs.get("body") or "").strip()
        if not title:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "title required"},
            )

        ppt = _get_powerpoint()
        if ppt is None:
            return self._not_installed_result()

        try:
            pres = ppt.ActivePresentation
            # ppLayoutText = 2
            slide = pres.Slides.Add(pres.Slides.Count + 1, 2)
            slide.Shapes.Title.TextFrame.TextRange.Text = title
            if body:
                slide.Shapes.Placeholders(2).TextFrame.TextRange.Text = body
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "ADD_SLIDE_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"slide_index": pres.Slides.Count, "title": title},
        )


# ---------------------------------------------------------------------- #
# Tool: powerpoint_export_pdf
# ---------------------------------------------------------------------- #
class PowerPointExportPdfTool(AppIntegrationTool):
    APP_KEY = "powerpoint"
    CONFIG_SECTION = "integrations.office"

    name = "powerpoint_export_pdf"
    description = "Export the active PowerPoint presentation to PDF."
    parameters = {
        "type": "object",
        "properties": {"output_path": {"type": "string"}},
        "required": ["output_path"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        output_path = Path(str(kwargs.get("output_path", ""))).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        ppt = _get_powerpoint()
        if ppt is None:
            return self._not_installed_result()

        try:
            pres = ppt.ActivePresentation
            # ppSaveAsPDF = 32
            pres.SaveAs(str(output_path), 32)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "EXPORT_FAILED", "message": str(exc)},
            )

        time.sleep(0.7)
        check = file_exists(str(output_path), min_size_bytes=1000)
        return ToolResult(
            success=check["verified"],
            tool=self.name,
            data={"output": str(output_path), "verified": check},
        )
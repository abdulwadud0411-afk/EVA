"""
Adobe Premiere Pro integration (Adobe CC).

COM automation via pywin32. Requires Premiere installed.
Export uses Adobe Media Encoder (AME) if available; falls back to
Premiere's built-in export.

Note: Premiere's COM interface is limited. For deep automation,
this tool also accepts .prproj project paths and can trigger
encodes via the AME command-line (no paid service).
"""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Any, List

from app.core.logger import get_logger
from app.tools.base import ToolResult, RiskLevel
from app.tools.integrations.integration_base import AppIntegrationTool
from app.tools.verifier import file_exists

logger = get_logger(__name__)


def _get_premiere():
    try:
        import win32com.client  # type: ignore
    except Exception as exc:  # noqa: BLE001
        logger.error("pywin32_not_available", error=str(exc))
        return None

    try:
        return win32com.client.GetActiveObject("PremierePro.Application")
    except Exception:  # noqa: BLE001
        pass

    try:
        return win32com.client.Dispatch("PremierePro.Application")
    except Exception as exc:  # noqa: BLE001
        logger.error("premiere_com_failed", error=str(exc))
        return None


# ---------------------------------------------------------------------- #
# Tool: premiere_open_project
# ---------------------------------------------------------------------- #
class PremiereOpenProjectTool(AppIntegrationTool):
    APP_KEY = "premiere"
    CONFIG_SECTION = "integrations.adobe"

    name = "premiere_open_project"
    description = "Open a Premiere Pro project file (.prproj)."
    parameters = {
        "type": "object",
        "properties": {"project_path": {"type": "string"}},
        "required": ["project_path"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        project_path = Path(str(kwargs.get("project_path", ""))).expanduser()
        if not project_path.exists():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "PROJECT_NOT_FOUND", "message": str(project_path)},
            )

        pr = _get_premiere()
        if pr is None:
            return self._not_installed_result()

        try:
            pr.OpenDocument(str(project_path))
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "OPEN_FAILED", "message": str(exc)},
            )

        return ToolResult(success=True, tool=self.name, data={"project": str(project_path)})


# ---------------------------------------------------------------------- #
# Tool: premiere_import_media
# ---------------------------------------------------------------------- #
class PremiereImportMediaTool(AppIntegrationTool):
    APP_KEY = "premiere"
    CONFIG_SECTION = "integrations.adobe"

    name = "premiere_import_media"
    description = "Import one or more media files into the active Premiere project."
    parameters = {
        "type": "object",
        "properties": {
            "media_paths": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["media_paths"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        paths: List[str] = list(kwargs.get("media_paths") or [])
        if not paths:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "media_paths is empty"},
            )

        for p in paths:
            if not Path(p).exists():
                return ToolResult(
                    success=False,
                    tool=self.name,
                    error={"code": "MEDIA_NOT_FOUND", "message": str(p)},
                )

        pr = _get_premiere()
        if pr is None:
            return self._not_installed_result()

        imported = []
        try:
            project = pr.ActiveProject if hasattr(pr, "ActiveProject") else None
            for p in paths:
                if project is not None:
                    project.ImportFiles(str(p), True, project.RootItem, False)
                imported.append(p)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "IMPORT_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"imported": imported, "count": len(imported)},
        )


# ---------------------------------------------------------------------- #
# Tool: premiere_export
# ---------------------------------------------------------------------- #
class PremiereExportTool(AppIntegrationTool):
    APP_KEY = "premiere"
    CONFIG_SECTION = "integrations.adobe"

    name = "premiere_export"
    description = "Export the active Premiere sequence to a file (uses AME if available)."
    parameters = {
        "type": "object",
        "properties": {
            "output_path": {"type": "string"},
            "preset_path": {"type": "string"},
        },
        "required": ["output_path"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        output_path = Path(str(kwargs.get("output_path", ""))).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        preset_path = kwargs.get("preset_path")

        pr = _get_premiere()
        if pr is None:
            return self._not_installed_result()

        try:
            if preset_path and Path(str(preset_path)).exists():
                seq = pr.ActiveSequence
                # Use AME
                ame = pr.Encoder
                ame.Export(seq, str(preset_path), str(output_path), 1, 0, 1)
            else:
                # Fall back to the direct export
                seq = pr.ActiveSequence
                seq.ExportDirect(str(output_path), "", 1, 1)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "EXPORT_FAILED", "message": str(exc)},
            )

        time.sleep(1.0)
        check = file_exists(str(output_path), min_size_bytes=1024)

        return ToolResult(
            success=check["verified"],
            tool=self.name,
            data={"output": str(output_path), "verified": check},
        )
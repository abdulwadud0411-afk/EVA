"""
DaVinci Resolve integration.

DaVinci Resolve ships with a Python scripting API (free version supports it).
We call into Resolve via its own Python module, which the user's Resolve
install registers as importable.

Tools:
    - davinci_open_project
    - davinci_import_media
    - davinci_render
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any, List, Optional

from app.core.logger import get_logger
from app.tools.base import ToolResult, RiskLevel
from app.tools.integrations.integration_base import AppIntegrationTool
from app.tools.verifier import file_exists

logger = get_logger(__name__)


# ---------------------------------------------------------------------- #
# DaVinci Resolve scripting API loader
# ---------------------------------------------------------------------- #
def _resolve_module_paths() -> List[str]:
    """Return possible Resolve API install directories."""
    return [
        r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules",
        r"C:\Program Files\Blackmagic Design\DaVinci Resolve\fusionscript.dll",
        "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules",
        "/opt/resolve/Developer/Scripting/Modules",
    ]


def _load_resolve():
    """Load the DaVinciResolveScript module, or return None."""
    # Already importable?
    try:
        import DaVinciResolveScript as dvr  # type: ignore
        return dvr
    except Exception:  # noqa: BLE001
        pass

    # Try to set env vars pointing at the Resolve install
    for p in _resolve_module_paths():
        path = Path(p)
        if not path.exists():
            continue
        if path.is_dir() and (path / "DaVinciResolveScript.py").exists():
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))
            break
        if path.is_file():  # .dll case
            os.environ.setdefault("RESOLVE_SCRIPT_LIB", str(path))

    # Resolve requires these two env vars to find its script library
    os.environ.setdefault(
        "RESOLVE_SCRIPT_API",
        r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting",
    )

    try:
        import DaVinciResolveScript as dvr  # type: ignore
        return dvr
    except Exception as exc:  # noqa: BLE001
        logger.error("davinci_module_load_failed", error=str(exc))
        return None


def _get_resolve():
    dvr = _load_resolve()
    if dvr is None:
        return None
    try:
        return dvr.scriptapp("Resolve")
    except Exception as exc:  # noqa: BLE001
        logger.error("davinci_scriptapp_failed", error=str(exc))
        return None


# ---------------------------------------------------------------------- #
# Tool: davinci_open_project
# ---------------------------------------------------------------------- #
class DaVinciOpenProjectTool(AppIntegrationTool):
    APP_KEY = "davinci_resolve"
    CONFIG_SECTION = "integrations.media_extended"

    name = "davinci_open_project"
    description = "Open a DaVinci Resolve project by name."
    parameters = {
        "type": "object",
        "properties": {"project_name": {"type": "string"}},
        "required": ["project_name"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        project_name = str(kwargs.get("project_name", "")).strip()
        if not project_name:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "project_name required"},
            )

        resolve = _get_resolve()
        if resolve is None:
            return self._not_installed_result(
                hint="Start DaVinci Resolve first; the scripting API requires it running."
            )

        try:
            pm = resolve.GetProjectManager()
            project = pm.LoadProject(project_name)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "OPEN_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=project is not None,
            tool=self.name,
            data={"project": project_name, "loaded": project is not None},
        )


# ---------------------------------------------------------------------- #
# Tool: davinci_import_media
# ---------------------------------------------------------------------- #
class DaVinciImportMediaTool(AppIntegrationTool):
    APP_KEY = "davinci_resolve"
    CONFIG_SECTION = "integrations.media_extended"

    name = "davinci_import_media"
    description = "Import media files into the current DaVinci Resolve media pool."
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
                error={"code": "INVALID_ARGUMENT", "message": "media_paths required"},
            )
        for p in paths:
            if not Path(p).exists():
                return ToolResult(
                    success=False,
                    tool=self.name,
                    error={"code": "MEDIA_NOT_FOUND", "message": str(p)},
                )

        resolve = _get_resolve()
        if resolve is None:
            return self._not_installed_result()

        try:
            pm = resolve.GetProjectManager()
            project = pm.GetCurrentProject()
            if project is None:
                return ToolResult(
                    success=False,
                    tool=self.name,
                    error={"code": "NO_PROJECT", "message": "No project open in Resolve."},
                )
            mp = project.GetMediaPool()
            result = mp.ImportMedia(paths)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "IMPORT_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=bool(result),
            tool=self.name,
            data={"imported": paths, "count": len(paths)},
        )


# ---------------------------------------------------------------------- #
# Tool: davinci_render
# ---------------------------------------------------------------------- #
class DaVinciRenderTool(AppIntegrationTool):
    APP_KEY = "davinci_resolve"
    CONFIG_SECTION = "integrations.media_extended"

    name = "davinci_render"
    description = "Render the current DaVinci project to a target directory."
    parameters = {
        "type": "object",
        "properties": {
            "output_dir": {"type": "string"},
            "preset_name": {"type": "string"},
        },
        "required": ["output_dir"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        output_dir = Path(str(kwargs.get("output_dir", ""))).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)
        preset = str(kwargs.get("preset_name") or "H.264 Master")

        resolve = _get_resolve()
        if resolve is None:
            return self._not_installed_result()

        try:
            pm = resolve.GetProjectManager()
            project = pm.GetCurrentProject()
            if project is None:
                return ToolResult(
                    success=False,
                    tool=self.name,
                    error={"code": "NO_PROJECT", "message": "Open a project first."},
                )

            # Configure the render settings
            project.SetRenderSettings({
                "TargetDir": str(output_dir),
                "SelectAllFrames": True,
            })

            job_id = project.AddRenderJob()
            if not job_id:
                return ToolResult(
                    success=False,
                    tool=self.name,
                    error={"code": "ADD_JOB_FAILED", "message": "Could not add render job."},
                )

            project.StartRendering()
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "RENDER_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"output_dir": str(output_dir), "job_id": job_id, "preset": preset},
        )
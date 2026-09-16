"""
Project helpers (Common).

Tools:
    - create_project_folder     : scaffold a fresh project folder
    - duplicate_as_template     : copy a folder as a new project from a template
"""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, List

from app.core.logger import get_logger
from app.tools.base import ToolResult, RiskLevel
from app.tools.integrations.integration_base import AppIntegrationTool

logger = get_logger(__name__)


# ---------------------------------------------------------------------- #
# Tool: create_project_folder
# ---------------------------------------------------------------------- #
class CreateProjectFolderTool(AppIntegrationTool):
    APP_KEY = "filesystem"
    CONFIG_SECTION = "integrations.common"

    name = "create_project_folder"
    description = "Create a new project folder with optional subfolders."
    parameters = {
        "type": "object",
        "properties": {
            "base_dir": {"type": "string"},
            "project_name": {"type": "string"},
            "subfolders": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["base_dir", "project_name"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        base = Path(str(kwargs.get("base_dir", ""))).expanduser()
        name = str(kwargs.get("project_name", "")).strip()
        if not name:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "project_name required"},
            )

        subfolders: List[str] = list(kwargs.get("subfolders") or [])
        target = base / name

        try:
            target.mkdir(parents=True, exist_ok=True)
            for sf in subfolders:
                (target / sf).mkdir(parents=True, exist_ok=True)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "CREATE_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"project_dir": str(target), "subfolders": subfolders},
        )


# ---------------------------------------------------------------------- #
# Tool: duplicate_as_template
# ---------------------------------------------------------------------- #
class DuplicateAsTemplateTool(AppIntegrationTool):
    APP_KEY = "filesystem"
    CONFIG_SECTION = "integrations.common"

    name = "duplicate_as_template"
    description = "Copy a template folder into a new project folder."
    parameters = {
        "type": "object",
        "properties": {
            "template_dir": {"type": "string"},
            "target_dir": {"type": "string"},
        },
        "required": ["template_dir", "target_dir"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        src = Path(str(kwargs.get("template_dir", ""))).expanduser()
        dst = Path(str(kwargs.get("target_dir", ""))).expanduser()

        if not src.is_dir():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "TEMPLATE_NOT_FOUND", "message": str(src)},
            )
        if dst.exists():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "TARGET_EXISTS", "message": str(dst)},
            )

        try:
            shutil.copytree(src, dst)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "COPY_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"template": str(src), "target": str(dst)},
        )
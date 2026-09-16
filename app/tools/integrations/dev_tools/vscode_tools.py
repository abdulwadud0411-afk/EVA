"""
VS Code integration.

Uses the `code` CLI (bundled with VS Code) — no paid service.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional

from app.core.logger import get_logger
from app.tools.base import ToolResult, RiskLevel
from app.tools.integrations.integration_base import AppIntegrationTool

logger = get_logger(__name__)


def _code_cli() -> Optional[str]:
    for name in ("code", "code.cmd", "code.exe"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _run_code(args: list, timeout: int = 60) -> subprocess.CompletedProcess:
    cli = _code_cli()
    if not cli:
        raise RuntimeError("VS Code CLI (`code`) not found on PATH.")
    return subprocess.run(
        [cli] + args,
        capture_output=True, text=True, timeout=timeout,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )


# ---------------------------------------------------------------------- #
# Tool: vscode_open
# ---------------------------------------------------------------------- #
class VSCodeOpenTool(AppIntegrationTool):
    APP_KEY = "vscode"
    CONFIG_SECTION = "integrations.dev_tools"

    name = "vscode_open"
    description = "Open a file or folder in VS Code."
    parameters = {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        target = Path(str(kwargs.get("path", ""))).expanduser()
        if not target.exists():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "PATH_NOT_FOUND", "message": str(target)},
            )
        try:
            _run_code([str(target)])
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "VSCODE_FAILED", "message": str(exc)},
            )
        return ToolResult(success=True, tool=self.name, data={"opened": str(target)})


# ---------------------------------------------------------------------- #
# Tool: vscode_open_folder
# ---------------------------------------------------------------------- #
class VSCodeOpenFolderTool(AppIntegrationTool):
    APP_KEY = "vscode"
    CONFIG_SECTION = "integrations.dev_tools"

    name = "vscode_open_folder"
    description = "Open a folder in VS Code (with optional new window)."
    parameters = {
        "type": "object",
        "properties": {
            "folder": {"type": "string"},
            "new_window": {"type": "boolean"},
        },
        "required": ["folder"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        folder = Path(str(kwargs.get("folder", ""))).expanduser()
        if not folder.is_dir():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "FOLDER_NOT_FOUND", "message": str(folder)},
            )
        args = ["-n" if kwargs.get("new_window") else "-r", str(folder)]
        try:
            _run_code(args)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "VSCODE_FAILED", "message": str(exc)},
            )
        return ToolResult(success=True, tool=self.name, data={"folder": str(folder)})


# ---------------------------------------------------------------------- #
# Tool: vscode_install_extension
# ---------------------------------------------------------------------- #
class VSCodeInstallExtensionTool(AppIntegrationTool):
    APP_KEY = "vscode"
    CONFIG_SECTION = "integrations.dev_tools"

    name = "vscode_install_extension"
    description = "Install a VS Code extension by its marketplace id."
    parameters = {
        "type": "object",
        "properties": {"extension_id": {"type": "string"}},
        "required": ["extension_id"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        ext = str(kwargs.get("extension_id", "")).strip()
        if not ext:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "extension_id required"},
            )
        try:
            r = _run_code(["--install-extension", ext], timeout=180)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "VSCODE_FAILED", "message": str(exc)},
            )
        return ToolResult(
            success=r.returncode == 0,
            tool=self.name,
            data={"extension": ext, "stdout_tail": (r.stdout or "")[-500:]},
        )


# ---------------------------------------------------------------------- #
# Tool: vscode_run_command
# ---------------------------------------------------------------------- #
class VSCodeRunCommandTool(AppIntegrationTool):
    APP_KEY = "vscode"
    CONFIG_SECTION = "integrations.dev_tools"

    name = "vscode_run_command"
    description = "Run any `code` CLI subcommand (e.g. --list-extensions)."
    parameters = {
        "type": "object",
        "properties": {
            "args": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["args"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        args = [str(a) for a in (kwargs.get("args") or [])]
        if not args:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "args required"},
            )
        try:
            r = _run_code(args, timeout=180)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "VSCODE_FAILED", "message": str(exc)},
            )
        return ToolResult(
            success=r.returncode == 0,
            tool=self.name,
            data={
                "returncode": r.returncode,
                "stdout_tail": (r.stdout or "")[-1000:],
                "stderr_tail": (r.stderr or "")[-1000:],
            },
        )
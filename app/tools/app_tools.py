"""
Application-control tools (Phase 2).

Tools:
    - open_application
    - close_application
    - list_running_applications

These are LOW-risk tools: they launch / close user applications and
inspect running processes. They do NOT modify files or system state.
"""
from __future__ import annotations

import os
import subprocess
import time
from typing import Any, Dict, List, Optional

from app.core.logger import get_logger
from app.tools.base import Tool, ToolResult, RiskLevel

logger = get_logger(__name__)


# ---------------------------------------------------------------------- #
# Known application aliases -> Windows launch commands
#
# We deliberately keep this small and safe. Anything not in this map
# is looked up by trying the raw name via `where` and then `start`.
# ---------------------------------------------------------------------- #
_APP_ALIASES: Dict[str, str] = {
    "chrome": "chrome",
    "google chrome": "chrome",
    "google-chrome": "chrome",
    "firefox": "firefox",
    "mozilla firefox": "firefox",
    "edge": "msedge",
    "microsoft edge": "msedge",
    "msedge": "msedge",
    "notepad": "notepad",
    "wordpad": "write",
    "explorer": "explorer",
    "file explorer": "explorer",
    "cmd": "cmd",
    "command prompt": "cmd",
    "powershell": "powershell",
    "terminal": "wt",
    "windows terminal": "wt",
    "calculator": "calc",
    "calc": "calc",
    "paint": "mspaint",
    "mspaint": "mspaint",
    "settings": "ms-settings:",
    "snipping tool": "snippingtool",
    "task manager": "taskmgr",
    "taskmgr": "taskmgr",
    "control panel": "control",
    "vscode": "code",
    "visual studio code": "code",
    "code": "code",
}


def _normalize_name(name: str) -> str:
    """Lowercase and collapse whitespace."""
    return " ".join(name.strip().lower().split())


def _resolve_command(application: str) -> str:
    """
    Map a friendly name to a launch command.

    Unknown names are returned unchanged — Windows `start` will try
    to find them on the PATH.
    """
    normalized = _normalize_name(application)
    return _APP_ALIASES.get(normalized, normalized)


def _is_process_running(name: str) -> bool:
    """
    Best-effort check whether a process matching `name` is running.

    Uses `tasklist` (always present on Windows). Returns False on any error.
    """
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {name}.exe", "/NH"],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        output = (result.stdout or "").lower()
        return name.lower() in output and "no tasks" not in output
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------- #
# Tool: open_application
# ---------------------------------------------------------------------- #
class OpenApplicationTool(Tool):
    name = "open_application"
    description = (
        "Open an installed Windows application by name. "
        "Examples: 'chrome', 'notepad', 'calculator', 'vscode'."
    )
    parameters = {
        "type": "object",
        "properties": {
            "application": {
                "type": "string",
                "description": "Name of the application to open (e.g. 'chrome', 'notepad').",
            },
        },
        "required": ["application"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        application = str(kwargs.get("application", "")).strip()
        if not application:
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "INVALID_ARGUMENT",
                    "message": "application name is required",
                },
            )

        command = _resolve_command(application)

        # Windows: use `start` via cmd so URLs and shell: URIs work too.
        try:
            if os.name == "nt":
                # CREATE_NO_WINDOW prevents a flashing console window.
                subprocess.Popen(
                    ["cmd", "/c", "start", "", command],
                    shell=False,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            else:
                # Non-Windows fallback (dev machines / CI).
                subprocess.Popen([command], shell=False)
        except FileNotFoundError:
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "APP_NOT_FOUND",
                    "message": f"'{application}' was not found on this system.",
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("open_application_failed", error=str(exc))
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "LAUNCH_FAILED",
                    "message": f"Failed to launch '{application}': {exc}",
                },
            )

        # Give the OS a moment to start the process, then verify
        time.sleep(1.0)
        running = _is_process_running(command)

        return ToolResult(
            success=True,
            tool=self.name,
            data={
                "application": application,
                "command": command,
                "verified_running": running,
                "note": (
                    "Process confirmed running."
                    if running
                    else "Launch command sent; process not yet visible in tasklist."
                ),
            },
        )


# ---------------------------------------------------------------------- #
# Tool: close_application
# ---------------------------------------------------------------------- #
class CloseApplicationTool(Tool):
    name = "close_application"
    description = (
        "Close a running Windows application by name. "
        "Examples: 'chrome', 'notepad'."
    )
    parameters = {
        "type": "object",
        "properties": {
            "application": {
                "type": "string",
                "description": "Name of the running application to close.",
            },
        },
        "required": ["application"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = True

    async def run(self, **kwargs: Any) -> ToolResult:
        application = str(kwargs.get("application", "")).strip()
        if not application:
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "INVALID_ARGUMENT",
                    "message": "application name is required",
                },
            )

        command = _resolve_command(application)
        process_name = f"{command}.exe"

        try:
            result = subprocess.run(
                ["taskkill", "/IM", process_name, "/F"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("close_application_failed", error=str(exc))
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "CLOSE_FAILED",
                    "message": f"Failed to close '{application}': {exc}",
                },
            )

        output = ((result.stdout or "") + (result.stderr or "")).strip()
        success = result.returncode == 0 and "not found" not in output.lower()

        return ToolResult(
            success=success,
            tool=self.name,
            data={
                "application": application,
                "process_name": process_name,
                "output": output,
            },
            error=(
                None
                if success
                else {
                    "code": "PROCESS_NOT_FOUND",
                    "message": output or f"No running process named {process_name}.",
                }
            ),
        )


# ---------------------------------------------------------------------- #
# Tool: list_running_applications
# ---------------------------------------------------------------------- #
class ListRunningApplicationsTool(Tool):
    name = "list_running_applications"
    description = (
        "List processes currently running on the PC. "
        "Returns process image names (e.g. 'chrome.exe')."
    )
    parameters = {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Maximum number of results to return (default 50).",
            },
        },
        "required": [],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        try:
            limit = int(kwargs.get("limit", 50))
        except (TypeError, ValueError):
            limit = 50
        if limit <= 0 or limit > 500:
            limit = 50

        try:
            result = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "LIST_FAILED",
                    "message": f"Failed to list processes: {exc}",
                },
            )

        processes: List[str] = []
        seen: set[str] = set()
        for line in (result.stdout or "").splitlines():
            line = line.strip()
            if not line:
                continue
            # CSV format: "image","pid","session","session#","mem"
            # Just grab the first quoted field.
            first = line.split(",")[0].strip().strip('"')
            if first and first not in seen:
                seen.add(first)
                processes.append(first)
            if len(processes) >= limit:
                break

        return ToolResult(
            success=True,
            tool=self.name,
            data={
                "count": len(processes),
                "processes": processes,
            },
        )
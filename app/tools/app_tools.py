"""
Application-control tools (Phase 2 + Phase 19 patches).

Tools:
    - open_application
    - close_application
    - list_running_applications

These are LOW-risk tools: they launch / close user applications and
inspect running processes. They do NOT modify files or system state.

Phase 19 additions:
    - open_application now auto-discovers well-known apps (Blender,
      Photoshop, VS Code, ...) via `app.tools.discovery`.
    - Success is now verified: the tool returns failure if the
      process does not actually appear in `tasklist`.
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
# is looked up via `app.tools.discovery` (well-known install paths)
# or launched by its raw name (Windows `start` will search PATH).
# ---------------------------------------------------------------------- #
_APP_ALIASES: Dict[str, str] = {
    # Browsers
    "chrome": "chrome",
    "google chrome": "chrome",
    "google-chrome": "chrome",
    "chrome browser": "chrome",
    "firefox": "firefox",
    "mozilla firefox": "firefox",
    "edge": "msedge",
    "microsoft edge": "msedge",
    "msedge": "msedge",
    "brave": "brave",
    "brave browser": "brave",

    # Basics
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

    # VS Code (multiple spellings)
    "vscode": "code",
    "vs code": "code",
    "vs-code": "code",
    "vsc": "code",
    "visual studio code": "code",
    "visual-studio-code": "code",
    "code": "code",

    # Creative tools
    "blender": "blender",
    "blender 3d": "blender",
    "unreal": "UnrealEditor",
    "unreal engine": "UnrealEditor",
    "photoshop": "photoshop",
    "adobe photoshop": "photoshop",
    "illustrator": "illustrator",
    "adobe illustrator": "illustrator",
    "premiere": "Adobe Premiere Pro",
    "adobe premiere": "Adobe Premiere Pro",
    "after effects": "AfterFX",
    "obs": "obs64",
    "obs studio": "obs64",

    # Office
    "word": "WINWORD",
    "excel": "EXCEL",
    "powerpoint": "POWERPNT",
    "outlook": "OUTLOOK",
    "onenote": "ONENOTE",

    # Communication
    "discord": "Discord",
    "telegram": "Telegram",
    "whatsapp": "WhatsApp",
    "zoom": "Zoom",
    "slack": "slack",
    "spotify": "Spotify",
}


def _normalize_name(name: str) -> str:
    """Lowercase and collapse whitespace."""
    return " ".join(name.strip().lower().split())


def _resolve_command(application: str) -> str:
    """
    Map a friendly name to a launch command.

    Resolution order:
        1. Friendly alias table (chrome, notepad, ...)
        2. Auto-discovery via `app.tools.discovery` for well-known
           apps (Blender, Photoshop, VS Code, ...)
        3. Fallback: raw name (Windows `start` will search PATH).
    """
    normalized = _normalize_name(application)

    # 1. Alias table
    alias = _APP_ALIASES.get(normalized)
    if alias is not None and not _is_path_like(alias):
        # For simple commands (notepad, chrome, ...) try discovery
        # first to get the real install path if available.
        try:
            from app.tools.discovery import APP_HINTS, discover_known_app
            if normalized in APP_HINTS:
                found = discover_known_app(normalized)
                if found:
                    logger.info(
                        "open_application_discovered",
                        application=normalized,
                        path=found,
                    )
                    return found
        except Exception as exc:  # noqa: BLE001
            logger.warning("app_discovery_failed", app=normalized, error=str(exc))
        return alias

    # 2. Auto-discovery for known install candidates
    try:
        from app.tools.discovery import APP_HINTS, discover_known_app
        if normalized in APP_HINTS:
            found = discover_known_app(normalized)
            if found:
                logger.info(
                    "open_application_discovered",
                    application=normalized,
                    path=found,
                )
                return found
    except Exception as exc:  # noqa: BLE001
        logger.warning("app_discovery_failed", app=normalized, error=str(exc))

    # 3. Raw fallback
    return normalized


def _is_path_like(value: str) -> bool:
    """Return True if the value looks like an absolute path."""
    if not value:
        return False
    if "\\" in value or "/" in value:
        return True
    if len(value) >= 2 and value[1] == ":":
        return True
    return False


def _is_process_running(name: str) -> bool:
    """
    Best-effort check whether a process matching `name` is running.

    `name` may be a full path or a bare executable name. Uses
    `tasklist` (always present on Windows). Returns False on any error.
    """
    if not name:
        return False
    # Extract the executable base name from a full path if needed.
    base = os.path.basename(name) if ("\\" in name or "/" in name) else name
    if base.lower().endswith(".exe"):
        base = base[:-4]

    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {base}.exe", "/NH"],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        output = (result.stdout or "").lower()
        return base.lower() in output and "no tasks" not in output
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------- #
# Tool: open_application
# ---------------------------------------------------------------------- #
class OpenApplicationTool(Tool):
    name = "open_application"
    description = (
        "Open an installed Windows application by name. "
        "Examples: 'chrome', 'notepad', 'calculator', 'vscode', 'blender'."
    )
    parameters = {
        "type": "object",
        "properties": {
            "application": {
                "type": "string",
                "description": "Name of the application to open.",
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

        # Windows: use `start` so URLs and shell: URIs work too.
        try:
            if os.name == "nt":
                subprocess.Popen(
                    ["cmd", "/c", "start", "", command],
                    shell=False,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            else:
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

        # Give the OS a moment to start the process, then verify.
        time.sleep(1.5)
        running = _is_process_running(command)

        if not running:
            return ToolResult(
                success=False,
                tool=self.name,
                data={
                    "application": application,
                    "command": command,
                    "verified_running": False,
                },
                error={
                    "code": "LAUNCH_NOT_VERIFIED",
                    "message": (
                        f"Launch command sent for '{application}' but "
                        f"the process is not running. Check that it is "
                        f"installed, or configure an explicit path."
                    ),
                },
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={
                "application": application,
                "command": command,
                "verified_running": True,
                "note": "Process confirmed running.",
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
        base = os.path.basename(command) if ("\\" in command or "/" in command) else command
        if base.lower().endswith(".exe"):
            process_name = base
        else:
            process_name = f"{base}.exe"

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
        seen: set = set()
        for line in (result.stdout or "").splitlines():
            line = line.strip()
            if not line:
                continue
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
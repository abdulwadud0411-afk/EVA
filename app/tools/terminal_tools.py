"""
Terminal tool (Phase 19).

HIGH-RISK tool — runs shell commands after CommandGuard validation.

Two-step process:
    1. CommandGuard classifies the command.
    2. If not allowlisted, the tool returns requires_confirmation=True
       and the caller (agent) prompts the user before re-running.
    3. If allowlisted, the command runs immediately.
"""
from __future__ import annotations

import os
import subprocess
import time
from typing import Any, List

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger
from app.security.command_guard import CommandGuard
from app.tools.base import Tool, ToolResult, RiskLevel

logger = get_logger(__name__)


class RunTerminalCommandTool(Tool):
    name = "run_terminal_command"
    description = (
        "Run a shell command. Allowlisted commands run immediately; "
        "others require user confirmation. Dangerous commands are blocked."
    )
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string"},
            "cwd": {"type": "string"},
            "timeout_seconds": {"type": "integer"},
            "confirmed": {"type": "boolean"},
        },
        "required": ["command"],
    }
    risk_level = RiskLevel.HIGH
    requires_confirmation = True

    async def run(self, **kwargs: Any) -> ToolResult:
        command = str(kwargs.get("command", "")).strip()
        if not command:
            return ToolResult(success=False, tool=self.name, error={
                "code": "INVALID_ARGUMENT", "message": "command is required",
            })

        cwd = kwargs.get("cwd")
        if cwd:
            cwd = str(cwd).strip() or None

        try:
            timeout = int(kwargs.get("timeout_seconds", 60))
        except (TypeError, ValueError):
            timeout = 60
        if timeout <= 0 or timeout > 3600:
            timeout = 60

        user_confirmed = bool(kwargs.get("confirmed", False))

        decision = CommandGuard.check(command)

        # Hard blocked
        if decision.matched_rule == "blocklist":
            logger.warning("terminal_blocked", command=command[:200])
            return ToolResult(success=False, tool=self.name, error={
                "code": "COMMAND_BLOCKED",
                "message": decision.reason,
            })

        # Not allowlisted → needs confirmation
        if decision.requires_confirmation and not user_confirmed:
            return ToolResult(success=False, tool=self.name, error={
                "code": "CONFIRMATION_REQUIRED",
                "message": (
                    f"Command '{command}' is not on the allowlist. "
                    f"Re-run with confirmed=true after user approval."
                ),
            })

        started = time.perf_counter()
        logger.info(
            "terminal_executing",
            command=command[:200],
            cwd=cwd,
            confirmed=user_confirmed,
        )

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=(
                    subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                ),
            )
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, tool=self.name, error={
                "code": "TIMEOUT",
                "message": f"Command exceeded {timeout}s.",
            })
        except Exception as exc:  # noqa: BLE001
            return ToolResult(success=False, tool=self.name, error={
                "code": "EXEC_FAILED", "message": str(exc),
            })

        duration_ms = int((time.perf_counter() - started) * 1000)
        stdout = (result.stdout or "")[-8000:]
        stderr = (result.stderr or "")[-4000:]

        return ToolResult(
            success=result.returncode == 0,
            tool=self.name,
            data={
                "command": command,
                "returncode": result.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "duration_ms": duration_ms,
                "confirmed": user_confirmed,
            },
            error=(
                None
                if result.returncode == 0
                else {
                    "code": "NONZERO_EXIT",
                    "message": f"Exit code {result.returncode}: {stderr[:200]}",
                }
            ),
        )
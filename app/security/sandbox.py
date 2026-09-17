"""
Sandbox mode (Phase 20).

When EVA encounters an unknown / unverified task, it enters "sandbox"
mode where only LOW/MEDIUM-risk tools are allowed. HIGH/CRITICAL tools
are blocked until the sandbox is exited (either automatically or by
an explicit user approval).

Public API:
    from app.security.sandbox import Sandbox, SandboxViolation
    Sandbox.enter("unknown task")
    Sandbox.allow_tool("open_application", "LOW")   # -> True
    Sandbox.allow_tool("delete_file", "HIGH")       # -> False
    Sandbox.exit()
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger

logger = get_logger(__name__)


class SandboxViolation(Exception):
    """Raised when an operation is denied by sandbox mode."""


@dataclass
class SandboxState:
    active: bool = False
    reason: str = ""
    started_at: float = 0.0
    allowed_risks: List[str] = field(default_factory=lambda: ["LOW", "MEDIUM"])
    max_steps: int = 5
    steps_taken: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active": self.active,
            "reason": self.reason,
            "started_at": self.started_at,
            "allowed_risks": list(self.allowed_risks),
            "max_steps": self.max_steps,
            "steps_taken": self.steps_taken,
        }


class Sandbox:
    """Track sandbox state and gate tool calls."""

    _state = SandboxState()
    _enabled: Optional[bool] = None
    _default_max_steps: Optional[int] = None

    # ------------------------------------------------------------------ #
    # Config
    # ------------------------------------------------------------------ #
    @classmethod
    def _is_enabled(cls) -> bool:
        if cls._enabled is not None:
            return cls._enabled
        return bool(ConfigManager.get("security.sandbox.enabled", True))

    @classmethod
    def configure(
        cls,
        enabled: Optional[bool] = None,
        allowed_risks: Optional[List[str]] = None,
        max_steps: Optional[int] = None,
    ) -> None:
        if enabled is not None:
            cls._enabled = bool(enabled)
        if allowed_risks is not None:
            cls._state.allowed_risks = [r.upper() for r in allowed_risks]
        if max_steps is not None:
            cls._default_max_steps = max(1, int(max_steps))
    @classmethod
    def reload(cls) -> None:
        cls._enabled = None
        cls._default_max_steps = None
        cls._state = SandboxState()

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    @classmethod
    def enter(cls, reason: str = "unknown task") -> None:
        # Prefer explicit max_steps from configure(); fall back to config.
        if cls._default_max_steps is not None:
            max_steps = cls._default_max_steps
        else:
            max_steps = int(
                ConfigManager.get("security.sandbox.max_sandbox_steps", 5)
            )
        cls._state = SandboxState(
            active=True,
            reason=reason,
            started_at=time.time(),
            allowed_risks=["LOW", "MEDIUM"],
            max_steps=max_steps,
        )
        logger.info("sandbox_entered", reason=reason, max_steps=max_steps)
    @classmethod
    def exit(cls) -> None:
        if cls._state.active:
            logger.info(
                "sandbox_exited",
                reason=cls._state.reason,
                steps=cls._state.steps_taken,
            )
        cls._state = SandboxState()

    @classmethod
    def is_active(cls) -> bool:
        return cls._state.active

    @classmethod
    def state(cls) -> SandboxState:
        return cls._state

    # ------------------------------------------------------------------ #
    # Gate
    # ------------------------------------------------------------------ #
    @classmethod
    def allow_tool(cls, tool_name: str, risk: str = "LOW") -> bool:
        """Return True if the tool may run right now."""
        if not cls._is_enabled():
            return True
        if not cls._state.active:
            return True

        risk = (risk or "LOW").upper()
        if risk not in cls._state.allowed_risks:
            logger.warning(
                "sandbox_blocked",
                tool=tool_name, risk=risk,
                allowed=cls._state.allowed_risks,
            )
            return False

        if cls._state.steps_taken >= cls._state.max_steps:
            logger.warning("sandbox_max_steps", tool=tool_name)
            return False

        cls._state.steps_taken += 1
        return True

    @classmethod
    def describe(cls) -> Dict[str, Any]:
        return {
            "enabled": cls._is_enabled(),
            "state": cls._state.to_dict(),
        }
"""
Permission & confirmation manager (Integrations Layer).

Centralizes risk-based confirmation for every integration tool.

Design:
    - RiskLevel comes from app.tools.base (LOW / MEDIUM / HIGH / CRITICAL).
    - LOW      -> always allowed.
    - MEDIUM   -> allowed, but logged.
    - HIGH     -> requires confirmation from a registered confirmer callback.
    - CRITICAL -> always requires typed confirmation from the user.

The confirmation callback is pluggable so the future GUI (Phase 21)
can replace the CLI prompt without touching any tool code.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, Dict, Optional

from app.core.logger import get_logger
from app.tools.base import RiskLevel

logger = get_logger(__name__)


# ---------------------------------------------------------------------- #
# Result types
# ---------------------------------------------------------------------- #
@dataclass
class PermissionDecision:
    """Outcome of a permission check."""
    allowed: bool
    reason: str = ""
    confirmed: bool = False


# Confirmer signature: (title, message, risk) -> bool
Confirmer = Callable[[str, str, RiskLevel], Awaitable[bool]]


# ---------------------------------------------------------------------- #
# Default CLI confirmer
# ---------------------------------------------------------------------- #
async def _cli_confirmer(title: str, message: str, risk: RiskLevel) -> bool:
    """
    Ask the user for confirmation via stdin.

    Runs in a worker thread so the asyncio loop is not blocked.
    """
    def _ask() -> bool:
        print()
        print("=" * 60)
        print(f" [!] CONFIRMATION REQUIRED  ({risk.value})")
        print(f"     {title}")
        print("-" * 60)
        for line in (message or "").splitlines():
            print(f"     {line}")
        print("=" * 60)
        try:
            answer = input("     Proceed? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return False
        return answer in {"y", "yes"}

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _ask)


# ---------------------------------------------------------------------- #
# PermissionManager
# ---------------------------------------------------------------------- #
class PermissionManager:
    """
    Central gatekeeper. Every integration tool must call `check()` before
    executing a non-LOW risk action.
    """

    _confirmer: Confirmer = _cli_confirmer
    _tool_overrides: Dict[str, RiskLevel] = {}

    # ------------------------------------------------------------------ #
    # Configuration
    # ------------------------------------------------------------------ #
    @classmethod
    def set_confirmer(cls, confirmer: Confirmer) -> None:
        """Replace the confirmation callback (e.g. from the future GUI)."""
        cls._confirmer = confirmer

    @classmethod
    def reset_confirmer(cls) -> None:
        cls._confirmer = _cli_confirmer

    @classmethod
    def set_tool_override(cls, tool_name: str, risk: RiskLevel) -> None:
        """Force a specific risk level for a tool (user override)."""
        cls._tool_overrides[tool_name.lower()] = risk

    @classmethod
    def clear_overrides(cls) -> None:
        cls._tool_overrides.clear()

    # ------------------------------------------------------------------ #
    # Check
    # ------------------------------------------------------------------ #
    @classmethod
    async def check(
        cls,
        tool_name: str,
        risk: RiskLevel,
        title: str = "",
        message: str = "",
    ) -> PermissionDecision:
        """
        Decide whether the tool is allowed to run.

        Never raises - always returns a PermissionDecision.
        """
        effective_risk = cls._tool_overrides.get(tool_name.lower(), risk)

        # LOW -> allowed silently
        if effective_risk == RiskLevel.LOW:
            return PermissionDecision(
                allowed=True, reason="low risk, auto-allowed", confirmed=False,
            )

        # MEDIUM -> allowed, logged
        if effective_risk == RiskLevel.MEDIUM:
            logger.info("permission_medium_allowed", tool=tool_name)
            return PermissionDecision(
                allowed=True, reason="medium risk, allowed with logging", confirmed=False,
            )

        # HIGH / CRITICAL -> require confirmation
        title = title or f"{tool_name} wants to run"
        message = message or f"Tool: {tool_name}\nRisk level: {effective_risk.value}"

        if effective_risk == RiskLevel.CRITICAL:
            message += "\nThis is a CRITICAL action. Type 'yes' to confirm."

        try:
            confirmed = await cls._confirmer(title, message, effective_risk)
        except Exception as exc:  # noqa: BLE001
            logger.error("permission_confirmer_failed", tool=tool_name, error=str(exc))
            return PermissionDecision(
                allowed=False, reason=f"confirmer error: {exc}", confirmed=False,
            )

        if not confirmed:
            logger.info("permission_denied", tool=tool_name, risk=effective_risk.value)
            return PermissionDecision(
                allowed=False, reason="user denied", confirmed=False,
            )

        logger.info("permission_granted", tool=tool_name, risk=effective_risk.value)
        return PermissionDecision(
            allowed=True, reason="user confirmed", confirmed=True,
        )

    # ------------------------------------------------------------------ #
    # Sync helper (for tests and simple callers)
    # ------------------------------------------------------------------ #
    @classmethod
    def check_sync(
        cls,
        tool_name: str,
        risk: RiskLevel,
    ) -> PermissionDecision:
        """Synchronous convenience - only for LOW/MEDIUM."""
        effective = cls._tool_overrides.get(tool_name.lower(), risk)
        if effective in (RiskLevel.LOW, RiskLevel.MEDIUM):
            return PermissionDecision(allowed=True, reason="sync allowed", confirmed=False)
        return PermissionDecision(
            allowed=False,
            reason="HIGH/CRITICAL require async confirmation",
            confirmed=False,
        )
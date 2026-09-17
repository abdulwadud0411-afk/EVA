"""
Confirmation gate (Phase 20).

Interactive confirmation for HIGH/CRITICAL actions.
Pluggable confirmer so the future GUI can replace the CLI prompt.

Public API:
    from app.security.confirmation import ConfirmationGate, ConfirmationRequest
    approved = await ConfirmationGate.request(tool_name, args, risk="HIGH")
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, Optional

from app.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ConfirmationRequest:
    tool_name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    risk: str = "HIGH"
    reason: str = ""
    title: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "risk": self.risk,
            "reason": self.reason,
            "title": self.title,
        }


Confirmer = Callable[[ConfirmationRequest], Awaitable[bool]]


async def _cli_confirmer(request: ConfirmationRequest) -> bool:
    def _ask() -> bool:
        print()
        print("=" * 60)
        print(f" [!] CONFIRMATION REQUIRED  ({request.risk})")
        print(f"     Tool: {request.tool_name}")
        if request.reason:
            print(f"     Reason: {request.reason}")
        if request.arguments:
            print(f"     Args: {request.arguments}")
        print("=" * 60)
        try:
            answer = input("     Proceed? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return False
        return answer in {"y", "yes"}

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _ask)


class ConfirmationGate:
    """Central place for user confirmations."""

    _confirmer: Confirmer = _cli_confirmer
    _auto_approve: bool = False

    @classmethod
    def set_confirmer(cls, confirmer: Confirmer) -> None:
        cls._confirmer = confirmer

    @classmethod
    def reset_confirmer(cls) -> None:
        cls._confirmer = _cli_confirmer

    @classmethod
    def set_auto_approve(cls, enabled: bool) -> None:
        cls._auto_approve = bool(enabled)

    @classmethod
    def is_auto_approve(cls) -> bool:
        return cls._auto_approve

    @classmethod
    async def request(
        cls,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        risk: str = "HIGH",
        reason: str = "",
        title: str = "",
    ) -> bool:
        if cls._auto_approve:
            logger.info("confirmation_auto_approved", tool=tool_name, risk=risk)
            return True

        req = ConfirmationRequest(
            tool_name=tool_name,
            arguments=dict(arguments or {}),
            risk=(risk or "HIGH").upper(),
            reason=reason,
            title=title or f"{tool_name} wants to run",
        )

        try:
            approved = await cls._confirmer(req)
        except Exception as exc:  # noqa: BLE001
            logger.error("confirmation_failed", tool=tool_name, error=str(exc))
            return False

        logger.info(
            "confirmation_result",
            tool=tool_name, risk=risk, approved=approved,
        )
        return bool(approved)

    @classmethod
    def request_sync(
        cls,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        risk: str = "HIGH",
        reason: str = "",
    ) -> bool:
        if cls._auto_approve:
            return True
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(cls.request(tool_name, arguments, risk, reason))
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(
                asyncio.run,
                cls.request(tool_name, arguments, risk, reason),
            )
            return future.result()
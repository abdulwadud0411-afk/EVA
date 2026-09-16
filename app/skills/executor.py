"""
Skill executor (Phase 15).

Runs each step of a skill through ToolRegistry, respecting
permission checks, timeouts, verification, and cancellation.

Emits events:
    SKILL_STARTED
    SKILL_STEP_STARTED
    SKILL_STEP_FINISHED
    SKILL_STEP_FAILED
    SKILL_FINISHED
    SKILL_CANCELLED
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional

from app.core.config_manager import ConfigManager
from app.core.events import Event, EventBus
from app.core.logger import get_logger
from app.skills.base import (
    Skill,
    SkillExecutionError,
    SkillResult,
    SkillStep,
)
from app.skills.registry import SkillRegistry

logger = get_logger(__name__)


class SkillExecutor:
    def __init__(self, event_bus: Optional[EventBus] = None) -> None:
        self.event_bus = event_bus or EventBus()
        self._cancel_flag = False

    # ------------------------------------------------------------------ #
    # Public
    # ------------------------------------------------------------------ #
    def cancel(self) -> None:
        """Request cancellation of the currently running skill."""
        self._cancel_flag = True

    async def execute(
        self,
        skill_name: str,
        extra_arguments: Optional[Dict[str, Any]] = None,
    ) -> SkillResult:
        if not ConfigManager.get("skills.enabled", True):
            raise SkillExecutionError("Skill system is disabled")

        skill = SkillRegistry.get_skill(skill_name)
        if skill is None:
            raise SkillExecutionError(f"Skill not found: {skill_name}")

        self._cancel_flag = False
        start = time.perf_counter()

        self.event_bus.publish(Event("SKILL_STARTED", {
            "skill": skill.name,
            "steps": len(skill.steps),
        }))

        # Pre-check required tools
        try:
            from app.tools.registry import ToolRegistry
            available = set(ToolRegistry.list_tools())
            missing = [t for t in skill.required_tools if t and t not in available]
            if missing:
                duration_ms = int((time.perf_counter() - start) * 1000)
                err = {
                    "code": "MISSING_TOOLS",
                    "message": f"Required tools not available: {missing}",
                }
                self.event_bus.publish(Event("SKILL_FINISHED", err))
                return SkillResult(
                    success=False,
                    skill_name=skill.name,
                    steps_total=len(skill.steps),
                    steps_completed=0,
                    error=err,
                    duration_ms=duration_ms,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("skill_precheck_failed", error=str(exc))

        results: List[Dict[str, Any]] = []
        completed = 0

        for step in skill.steps:
            if self._cancel_flag:
                duration_ms = int((time.perf_counter() - start) * 1000)
                self.event_bus.publish(Event("SKILL_CANCELLED", {"skill": skill.name}))
                return SkillResult(
                    success=False,
                    skill_name=skill.name,
                    steps_total=len(skill.steps),
                    steps_completed=completed,
                    results=results,
                    error={"code": "CANCELLED", "message": "Cancelled by user"},
                    duration_ms=duration_ms,
                    cancelled=True,
                )

            step_result = await self._run_step(step, extra_arguments)

            results.append({
                "index": step.index,
                "action": step.action,
                "tool": step.tool_name,
                "result": step_result,
            })

            if not step_result.get("success"):
                if step.optional:
                    logger.info("optional_step_failed", index=step.index)
                    continue
                duration_ms = int((time.perf_counter() - start) * 1000)
                err = step_result.get("error") or {
                    "code": "STEP_FAILED",
                    "message": f"Step {step.index} failed",
                }
                self.event_bus.publish(Event("SKILL_FINISHED", {
                    "skill": skill.name,
                    "success": False,
                    "failed_at": step.index,
                }))
                return SkillResult(
                    success=False,
                    skill_name=skill.name,
                    steps_total=len(skill.steps),
                    steps_completed=completed,
                    results=results,
                    error=err,
                    duration_ms=duration_ms,
                )

            completed += 1

        duration_ms = int((time.perf_counter() - start) * 1000)

        # Optional post-skill verification
        verified = True
        if ConfigManager.get("skills.auto_verify", True) and skill.verification:
            try:
                from app.skills.verifier import SkillVerifier
                verified = await SkillVerifier().verify(skill)
            except Exception as exc:  # noqa: BLE001
                logger.warning("skill_verification_failed", error=str(exc))
                verified = False

        self.event_bus.publish(Event("SKILL_FINISHED", {
            "skill": skill.name,
            "success": True,
            "verified": verified,
        }))

        return SkillResult(
            success=True,
            skill_name=skill.name,
            steps_total=len(skill.steps),
            steps_completed=completed,
            results=results,
            duration_ms=duration_ms,
        )

    # ------------------------------------------------------------------ #
    # Step
    # ------------------------------------------------------------------ #
    async def _run_step(
        self,
        step: SkillStep,
        extra_arguments: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.event_bus.publish(Event("SKILL_STEP_STARTED", {
            "index": step.index,
            "action": step.action,
            "tool": step.tool_name,
        }))

        # Steps without a tool are informational only.
        if not step.tool_name:
            self.event_bus.publish(Event("SKILL_STEP_FINISHED", {
                "index": step.index,
                "success": True,
                "note": "no-tool step",
            }))
            return {"success": True, "note": "no-tool step"}

        arguments = dict(step.arguments or {})
        if extra_arguments:
            arguments.update(extra_arguments)

        timeout = int(step.timeout_seconds
                      or ConfigManager.get("skills.step_timeout_seconds", 60))
        max_retries = int(ConfigManager.get("skills.max_retries_per_step", 1))

        last_error: Optional[Dict[str, Any]] = None
        for attempt in range(max_retries + 1):
            if self._cancel_flag:
                return {"success": False, "error": {"code": "CANCELLED", "message": "cancelled"}}

            try:
                from app.tools.registry import ToolRegistry
                result = await asyncio.wait_for(
                    ToolRegistry.execute(step.tool_name, arguments),
                    timeout=timeout,
                )
                payload = result.to_dict() if hasattr(result, "to_dict") else {
                    "success": getattr(result, "success", False),
                    "tool": step.tool_name,
                    "data": getattr(result, "data", None),
                    "error": getattr(result, "error", None),
                }

                if payload.get("success"):
                    self.event_bus.publish(Event("SKILL_STEP_FINISHED", {
                        "index": step.index,
                        "success": True,
                    }))
                    return payload
                last_error = payload.get("error") or {
                    "code": "TOOL_FAILED",
                    "message": f"{step.tool_name} returned failure",
                }
            except asyncio.TimeoutError:
                last_error = {"code": "TIMEOUT", "message": f"Step timed out after {timeout}s"}
            except Exception as exc:  # noqa: BLE001
                last_error = {"code": "EXCEPTION", "message": str(exc)}

            logger.warning(
                "skill_step_retry",
                index=step.index,
                attempt=attempt,
                error=last_error,
            )

        self.event_bus.publish(Event("SKILL_STEP_FAILED", {
            "index": step.index,
            "error": last_error,
        }))
        return {"success": False, "error": last_error}
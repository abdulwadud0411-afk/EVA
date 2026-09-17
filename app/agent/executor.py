"""
Executor (Phase 16).

Runs a Plan step by step through the ToolRegistry.
On failure, asks the Recovery handler for an alternative step.

Public API:
    executor = Executor(event_bus=bus)
    result = await executor.execute(plan, recovery=recovery)
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from app.agent.planner import Plan, PlanStep
from app.core.config_manager import ConfigManager
from app.core.events import Event, EventBus
from app.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class StepResult:
    step: PlanStep
    success: bool
    result: Dict[str, Any] = field(default_factory=dict)
    error: Optional[Dict[str, str]] = None
    duration_ms: int = 0
    retries: int = 0
    skipped: bool = False


@dataclass
class ExecutionResult:
    goal: str
    success: bool
    steps_total: int
    steps_completed: int
    results: List[StepResult] = field(default_factory=list)
    final_message: str = ""
    duration_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "success": self.success,
            "steps_total": self.steps_total,
            "steps_completed": self.steps_completed,
            "final_message": self.final_message,
            "duration_ms": self.duration_ms,
            "results": [
                {
                    "step": r.step.to_dict(),
                    "success": r.success,
                    "result": r.result,
                    "error": r.error,
                    "duration_ms": r.duration_ms,
                    "retries": r.retries,
                    "skipped": r.skipped,
                }
                for r in self.results
            ],
        }


class ExecutorError(Exception):
    """Raised when execution itself fails (not a step failure)."""


class Executor:
    def __init__(self, event_bus: Optional[EventBus] = None) -> None:
        self.event_bus = event_bus or EventBus()
        self.step_timeout = int(
            ConfigManager.get("agent.executor.step_timeout_seconds", 60)
        )
        self.stop_on_first_failure = bool(
            ConfigManager.get("agent.executor.stop_on_first_failure", False)
        )

    async def execute(
        self,
        plan: Plan,
        recovery: Optional[Any] = None,
        cancel_flag: Optional[Callable[[], bool]] = None,
    ) -> ExecutionResult:
        start = time.perf_counter()
        results: List[StepResult] = []
        completed = 0

        self.event_bus.publish(Event("EXECUTION_STARTED", {
            "goal": plan.goal,
            "steps": len(plan.steps),
        }))

        for step in plan.steps:
            if cancel_flag is not None and cancel_flag():
                logger.info("execution_cancelled", step=step.index)
                self.event_bus.publish(Event("EXECUTION_CANCELLED", {}))
                return ExecutionResult(
                    goal=plan.goal,
                    success=False,
                    steps_total=len(plan.steps),
                    steps_completed=completed,
                    results=results,
                    final_message="Cancelled by user.",
                    duration_ms=int((time.perf_counter() - start) * 1000),
                )

            step_result = await self._run_step(step)
            results.append(step_result)

            if step_result.success:
                completed += 1
                continue

            if getattr(step, "optional", False):
                logger.info("optional_step_failed", index=step.index)
                continue

            if recovery is not None:
                recovered = await self._try_recovery(
                    step, step_result, recovery, results,
                )
                if recovered:
                    completed += 1
                    continue

            if self.stop_on_first_failure or step.critical:
                logger.warning("critical_step_failed_stopping", index=step.index)
                break

        success = completed == len(plan.steps)
        duration_ms = int((time.perf_counter() - start) * 1000)
        final = self._build_final_message(plan, completed, success)

        self.event_bus.publish(Event("EXECUTION_FINISHED", {
            "goal": plan.goal,
            "success": success,
            "completed": completed,
            "total": len(plan.steps),
            "duration_ms": duration_ms,
        }))

        return ExecutionResult(
            goal=plan.goal,
            success=success,
            steps_total=len(plan.steps),
            steps_completed=completed,
            results=results,
            final_message=final,
            duration_ms=duration_ms,
        )

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    async def _run_step(self, step: PlanStep) -> StepResult:
        started = time.perf_counter()

        self.event_bus.publish(Event("PLAN_STEP_STARTED", {
            "index": step.index,
            "action": step.action,
            "tool": step.tool_name,
        }))

        if not step.tool_name:
            duration_ms = int((time.perf_counter() - started) * 1000)
            self.event_bus.publish(Event("PLAN_STEP_FINISHED", {
                "index": step.index,
                "success": True,
                "note": "no-tool step",
            }))
            return StepResult(
                step=step,
                success=True,
                result={"note": "no-tool step"},
                duration_ms=duration_ms,
            )

        try:
            from app.tools.registry import ToolRegistry
            result = await asyncio.wait_for(
                ToolRegistry.execute(step.tool_name, dict(step.arguments or {})),
                timeout=self.step_timeout,
            )
        except asyncio.TimeoutError:
            duration_ms = int((time.perf_counter() - started) * 1000)
            err = {
                "code": "TIMEOUT",
                "message": f"step timed out after {self.step_timeout}s",
            }
            self.event_bus.publish(Event("PLAN_STEP_FAILED", {
                "index": step.index, "error": err,
            }))
            return StepResult(step=step, success=False, error=err, duration_ms=duration_ms)
        except Exception as exc:  # noqa: BLE001
            duration_ms = int((time.perf_counter() - started) * 1000)
            err = {"code": "EXCEPTION", "message": str(exc)}
            self.event_bus.publish(Event("PLAN_STEP_FAILED", {
                "index": step.index, "error": err,
            }))
            return StepResult(step=step, success=False, error=err, duration_ms=duration_ms)

        duration_ms = int((time.perf_counter() - started) * 1000)
        payload = result.to_dict() if hasattr(result, "to_dict") else dict(result)

        if payload.get("success"):
            self.event_bus.publish(Event("PLAN_STEP_FINISHED", {
                "index": step.index, "success": True,
            }))
            return StepResult(
                step=step,
                success=True,
                result=payload.get("data") or {},
                duration_ms=duration_ms,
            )

        err = payload.get("error") or {"code": "TOOL_FAILED", "message": "unknown"}
        self.event_bus.publish(Event("PLAN_STEP_FAILED", {
            "index": step.index, "error": err,
        }))
        return StepResult(step=step, success=False, error=err, duration_ms=duration_ms)

    async def _try_recovery(
        self,
        step: PlanStep,
        failed: StepResult,
        recovery: Any,
        results: List[StepResult],
    ) -> bool:
        try:
            recovered = await recovery.attempt(
                step=step,
                failure=failed.error or {},
                attempt=1,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("recovery_failed", error=str(exc))
            return False

        if not recovered or not recovered.alternative_step:
            return False

        alt = recovered.alternative_step
        logger.info(
            "executor_retry_with_alternative",
            index=step.index,
            alt=alt.action,
        )

        alt_result = await self._run_step(alt)
        alt_result.retries = 1
        results.append(alt_result)
        return alt_result.success

    def _build_final_message(
        self,
        plan: Plan,
        completed: int,
        success: bool,
    ) -> str:
        if success:
            return f"Completed all {len(plan.steps)} steps for: {plan.goal}"
        return (
            f"Completed {completed}/{len(plan.steps)} steps for: {plan.goal}. "
            f"Some steps failed — check logs."
        )
"""
Agent verifier (Phase 16).

Verifies that executed steps actually achieved their intent.

Strategy:
    1. Structured spec in `expected_result`:
         "file_exists:<path>"
         "process_running:<name>"
         "active_window_contains:<substring>"
    2. Free-text expectation -> optional vision check (config-gated)
    3. Fallback: trust the tool if it reported success.

Public API:
    v = AgentVerifier()
    res = await v.verify_step(step, result_dict)
    res = await v.verify_plan(plan, execution_result)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.agent.planner import Plan, PlanStep
from app.core.config_manager import ConfigManager
from app.core.events import Event, EventBus
from app.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class VerifyResult:
    verified: bool
    reason: str = ""
    checks: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verified": self.verified,
            "reason": self.reason,
            "checks": self.checks,
        }


class AgentVerifier:
    def __init__(self, event_bus: Optional[EventBus] = None) -> None:
        self.event_bus = event_bus or EventBus()
        self.enabled = bool(ConfigManager.get("agent.verification.enabled", True))
        self.use_vision = bool(ConfigManager.get("agent.verification.use_vision", False))

    # ------------------------------------------------------------------ #
    # Step verification
    # ------------------------------------------------------------------ #
    async def verify_step(
        self,
        step: PlanStep,
        result: Dict[str, Any],
    ) -> VerifyResult:
        if not self.enabled:
            return VerifyResult(verified=True, reason="verification disabled")

        if not result.get("success", False):
            return VerifyResult(
                verified=False,
                reason="tool reported failure",
            )

        spec = (step.expected_result or "").strip()
        if not spec:
            return VerifyResult(verified=True, reason="no explicit expectation")

        check = self._run_spec_check(spec)
        if check is not None:
            return check

        if self.use_vision:
            vision = await self._vision_check(step)
            if vision is not None:
                return vision

        return VerifyResult(
            verified=True,
            reason=f"no matching verifier for: {spec[:80]}",
        )

    async def verify_plan(
        self,
        plan: Plan,
        execution: Any,
    ) -> VerifyResult:
        checks: List[Dict[str, Any]] = []
        all_ok = True
        for step_result in getattr(execution, "results", []) or []:
            if getattr(step_result, "skipped", False):
                continue
            r = await self.verify_step(
                step_result.step,
                {
                    "success": step_result.success,
                    "data": step_result.result,
                    "error": step_result.error,
                },
            )
            checks.append({
                "index": step_result.step.index,
                "action": step_result.step.action,
                "verified": r.verified,
                "reason": r.reason,
            })
            if not r.verified:
                all_ok = False

        self.event_bus.publish(Event("PLAN_VERIFIED", {
            "goal": plan.goal,
            "verified": all_ok,
            "checks": len(checks),
        }))

        return VerifyResult(
            verified=all_ok,
            reason="all steps verified" if all_ok else "some steps failed verification",
            checks=checks,
        )

    # ------------------------------------------------------------------ #
    # Spec parsing
    # ------------------------------------------------------------------ #
    def _run_spec_check(self, spec: str) -> Optional[VerifyResult]:
        lowered = spec.lower()

        if lowered.startswith("file_exists:"):
            path = spec.split(":", 1)[1].strip()
            from app.tools.verifier import file_exists
            r = file_exists(path)
            return VerifyResult(
                verified=bool(r.get("verified")),
                reason=r.get("reason", ""),
                checks=[{"type": "file_exists", "path": path, "result": r}],
            )

        if lowered.startswith("process_running:"):
            name = spec.split(":", 1)[1].strip()
            from app.tools.verifier import process_running
            r = process_running(name)
            return VerifyResult(
                verified=bool(r.get("verified")),
                reason=r.get("reason", ""),
                checks=[{"type": "process_running", "name": name, "result": r}],
            )

        if lowered.startswith("active_window_contains:"):
            needle = spec.split(":", 1)[1].strip()
            from app.tools.verifier import active_window_title_contains
            r = active_window_title_contains(needle)
            return VerifyResult(
                verified=bool(r.get("verified")),
                reason=r.get("reason", ""),
                checks=[{
                    "type": "active_window_contains",
                    "needle": needle,
                    "result": r,
                }],
            )

        return None

    async def _vision_check(self, step: PlanStep) -> Optional[VerifyResult]:
        try:
            from app.brain.vision import VisionClient
            from app.tools.screen_tools import capture_for_vision
        except Exception:  # noqa: BLE001
            return None

        try:
            image = capture_for_vision()
        except Exception:  # noqa: BLE001
            return None

        prompt = (
            "Answer with a single line: DID_SUCCEED or DID_FAIL. "
            f"Action that was attempted: {step.action}. "
            f"Expected outcome: {step.expected_result or 'no description'}."
        )
        try:
            client = VisionClient()
            result = await client.analyze_image(image, prompt=prompt)
        except Exception as exc:  # noqa: BLE001
            logger.warning("agent_verifier_vision_failed", error=str(exc))
            return None

        text = (result.get("text") or "").upper()
        verified = "DID_SUCCEED" in text or "SUCCESS" in text
        return VerifyResult(
            verified=verified,
            reason="vision check",
            checks=[{"type": "vision", "response": text[:200]}],
        )
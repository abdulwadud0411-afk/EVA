"""
Recovery (Phase 16).

When a step fails, ask the AI for an alternative approach. Bounded by
`agent.recovery.max_retries`. Returns a new PlanStep to try.

Public API:
    r = Recovery(event_bus=bus)
    outcome = await r.attempt(step, failure, attempt=1)
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.agent.planner import PlanStep, _allowed_tools
from app.brain.provider_registry import ProviderRegistry
from app.core.config_manager import ConfigManager
from app.core.events import Event, EventBus
from app.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RecoveryOutcome:
    recovered: bool
    alternative_step: Optional[PlanStep] = None
    reason: str = ""
    should_skip: bool = False


_RECOVERY_PROMPT = """You are EVA's recovery planner.

A step of the plan just failed. Propose ONE alternative step that
might achieve the same goal using a different tool or different
arguments.

Return ONLY JSON in this shape:
{
  "reasoning": "<short>",
  "alternative_step": {
    "index": <same index>,
    "action": "<short human action>",
    "tool_name": "<registered tool name>",
    "arguments": {},
    "expected_result": "<how to verify>"
  }
}

If no alternative is possible, return:
{"reasoning": "no alternative", "alternative_step": null}
"""


class Recovery:
    def __init__(self, event_bus: Optional[EventBus] = None) -> None:
        self.event_bus = event_bus or EventBus()
        self.enabled = bool(ConfigManager.get("agent.recovery.enabled", True))
        self.max_retries = int(
            ConfigManager.get("agent.recovery.max_retries", 2)
        )
        self.ask_ai = bool(
            ConfigManager.get("agent.recovery.ask_ai_for_alternative", True)
        )

    async def attempt(
        self,
        step: PlanStep,
        failure: Dict[str, str],
        attempt: int = 1,
    ) -> RecoveryOutcome:
        if not self.enabled:
            return RecoveryOutcome(False, reason="recovery disabled")
        if attempt > self.max_retries:
            return RecoveryOutcome(
                False,
                reason=f"max retries ({self.max_retries}) exceeded",
            )

        self.event_bus.publish(Event("RECOVERY_STARTED", {
            "step": step.index,
            "attempt": attempt,
            "error": failure,
        }))

        if not self.ask_ai:
            outcome = self._simple_fallback(step, failure)
            self._publish_finished(step, outcome)
            return outcome

        outcome = await self._ai_alternative(step, failure, attempt)
        self._publish_finished(step, outcome)
        return outcome

    # ------------------------------------------------------------------ #
    # Simple fallbacks (no AI)
    # ------------------------------------------------------------------ #
    def _simple_fallback(
        self,
        step: PlanStep,
        failure: Dict[str, str],
    ) -> RecoveryOutcome:
        code = (failure or {}).get("code", "")
        if code in {"TIMEOUT", "EXCEPTION", "TOOL_FAILED"}:
            return RecoveryOutcome(
                recovered=True,
                alternative_step=step,
                reason="simple retry",
            )
        return RecoveryOutcome(
            False,
            reason=f"no simple fallback for {code}",
        )

    # ------------------------------------------------------------------ #
    # AI-driven alternative
    # ------------------------------------------------------------------ #
    async def _ai_alternative(
        self,
        step: PlanStep,
        failure: Dict[str, str],
        attempt: int,
    ) -> RecoveryOutcome:
        tools_hint = ", ".join(sorted(_allowed_tools())[:120]) or "(none)"
        user_msg = (
            f"FAILED STEP:\n"
            f"  action: {step.action}\n"
            f"  tool: {step.tool_name}\n"
            f"  arguments: {json.dumps(step.arguments, ensure_ascii=False)}\n"
            f"  expected_result: {step.expected_result}\n\n"
            f"FAILURE:\n"
            f"  code: {failure.get('code')}\n"
            f"  message: {failure.get('message')}\n\n"
            f"AVAILABLE_TOOLS: {tools_hint}\n"
            f"ATTEMPT: {attempt}/{self.max_retries}\n\n"
            "Propose one alternative step."
        )

        try:
            provider = ProviderRegistry.get_active_provider()
            response = await provider.generate(
                messages=[
                    {"role": "system", "content": _RECOVERY_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                tools=None,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("recovery_ai_failed", error=str(exc))
            return RecoveryOutcome(False, reason=f"AI failed: {exc}")

        text = (response.text or "").strip()
        data = self._extract_json(text)
        if not data or not data.get("alternative_step"):
            return RecoveryOutcome(False, reason="AI produced no alternative")

        alt_raw = data["alternative_step"]
        allowed = _allowed_tools()
        tool = str(alt_raw.get("tool_name") or "")
        if tool and allowed and tool not in allowed:
            return RecoveryOutcome(False, reason=f"unknown tool: {tool}")

        alt = PlanStep.from_dict({
            "index": step.index,
            "action": alt_raw.get("action", step.action),
            "tool_name": tool,
            "arguments": alt_raw.get("arguments", {}),
            "expected_result": alt_raw.get("expected_result", step.expected_result),
            "critical": step.critical,
        })

        return RecoveryOutcome(
            recovered=True,
            alternative_step=alt,
            reason=str(data.get("reasoning", "AI alternative")),
        )

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _extract_json(text: str) -> Optional[Dict[str, Any]]:
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                return None
        return None

    def _publish_finished(
        self,
        step: PlanStep,
        outcome: RecoveryOutcome,
    ) -> None:
        self.event_bus.publish(Event("RECOVERY_FINISHED", {
            "step": step.index,
            "recovered": outcome.recovered,
            "reason": outcome.reason,
        }))
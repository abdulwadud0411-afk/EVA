"""
Planner (Phase 16).

Takes a user goal, calls the AI provider with the planner prompt,
parses the JSON response into a Plan, and returns it.

Public API:
    planner = Planner()
    plan = await planner.create_plan("build a python calculator on desktop")
"""
from __future__ import annotations

import importlib
import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.brain.provider_registry import ProviderRegistry
from app.core.config_manager import ConfigManager
from app.core.events import Event, EventBus
from app.core.logger import get_logger

logger = get_logger(__name__)


_ALLOWED_TOOL_NAMES: Optional[set] = None


def _ensure_tools_registered() -> None:
    """
    Make sure `app.tools` has been imported and every tool is
    registered. If the registry was cleared (e.g. by a previous
    test), reload the package to re-run registration.
    """
    try:
        import app.tools  # noqa: F401
    except Exception:  # noqa: BLE001
        return

    try:
        from app.tools.registry import ToolRegistry
        if not ToolRegistry.list_tools():
            try:
                importlib.reload(app.tools)
            except Exception:  # noqa: BLE001
                pass
    except Exception:  # noqa: BLE001
        pass


def _allowed_tools() -> set:
    """Return the set of currently registered tool names (cached)."""
    global _ALLOWED_TOOL_NAMES
    if _ALLOWED_TOOL_NAMES is None:
        _ensure_tools_registered()
        try:
            from app.tools.registry import ToolRegistry
            _ALLOWED_TOOL_NAMES = set(ToolRegistry.list_tools())
        except Exception:  # noqa: BLE001
            _ALLOWED_TOOL_NAMES = set()
    return _ALLOWED_TOOL_NAMES


def refresh_allowed_tools() -> None:
    """Force re-read of the tool registry (used by tests)."""
    global _ALLOWED_TOOL_NAMES
    _ALLOWED_TOOL_NAMES = None


@dataclass
class PlanStep:
    index: int
    action: str
    tool_name: str = ""
    arguments: Dict[str, Any] = field(default_factory=dict)
    expected_result: str = ""
    critical: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "action": self.action,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "expected_result": self.expected_result,
            "critical": self.critical,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlanStep":
        return cls(
            index=int(data.get("index", 0)),
            action=str(data.get("action", "")),
            tool_name=str(data.get("tool_name") or ""),
            arguments=dict(data.get("arguments") or {}),
            expected_result=str(data.get("expected_result", "")),
            critical=bool(data.get("critical", True)),
        )


@dataclass
class Plan:
    goal: str
    steps: List[PlanStep] = field(default_factory=list)
    reasoning: str = ""
    raw_response: str = ""

    @property
    def is_trivial(self) -> bool:
        return len(self.steps) <= 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "reasoning": self.reasoning,
            "steps": [s.to_dict() for s in self.steps],
        }


class PlannerError(Exception):
    """Raised when planning fails."""


class Planner:
    def __init__(self, event_bus: Optional[EventBus] = None) -> None:
        self.event_bus = event_bus or EventBus()
        self.max_steps = int(ConfigManager.get("agent.planner.max_steps", 12))
        self.timeout = int(ConfigManager.get("agent.planner.timeout_seconds", 120))
        self._system_prompt = self._load_prompt()

    @staticmethod
    def _load_prompt() -> str:
        path = ConfigManager.get_project_root() / "prompts" / "planner.txt"
        if path.exists():
            try:
                text = path.read_text(encoding="utf-8").strip()
                if text:
                    return text
            except OSError:
                pass
        return (
            "You are EVA's planner. Break the user's goal into a minimal, "
            "ordered list of concrete steps. Return ONLY JSON."
        )

    async def create_plan(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Plan:
        if not goal.strip():
            raise PlannerError("Empty goal.")

        tools_hint = self._tools_hint()
        user_msg = self._build_user_message(goal, tools_hint, context)

        provider = ProviderRegistry.get_active_provider()
        self.event_bus.publish(Event("PLAN_STARTED", {"goal": goal}))

        try:
            response = await provider.generate(
                messages=[
                    {"role": "system", "content": self._system_prompt},
                    {"role": "user", "content": user_msg},
                ],
                tools=None,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("planner_generate_failed", error=str(exc))
            raise PlannerError(f"AI provider failed: {exc}") from exc

        text = (response.text or "").strip()
        plan = self._parse_plan(goal, text)

        self.event_bus.publish(Event("PLAN_READY", {
            "goal": goal,
            "steps": len(plan.steps),
        }))
        return plan

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _tools_hint() -> str:
        names = sorted(_allowed_tools())
        if not names:
            return "(no tools available)"
        shown = names[:120]
        more = "" if len(names) <= 120 else f" (+{len(names) - 120} more)"
        return ", ".join(shown) + more

    def _build_user_message(
        self,
        goal: str,
        tools_hint: str,
        context: Optional[Dict[str, Any]],
    ) -> str:
        parts = [f"GOAL: {goal}", f"AVAILABLE_TOOLS: {tools_hint}"]
        if context:
            parts.append(
                f"CONTEXT: {json.dumps(context, ensure_ascii=False)[:800]}"
            )
        parts.append(
            "Respond with a JSON object only, in this exact shape:\n"
            '{"reasoning": "<short>", "steps": ['
            '{"index": 1, "action": "<short human action>", '
            '"tool_name": "<registered tool name or empty>", '
            '"arguments": {}, '
            '"expected_result": "<how to verify>", '
            '"critical": true}'
            "]}\n"
            f"Use at most {self.max_steps} steps. "
            "If the goal is trivial (one action), return exactly one step."
        )
        return "\n\n".join(parts)

    def _parse_plan(self, goal: str, text: str) -> Plan:
        data = self._extract_json(text)
        if data is None:
            raise PlannerError("Planner returned no parseable JSON.")

        raw_steps = data.get("steps") or []
        if not isinstance(raw_steps, list):
            raise PlannerError("Plan 'steps' must be a list.")

        allowed = _allowed_tools()
        validated: List[PlanStep] = []
        for i, raw in enumerate(raw_steps, start=1):
            if not isinstance(raw, dict):
                continue
            step = PlanStep.from_dict({
                "index": raw.get("index", i),
                "action": raw.get("action", ""),
                "tool_name": raw.get("tool_name", ""),
                "arguments": raw.get("arguments", {}),
                "expected_result": raw.get("expected_result", ""),
                "critical": raw.get("critical", True),
            })
            if step.tool_name and allowed and step.tool_name not in allowed:
                logger.warning(
                    "planner_unknown_tool_rejected",
                    tool=step.tool_name,
                    step=step.index,
                )
                step.tool_name = ""
            if not step.action:
                continue
            validated.append(step)
            if len(validated) >= self.max_steps:
                break

        if not validated:
            raise PlannerError("Planner produced no valid steps.")

        return Plan(
            goal=goal,
            steps=validated,
            reasoning=str(data.get("reasoning", "")),
            raw_response=text,
        )

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict[str, Any]]:
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if fence:
            try:
                return json.loads(fence.group(1))
            except json.JSONDecodeError:
                pass
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
        return None
"""
Agent loop with memory integration (Phase 12 + Phase 16).

Flow:
    1. Handle memory commands locally (remember / what's my name).
    2. Try LOCAL intent matching (0 tokens).
    3. If request is complex → Planner + Executor + Verifier + Recovery.
    4. Otherwise → AI provider with dynamically selected tools.
    5. Save every message to persistent memory.

Memory integration:
    - Conversation history stored in SQLite (survives restarts).
    - User preferences auto-detected from "remember X" commands.
    - Memory context injected into system prompt.

Phase 16 integration:
    - Planner path engages only for long, multi-action requests.
    - Trivial plans fall back to the direct tool-calling path.
    - Planner path failure logs a warning and falls back gracefully.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple

import app.brain.providers  # noqa: F401
import app.tools  # noqa: F401

from app.agent.local_intent import match_local
from app.agent.tool_selector import select_tool_schemas
from app.brain.provider_registry import ProviderRegistry
from app.brain.ai_router import AIRouter
from app.brain.routing_rules import RoutingContext
from app.brain.response_models import AIResponse, ToolCall
from app.core.config_manager import ConfigManager
from app.core.events import Event, EventBus
from app.core.logger import get_logger
from app.core.state import app_state, TaskState
from app.tools.base import ToolResult
from app.tools.registry import ToolRegistry

logger = get_logger(__name__)


_DEFAULT_SYSTEM_PROMPT = (
    "You are EVA, a personal AI desktop assistant.\n"
    "Complete tasks with the MINIMUM number of tool calls.\n"
    "Do not repeat a tool call you already made.\n"
    "Once the task is done, respond with text immediately.\n"
)


# ---------------------------------------------------------------------- #
# Memory command patterns
# ---------------------------------------------------------------------- #
_REMEMBER_NAME_PATTERNS = [
    re.compile(
        r"^(?:eva[, ]*)?(?:please\s+)?remember\s+(?:that\s+)?my\s+name\s+is\s+(?P<value>.+?)[.!?]?$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:eva[, ]*)?(?:please\s+)?call\s+me\s+(?P<value>.+?)[.!?]?$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:eva[, ]*)?my\s+name\s+is\s+(?P<value>.+?)[.!?]?$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:eva[, ]*)?amar\s+nam\s+(?P<value>.+?)[.!?]?$",
        re.IGNORECASE,
    ),
]

_REMEMBER_LANGUAGE_PATTERNS = [
    re.compile(
        r"^(?:eva[, ]*)?(?:please\s+)?remember\s+(?:that\s+)?i\s+prefer\s+(?P<value>.+?)[.!?]?$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:eva[, ]*)?(?:please\s+)?i\s+prefer\s+(?P<value>.+?)[.!?]?$",
        re.IGNORECASE,
    ),
]

_QUERY_NAME_PATTERNS = [
    re.compile(r"^(?:eva[, ]*)?what(?:'s|\s+is)\s+my\s+name\??$", re.IGNORECASE),
    re.compile(r"^(?:eva[, ]*)?who\s+am\s+i\??$", re.IGNORECASE),
    re.compile(r"^(?:eva[, ]*)?amar\s+nam\s+ki\??$", re.IGNORECASE),
]

_FORGET_NAME_PATTERNS = [
    re.compile(r"^(?:eva[, ]*)?forget\s+my\s+name[.!?]?$", re.IGNORECASE),
]


def _load_system_prompt() -> str:
    path = ConfigManager.get_project_root() / "prompts" / "system.txt"
    if path.exists():
        try:
            text = path.read_text(encoding="utf-8").strip()
            if text:
                return text
        except OSError:
            pass
    return _DEFAULT_SYSTEM_PROMPT


def _tool_call_signature(tc: ToolCall) -> Tuple[str, str]:
    try:
        args_json = json.dumps(tc.arguments or {}, sort_keys=True, ensure_ascii=False)
    except Exception:  # noqa: BLE001
        args_json = str(tc.arguments)
    return (tc.name, args_json)


# ---------------------------------------------------------------------- #
# AgentLoop
# ---------------------------------------------------------------------- #
class AgentLoop:
    def __init__(self, event_bus: Optional[EventBus] = None) -> None:
        self.event_bus = event_bus or EventBus()
        self.history: List[Dict[str, Any]] = []
        self._system_prompt = _load_system_prompt()
        self._provider = None
        self._history_limit: int = int(ConfigManager.get("ai.history_limit", 8))
        self._max_tool_steps: int = int(ConfigManager.get("agent.max_steps", 6))
        self._local_intent_enabled: bool = bool(
            ConfigManager.get("agent.local_intent_enabled", True)
        )
        self._dynamic_tools_enabled: bool = bool(
            ConfigManager.get("agent.dynamic_tools_enabled", True)
        )
        self._detect_duplicates: bool = bool(
            ConfigManager.get("agent.detect_duplicate_tool_calls", True)
        )

        # TTS
        self._speak_controller = None
        self._speak_enabled: bool = bool(
            ConfigManager.get("voice.speak_responses", True)
        )
        self._speak_only_voice: bool = bool(
            ConfigManager.get("voice.speak_only_in_voice_mode", True)
        )
        self._voice_turn: bool = False

        # Memory (Phase 12)
        self._memory_enabled: bool = False
        self._conversation = None
        try:
            from app.memory.memory import MemoryStore
            MemoryStore.init()
            self._conversation = MemoryStore.conversation()
            self._memory_enabled = True
            logger.info("agent_memory_enabled")
        except Exception as exc:  # noqa: BLE001
            logger.warning("agent_memory_disabled", error=str(exc))

    # ------------------------------------------------------------------ #
    # TTS
    # ------------------------------------------------------------------ #
    def _get_speak_controller(self):
        if self._speak_controller is None:
            try:
                from app.voice.tts import SpeakController
                self._speak_controller = SpeakController()
            except Exception as exc:  # noqa: BLE001
                logger.error("tts_controller_load_failed", error=str(exc))
                self._speak_controller = None
        return self._speak_controller

    async def _speak(self, text: str) -> None:
        if not self._speak_enabled:
            return
        if self._speak_only_voice and not self._voice_turn:
            return
        controller = self._get_speak_controller()
        if controller is None:
            return
        try:
            await controller.speak(text)
        except Exception as exc:  # noqa: BLE001
            logger.error("speak_failed", error=str(exc))

    # ------------------------------------------------------------------ #
    # Memory helpers
    # ------------------------------------------------------------------ #
    def _memory_save_user(self, text: str) -> None:
        if not self._memory_enabled or self._conversation is None:
            return
        try:
            self._conversation.append_user(text)
        except Exception as exc:  # noqa: BLE001
            logger.warning("memory_save_user_failed", error=str(exc))

    def _memory_save_assistant(self, text: str) -> None:
        if not self._memory_enabled or self._conversation is None:
            return
        try:
            self._conversation.append_assistant(text)
        except Exception as exc:  # noqa: BLE001
            logger.warning("memory_save_assistant_failed", error=str(exc))

    def _memory_save_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
        result: Dict[str, Any],
    ) -> None:
        if not self._memory_enabled or self._conversation is None:
            return
        try:
            self._conversation.append_tool(name, arguments, result)
        except Exception as exc:  # noqa: BLE001
            logger.warning("memory_save_tool_failed", error=str(exc))

    def _try_memory_command(self, text: str) -> Optional[str]:
        """Handle remember / forget / query commands locally. 0 tokens."""
        if not self._memory_enabled:
            return None

        from app.memory.memory import MemoryStore

        # Name save
        for pat in _REMEMBER_NAME_PATTERNS:
            m = pat.match(text)
            if m:
                value = m.group("value").strip()
                if value:
                    MemoryStore.user.set_preferred_name(value)
                    logger.info("memory_name_saved", name=value)
                    return f"Noted, {value}. I'll remember your name."

        # Language save
        for pat in _REMEMBER_LANGUAGE_PATTERNS:
            m = pat.match(text)
            if m:
                value = m.group("value").strip()
                if value:
                    MemoryStore.user.set_language(value)
                    return f"Got it — I'll use {value} from now on."

        # Name query
        for pat in _QUERY_NAME_PATTERNS:
            if pat.match(text):
                name = MemoryStore.user.get_preferred_name()
                if name:
                    return f"Your name is {name}."
                return "I don't know your name yet. Tell me with 'remember my name is ...'"

        # Forget name
        for pat in _FORGET_NAME_PATTERNS:
            if pat.match(text):
                if MemoryStore.user.delete("preferred_name"):
                    return "Forgot your name."
                return "I didn't have your name stored."

        return None

    def _build_memory_context(self) -> str:
        """Return a short memory context string for the system prompt."""
        if not self._memory_enabled:
            return ""
        try:
            from app.memory.memory import MemoryStore
            prefs = MemoryStore.user.all()
            if not prefs:
                return ""
            lines = ["Known user preferences:"]
            for p in prefs[:10]:
                lines.append(f"- {p.key}: {p.value}")
            return "\n".join(lines)
        except Exception:  # noqa: BLE001
            return ""

    def _augmented_system_prompt(self) -> str:
        ctx = self._build_memory_context()
        if not ctx:
            return self._system_prompt
        return f"{self._system_prompt}\n\n{ctx}"

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    async def run(self, user_input: str, voice_turn: bool = False) -> str:
        self._voice_turn = bool(voice_turn)

        # 0. Memory commands (0 tokens)
        memory_response = self._try_memory_command(user_input)
        if memory_response is not None:
            self._memory_save_user(user_input)
            self._memory_save_assistant(memory_response)
            self.history.append({"role": "user", "content": user_input})
            self.history.append({"role": "assistant", "content": memory_response})
            self._trim_history()
            await self._speak(memory_response)
            return memory_response

        # 1. Local intent
        if self._local_intent_enabled:
            try:
                local = match_local(user_input)
            except Exception as exc:  # noqa: BLE001
                logger.warning("local_intent_failed", error=str(exc))
                local = None

            if local is not None and local.matched:
                logger.info("local_intent_matched", intent=local.intent)
                self.event_bus.publish(Event("LOCAL_INTENT", {"intent": local.intent}))

                if local.direct_response is not None:
                    text = local.direct_response
                    self._memory_save_user(user_input)
                    self._memory_save_assistant(text)
                    self.history.append({"role": "user", "content": user_input})
                    self.history.append({"role": "assistant", "content": text})
                    self._trim_history()
                    await self._speak(text)
                    return text

                result = await ToolRegistry.execute(local.tool_name, local.arguments)
                text = self._render_local_result(local.tool_name, result)
                self._memory_save_user(user_input)
                self._memory_save_tool(
                    local.tool_name, local.arguments, result.to_dict(),
                )
                self._memory_save_assistant(text)
                self.history.append({"role": "user", "content": user_input})
                self.history.append({"role": "assistant", "content": text})
                self._trim_history()
                await self._speak(text)
                return text

        # 2. Provider path (includes Phase 16 planner check)
        text = await self._run_provider(user_input)
        await self._speak(text)
        return text

    # ------------------------------------------------------------------ #
    # Phase 16 — Planner path detection
    # ------------------------------------------------------------------ #
    def _should_use_planner(self, user_input: str) -> bool:
        """Decide if a request is complex enough for the planner path."""
        if not bool(ConfigManager.get("agent.planner.enabled", True)):
            return False

        text = (user_input or "").strip()
        min_len = int(ConfigManager.get("agent.planner.min_length_for_planning", 60))
        if len(text) < min_len:
            return False

        raw_words = ConfigManager.get(
            "agent.planner.multi_action_words",
            ["and", "then", "after", "also", "তারপর", "এবং", "ও"],
        )
        words = [str(w).lower() for w in (raw_words or [])]
        low = text.lower()
        return any(w and w in low for w in words)

    # ------------------------------------------------------------------ #
    # Phase 16 — Planner path execution
    # ------------------------------------------------------------------ #
    async def _run_planner_path(self, user_input: str) -> str:
        """
        Complex request: plan -> execute -> verify.
        Raises RuntimeError("trivial_plan_skip") if the plan turns out
        to be a single step, so the caller can fall back to the direct
        path.
        """
        from app.agent.planner import Planner
        from app.agent.executor import Executor
        from app.agent.verifier import AgentVerifier
        from app.agent.recovery import Recovery

        app_state.task_state = TaskState.PLANNING

        planner = Planner(event_bus=self.event_bus)
        plan = await planner.create_plan(user_input)

        if plan.is_trivial:
            raise RuntimeError("trivial_plan_skip")

        self.event_bus.publish(Event("PLANNER_PATH_ENGAGED", {
            "goal": plan.goal,
            "steps": len(plan.steps),
        }))
        logger.info("planner_path_engaged", steps=len(plan.steps))

        app_state.task_state = TaskState.EXECUTING

        executor = Executor(event_bus=self.event_bus)
        recovery = Recovery(event_bus=self.event_bus)
        verifier = AgentVerifier(event_bus=self.event_bus)

        execution = await executor.execute(plan, recovery=recovery)

        app_state.task_state = TaskState.VERIFYING
        verification = await verifier.verify_plan(plan, execution)

        final = execution.final_message
        if not verification.verified:
            final += " (some steps could not be verified)"

        # Phase 16 fix: append the user message + assistant reply so the
        # history stays well-formed (a user turn with its assistant reply).
        self._memory_save_user(user_input)
        self._memory_save_assistant(final)
        self.history.append({"role": "user", "content": user_input})
        self.history.append({"role": "assistant", "content": final})
        self._trim_history()

        app_state.task_state = TaskState.IDLE
        return final

    # ------------------------------------------------------------------ #
    # Provider path (direct tool-calling — unchanged for simple requests)
    # ------------------------------------------------------------------ #
    async def _run_provider(self, user_input: str) -> str:
        # ---- Phase 16: try planner first for complex requests ---- #
        if self._should_use_planner(user_input):
            try:
                return await self._run_planner_path(user_input)
            except RuntimeError as exc:
                if "trivial_plan_skip" not in str(exc):
                    raise
                logger.info("planner_skipped_trivial_plan")
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "planner_path_failed_falling_back",
                    error=str(exc),
                )
        # ---- Direct path (original behavior) ---- #

        provider = self._get_provider()
        app_state.task_state = TaskState.THINKING
        self.history.append({"role": "user", "content": user_input})
        self._trim_history()
        self._memory_save_user(user_input)

        if self._dynamic_tools_enabled:
            try:
                tools_schema = select_tool_schemas(user_input) or None
            except Exception as exc:  # noqa: BLE001
                logger.warning("tool_selector_failed", error=str(exc))
                tools_schema = ToolRegistry.all_schemas() or None
        else:
            tools_schema = ToolRegistry.all_schemas() or None

        seen_tool_calls: Set[Tuple[str, str]] = set()

        for step in range(self._max_tool_steps):
            messages = [
                {"role": "system", "content": self._augmented_system_prompt()},
                *self._sanitize_history_for_provider(),
            ]
            try:
                # Phase 18: if using router, pass a RoutingContext
                if isinstance(provider, AIRouter):
                    ctx = RoutingContext(
                        text=user_input,
                        has_tools=bool(tools_schema),
                        message_count=len(messages),
                    )
                    response: AIResponse = await provider.generate(
                        messages=messages, tools=tools_schema, ctx=ctx,
                    )
                else:
                    response: AIResponse = await provider.generate(
                        messages=messages, tools=tools_schema,
                    )
            except Exception as exc:  # noqa: BLE001
                app_state.task_state = TaskState.FAILED
                logger.error("agent_generate_failed", error=str(exc))
                self._drop_dangling_tool_calls()
                raise

            if not response.has_tool_calls:
                text = response.text or "(no response)"
                self.history.append({"role": "assistant", "content": text})
                self._trim_history()
                self._memory_save_assistant(text)
                app_state.task_state = TaskState.IDLE
                return text

            filtered_calls: List[ToolCall] = []
            for tc in response.tool_calls:
                sig = _tool_call_signature(tc)
                if self._detect_duplicates and sig in seen_tool_calls:
                    logger.warning(
                        "duplicate_tool_call_skipped",
                        name=tc.name,
                        arguments=tc.arguments,
                    )
                    self.history.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.name,
                        "content": json.dumps({
                            "success": False,
                            "tool": tc.name,
                            "data": None,
                            "error": {
                                "code": "DUPLICATE_CALL",
                                "message": "Already called with same args.",
                            },
                            "duration_ms": 0,
                        }, ensure_ascii=False),
                    })
                    continue
                seen_tool_calls.add(sig)
                filtered_calls.append(tc)

            if not filtered_calls:
                logger.warning("all_tool_calls_were_duplicates", step=step)
                tools_schema = None
                continue

            self.history.append(
                self._assistant_message_with_tool_calls(response, filtered_calls)
            )

            for tool_call in filtered_calls:
                name = tool_call.name
                args = tool_call.arguments or {}

                # ---- Phase 20: security pipeline ---- #
                verdict = await self._security_check(name, args)
                if not verdict.get("allow", True):
                    reason = verdict.get("reason", "blocked by security")
                    blocked_result = ToolResult(
                        success=False,
                        tool=name,
                        error={
                            "code": "SECURITY_BLOCKED",
                            "message": reason,
                        },
                    )
                    self.event_bus.publish(Event("TOOL_BLOCKED", {
                        "name": name,
                        "arguments": args,
                        "reason": reason,
                    }))
                    self.history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": name,
                        "content": json.dumps(
                            blocked_result.to_dict(), ensure_ascii=False,
                        ),
                    })
                    continue

                # ---- Execute ---- #
                self.event_bus.publish(
                    Event("TOOL_STARTED", {"name": name, "arguments": args})
                )
                app_state.task_state = TaskState.EXECUTING
                result = await ToolRegistry.execute(name, args)
                self.event_bus.publish(
                    Event(
                        "TOOL_FINISHED" if result.success else "TOOL_FAILED",
                        {"name": name, "arguments": args, "result": result.to_dict()},
                    )
                )
                self._memory_save_tool(name, args, result.to_dict())
                self.history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": name,
                    "content": json.dumps(result.to_dict(), ensure_ascii=False),
                })

            if self._dynamic_tools_enabled:
                tools_schema = select_tool_schemas(user_input) or None

            self._trim_history()

        logger.warning("agent_max_tool_steps_reached", steps=self._max_tool_steps)
        app_state.task_state = TaskState.FAILED
        self._drop_dangling_tool_calls()
        return (
            "I reached the maximum number of tool steps for this request. "
            "Please try a simpler instruction."
        )

    # ------------------------------------------------------------------ #
    # History hygiene
    # ------------------------------------------------------------------ #
    def _sanitize_history_for_provider(self) -> List[Dict[str, Any]]:
        """
        Return a history that is safe to send to the AI provider.

        Rules enforced:
            - Every `tool` message must be preceded by an assistant
              message with matching `tool_calls`.
            - Any unresolved assistant `tool_calls` (whose tool
              response never arrived) are dropped.
            - Leading tool messages are dropped.
        """
        if not self.history:
            return []

        sanitized: List[Dict[str, Any]] = []
        pending_tool_ids: set = set()

        def _drop_trailing_assistant_with_tool_calls() -> None:
            for i in range(len(sanitized) - 1, -1, -1):
                m = sanitized[i]
                if m.get("role") == "assistant" and m.get("tool_calls"):
                    del sanitized[i:]
                    return

        for msg in self.history:
            role = msg.get("role")
            if role == "assistant":
                sanitized.append(msg)
                pending_tool_ids = set()
                for tc in msg.get("tool_calls") or []:
                    if isinstance(tc, dict) and "id" in tc:
                        pending_tool_ids.add(tc["id"])
            elif role == "tool":
                tc_id = msg.get("tool_call_id")
                if tc_id in pending_tool_ids:
                    sanitized.append(msg)
                    pending_tool_ids.discard(tc_id)
                # else: drop orphan tool message
            elif role == "user":
                # If previous assistant tool_calls never resolved, drop
                # that assistant message (and any trailing tool messages
                # already added) so the user turn starts clean.
                if pending_tool_ids:
                    _drop_trailing_assistant_with_tool_calls()
                    pending_tool_ids.clear()
                sanitized.append(msg)
            else:
                sanitized.append(msg)

        # If the last assistant turn has unresolved tool_calls, drop it.
        if pending_tool_ids:
            _drop_trailing_assistant_with_tool_calls()

        return sanitized

    def _drop_dangling_tool_calls(self) -> None:
        if not self.history:
            return
        for i in range(len(self.history) - 1, -1, -1):
            msg = self.history[i]
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                expected_ids = {tc["id"] for tc in msg["tool_calls"]}
                seen_ids = set()
                for j in range(i + 1, len(self.history)):
                    m = self.history[j]
                    if m.get("role") == "tool":
                        seen_ids.add(m.get("tool_call_id"))
                if expected_ids - seen_ids:
                    self.history = self.history[:i]
                return

    # ------------------------------------------------------------------ #
    # Rendering
    # ------------------------------------------------------------------ #
    def _render_local_result(self, tool_name: str, result) -> str:
        if not result.success:
            err = (result.error or {}).get("message", "unknown error")
            return f"Sorry, that didn't work: {err}"
        data = result.data or {}

        if tool_name == "open_application":
            return f"Opened {data.get('application', 'the app')}."
        if tool_name == "open_url":
            title = data.get("title") or data.get("url")
            return f"Opened {title}."
        if tool_name == "volume_up":
            return f"Volume is now at {data.get('new_level_percent', '?')}%."
        if tool_name == "volume_down":
            return f"Volume is now at {data.get('new_level_percent', '?')}%."
        if tool_name == "mute":
            return "Muted." if data.get("muted") else "Unmuted."
        if tool_name == "take_screenshot":
            return f"Screenshot saved: {data.get('path', '?')}"
        if tool_name == "media_control":
            return f"Media {data.get('action', 'control')} sent."
        if tool_name == "minimize_window":
            return "Window minimized."
        if tool_name == "maximize_window":
            return "Window maximized."
        if tool_name == "focus_window":
            return f"Focused '{data.get('title', 'window')}'."
        if tool_name == "get_active_window":
            return f"Active window: {data.get('title', 'unknown')}."
        if tool_name == "list_windows":
            return f"There are {data.get('count', 0)} visible windows."
        if tool_name == "get_clipboard_text":
            text = data.get("text", "")
            return f"Clipboard: {text}" if text else "Clipboard is empty."
        return "Done."
        # ------------------------------------------------------------------ #
    # Phase 20 — Security pipeline
    # ------------------------------------------------------------------ #
    async def _security_check(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Run the full security pipeline before executing a tool.

        Pipeline:
            1. Sandbox    (HIGH/CRITICAL blocked if sandbox active)
            2. Permissions (allow / confirm / deny)
            3. Rate limiter
            4. Network whitelist (for network-touching tools)
            5. Confirmation gate (if required)
            6. Audit log

        Returns:
            {"allow": bool, "reason": str}
        """
        try:
            from app.security import (
                PermissionManager,
                ConfirmationGate,
                RateLimiter,
                NetworkWhitelist,
                Sandbox,
                AuditLog,
            )
            from app.tools.registry import ToolRegistry
        except Exception as exc:  # noqa: BLE001
            logger.warning("security_import_failed", error=str(exc))
            return {"allow": True, "reason": "security not available"}

        # Determine risk from tool
        tool = ToolRegistry.get(tool_name)
        risk = "LOW"
        if tool is not None:
            risk_obj = getattr(tool, "risk_level", None)
            if risk_obj is not None:
                risk = getattr(risk_obj, "value", str(risk_obj))

        # 1. Sandbox
        if not Sandbox.allow_tool(tool_name, risk):
            AuditLog.log(
                "SANDBOX_BLOCKED", tool=tool_name, risk=risk,
                data={"arguments": arguments},
            )
            return {
                "allow": False,
                "reason": (
                    f"Sandbox mode is active — '{tool_name}' "
                    f"(risk {risk}) is not allowed. Exit sandbox to continue."
                ),
            }

        # 2. Permissions
        try:
            decision = PermissionManager.check(tool_name, risk=risk)
        except Exception as exc:  # noqa: BLE001
            logger.warning("permission_check_failed", error=str(exc))
            decision = None

        if decision is not None and not decision.allow:
            if not decision.requires_confirmation:
                AuditLog.log(
                    "PERMISSION_DENIED", tool=tool_name, risk=risk,
                    data={"reason": decision.reason},
                )
                return {"allow": False, "reason": decision.reason}

            # 3. Confirmation required
            approved = await ConfirmationGate.request(
                tool_name=tool_name,
                arguments=arguments,
                risk=risk,
                reason=decision.reason,
            )
            AuditLog.log(
                "CONFIRMATION_RESULT",
                tool=tool_name, risk=risk,
                data={"approved": approved, "reason": decision.reason},
            )
            if not approved:
                return {
                    "allow": False,
                    "reason": "User denied confirmation.",
                }

        # 4. Rate limit
        if not RateLimiter.allow(tool_name):
            AuditLog.log(
                "RATE_LIMITED", tool=tool_name, risk=risk,
                data={"arguments": arguments},
            )
            return {
                "allow": False,
                "reason": f"Rate limit exceeded for '{tool_name}'.",
            }

        # 5. Network whitelist (for network-touching tools)
        if tool_name in {"open_url", "search_web", "download_file"}:
            url = arguments.get("url") or arguments.get("query") or ""
            if url:
                wl = NetworkWhitelist.check(str(url))
                if not wl.allow:
                    AuditLog.log(
                        "NETWORK_BLOCKED", tool=tool_name, risk=risk,
                        data={"url": url, "reason": wl.reason},
                    )
                    return {"allow": False, "reason": wl.reason}

        # 6. Audit — log approval
        AuditLog.log(
            "TOOL_APPROVED",
            tool=tool_name, risk=risk,
            data={"arguments": arguments},
        )
        return {"allow": True, "reason": "approved"}


    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_provider(self):
        if self._provider is None:
            # Phase 18: use AI router (respects routing rules + fallback)
            try:
                # Detect monkey-patched stub (used by tests).
                # If ProviderRegistry.get_active_provider() returns a
                # class that isn't a registered provider, treat it as a
                # test stub and bypass the router.
                active = ProviderRegistry.get_active_provider()
                active_type = type(active).__name__
                registered_types = {
                    cls.__name__
                    for cls in ProviderRegistry._providers.values()
                }
                if active_type not in registered_types:
                    logger.info(
                        "test_stub_detected_router_bypassed",
                        stub=active_type,
                    )
                    self._router = None
                    self._provider = active
                    app_state.active_provider = active_type
                    app_state.active_model = getattr(active, "model", "")
                    return self._provider

                # Normal path: use AI router
                self._router = AIRouter.from_config()
                self._provider = self._router
                app_state.active_provider = "router"
                app_state.active_model = "auto"
                logger.info("router_loaded", mode=self._router.mode)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "router_init_failed_fallback_to_registry",
                    error=str(exc),
                )
                self._router = None
                self._provider = ProviderRegistry.get_active_provider()
                app_state.active_provider = type(self._provider).__name__
                app_state.active_model = getattr(self._provider, "model", "")
                logger.info(
                    "provider_loaded",
                    provider=app_state.active_provider,
                    model=app_state.active_model,
                )
        return self._provider
    def _trim_history(self) -> None:
        max_msgs = max(2, self._history_limit)
        if len(self.history) <= max_msgs:
            return
        target_start = len(self.history) - max_msgs
        while target_start < len(self.history):
            if self.history[target_start].get("role") != "tool":
                break
            target_start += 1
        if target_start < len(self.history):
            msg = self.history[target_start]
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                target_start += 1
                while target_start < len(self.history):
                    if self.history[target_start].get("role") != "tool":
                        break
                    target_start += 1
        if target_start >= len(self.history):
            return
        self.history = self.history[target_start:]

    @staticmethod
    def _assistant_message_with_tool_calls(
        response: AIResponse,
        tool_calls: Optional[List[ToolCall]] = None,
    ) -> Dict[str, Any]:
        calls = tool_calls if tool_calls is not None else response.tool_calls
        payload = []
        for tc in calls:
            payload.append({
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                },
            })
        return {
            "role": "assistant",
            "content": response.text or "",
            "tool_calls": payload,
        }
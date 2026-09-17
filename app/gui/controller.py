"""
GUI Controller (Phase 21).

Bridges the EVA core (AgentLoop + EventBus + voice) to the GUI.
No Qt imports — so it can be unit-tested headlessly.

The GUI calls:
    await controller.send_message("hello")
    await controller.cancel_current_task()
    await controller.toggle_listening()

The controller emits callbacks (registered by the GUI):
    on_user_message(text)
    on_assistant_message(text)
    on_tool_event(dict)
    on_status_changed(old, new)
    on_error(message)
"""
from __future__ import annotations

import asyncio
import threading
from typing import Any, Callable, Dict, List, Optional

from app.agent.agent import AgentLoop
from app.core.events import Event, EventBus
from app.core.logger import get_logger
from app.gui.gui_state import GUIState, GUIStatus

logger = get_logger(__name__)


UserMessageCB = Callable[[str], None]
AssistantMessageCB = Callable[[str], None]
ToolEventCB = Callable[[Dict[str, Any]], None]
ErrorCB = Callable[[str], None]


class GUIController:
    """Bridge between GUI widgets and AgentLoop."""

    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        gui_state: Optional[GUIState] = None,
        agent: Optional[AgentLoop] = None,
    ) -> None:
        self.event_bus = event_bus or EventBus()
        self.state = gui_state or GUIState()
        self._agent: Optional[AgentLoop] = agent
        self._lock = threading.RLock()
        self._cancelled = False

        # Callbacks (GUI registers these)
        self._on_user_message: List[UserMessageCB] = []
        self._on_assistant_message: List[AssistantMessageCB] = []
        self._on_tool_event: List[ToolEventCB] = []
        self._on_error: List[ErrorCB] = []

        self._wire_events()

    # ------------------------------------------------------------------ #
    # Agent access
    # ------------------------------------------------------------------ #
    def set_agent(self, agent: AgentLoop) -> None:
        with self._lock:
            self._agent = agent

    def _ensure_agent(self) -> AgentLoop:
        with self._lock:
            if self._agent is None:
                self._agent = AgentLoop(event_bus=self.event_bus)
            return self._agent

    # ------------------------------------------------------------------ #
    # Callback registration
    # ------------------------------------------------------------------ #
    def on_user_message(self, cb: UserMessageCB) -> None:
        self._on_user_message.append(cb)

    def on_assistant_message(self, cb: AssistantMessageCB) -> None:
        self._on_assistant_message.append(cb)

    def on_tool_event(self, cb: ToolEventCB) -> None:
        self._on_tool_event.append(cb)

    def on_error(self, cb: ErrorCB) -> None:
        self._on_error.append(cb)

    # ------------------------------------------------------------------ #
    # Core commands
    # ------------------------------------------------------------------ #
    async def send_message(self, text: str) -> str:
        """Send a user message to the agent and return the reply."""
        text = (text or "").strip()
        if not text:
            return ""

        self._cancelled = False
        self.state.set_task(text[:120])
        self.state.set(GUIStatus.THINKING)
        self._emit_user(text)

        try:
            agent = self._ensure_agent()
            reply = await agent.run(text)
        except Exception as exc:  # noqa: BLE001
            logger.error("controller_send_failed", error=str(exc))
            self.state.set_error(str(exc))
            self._emit_error(str(exc))
            self.state.clear_task()
            return ""

        if self._cancelled:
            self.state.clear_task()
            self.state.set(GUIStatus.IDLE)
            return reply or ""

        self._emit_assistant(reply)
        self.state.clear_task()
        self.state.set(GUIStatus.IDLE)
        return reply

    async def cancel_current_task(self) -> None:
        """Best-effort cancellation of the current task."""
        self._cancelled = True
        self.state.clear_task()
        self.state.set(GUIStatus.IDLE)
        try:
            from app.voice.tts import SpeakController
            SpeakController().stop()  # noqa: B018
        except Exception:  # noqa: BLE001
            pass
        logger.info("controller_task_cancelled")

    async def toggle_listening(self) -> bool:
        """
        Placeholder for the future call button.

        Returns True if listening was started, False if stopped.
        """
        if self.state.status == GUIStatus.LISTENING:
            self.state.set(GUIStatus.IDLE)
            return False
        self.state.set(GUIStatus.LISTENING)
        return True

    def is_cancelled(self) -> bool:
        return self._cancelled

    # ------------------------------------------------------------------ #
    # Event bus wiring
    # ------------------------------------------------------------------ #
    def _wire_events(self) -> None:
        self.event_bus.subscribe(self._on_event)

    def _on_event(self, event: Event) -> None:
        etype = event.type
        if etype == "TOOL_STARTED":
            self.state.set(GUIStatus.THINKING)
            self._emit_tool({"event": "started", **(event.data or {})})
        elif etype == "TOOL_FINISHED":
            self._emit_tool({"event": "finished", **(event.data or {})})
        elif etype == "TOOL_FAILED":
            self._emit_tool({"event": "failed", **(event.data or {})})
        elif etype == "TOOL_BLOCKED":
            self._emit_tool({"event": "blocked", **(event.data or {})})
        elif etype == "ERROR":
            msg = str((event.data or {}).get("message", "error"))
            self.state.set_error(msg)
            self._emit_error(msg)
        elif etype == "SPEAKING_STARTED":
            self.state.set(GUIStatus.SPEAKING)
        elif etype == "SPEAKING_FINISHED":
            if self.state.status == GUIStatus.SPEAKING:
                self.state.set(GUIStatus.IDLE)

    # ------------------------------------------------------------------ #
    # Emit helpers
    # ------------------------------------------------------------------ #
    def _emit_user(self, text: str) -> None:
        for cb in list(self._on_user_message):
            try:
                cb(text)
            except Exception:  # noqa: BLE001
                pass

    def _emit_assistant(self, text: str) -> None:
        for cb in list(self._on_assistant_message):
            try:
                cb(text)
            except Exception:  # noqa: BLE001
                pass

    def _emit_tool(self, payload: Dict[str, Any]) -> None:
        for cb in list(self._on_tool_event):
            try:
                cb(payload)
            except Exception:  # noqa: BLE001
                pass

    def _emit_error(self, message: str) -> None:
        for cb in list(self._on_error):
            try:
                cb(message)
            except Exception:  # noqa: BLE001
                pass
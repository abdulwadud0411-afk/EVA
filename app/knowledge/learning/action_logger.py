"""
Action logger (Phase 15).

Captures user mouse / keyboard events into a normalised action log.
Used by the DemonstrationLearner to build a workflow from a live demo.

Events captured:
    - mouse clicks (button, x, y)
    - keyboard hotkeys / printable keys (as text)
    - window switches (active window title changes)

Every event is debounced and capped.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ActionEvent:
    timestamp: str
    kind: str                     # "click" | "key" | "hotkey" | "window"
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"timestamp": self.timestamp, "kind": self.kind, "data": self.data}


class ActionLogger:
    """Global input hook that records user actions while running."""

    def __init__(self) -> None:
        self.events: List[ActionEvent] = []
        self._running = False
        self._lock = threading.Lock()
        self._debounce = float(ConfigManager.get("learning.demonstration.event_debounce_seconds", 0.5))
        self._max_events = int(ConfigManager.get("learning.demonstration.max_events", 500))
        self._last_at: float = 0.0
        self._last_window: str = ""

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def start(self) -> bool:
        if self._running:
            return True
        try:
            import keyboard  # type: ignore
            import mouse  # type: ignore
        except Exception as exc:  # noqa: BLE001
            logger.error("input_hooks_not_available", error=str(exc))
            return False

        self.events = []
        self._last_window = ""
        self._running = True

        try:
            mouse.on_click(self._on_click)
            keyboard.on_press(self._on_key_press)
        except Exception as exc:  # noqa: BLE001
            logger.error("input_hook_register_failed", error=str(exc))
            self._running = False
            return False

        self._start_window_watcher()
        logger.info("action_logger_started")
        return True

    def stop(self) -> List[ActionEvent]:
        if not self._running:
            return list(self.events)
        try:
            import keyboard  # type: ignore
            import mouse  # type: ignore
            mouse.unhook_all()
            keyboard.unhook_all()
        except Exception:  # noqa: BLE001
            pass
        self._running = False
        logger.info("action_logger_stopped", count=len(self.events))
        return list(self.events)

    # ------------------------------------------------------------------ #
    # Event handlers (called from hook threads)
    # ------------------------------------------------------------------ #
    def _on_click(self, event=None) -> None:
        if not self._running or event is None:
            return
        now = time.time()
        if now - self._last_at < self._debounce:
            return
        self._last_at = now

        try:
            x, y = int(event.x), int(event.y)
            button = getattr(event, "button", "left")
        except Exception:  # noqa: BLE001
            return

        self._append("click", {"x": x, "y": y, "button": button})

    def _on_key_press(self, event=None) -> None:
        if not self._running or event is None:
            return
        # Debounce printable keys quickly; do not debounce hotkeys.
        try:
            name = getattr(event, "name", "")
            is_keypad = getattr(event, "is_keypad", False)
            if is_keypad:
                return
        except Exception:  # noqa: BLE001
            return

        if not name:
            return

        # Treat single-character names as text (accumulated).
        if len(name) == 1:
            self._append("key", {"char": name})
        else:
            now = time.time()
            if now - self._last_at < self._debounce:
                return
            self._last_at = now
            self._append("hotkey", {"name": name})

    def _append(self, kind: str, data: Dict[str, Any]) -> None:
        with self._lock:
            if len(self.events) >= self._max_events:
                return
            self.events.append(ActionEvent(
                timestamp=datetime.now().isoformat(),
                kind=kind,
                data=data,
            ))

    # ------------------------------------------------------------------ #
    # Window watcher
    # ------------------------------------------------------------------ #
    def _start_window_watcher(self) -> None:
        def _loop() -> None:
            try:
                import win32gui  # type: ignore
            except Exception:  # noqa: BLE001
                return
            while self._running:
                try:
                    hwnd = win32gui.GetForegroundWindow()
                    title = win32gui.GetWindowText(hwnd) or ""
                except Exception:  # noqa: BLE001
                    title = ""
                if title and title != self._last_window:
                    self._last_window = title
                    self._append("window", {"title": title})
                time.sleep(0.5)

        threading.Thread(target=_loop, name="eva-window-watcher", daemon=True).start()

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def count(self) -> int:
        return len(self.events)

    def as_dicts(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self.events]
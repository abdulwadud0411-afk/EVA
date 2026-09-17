"""
GUI state machine (Phase 21).

Pure-Python state model — no Qt imports. Safe to unit-test without
PySide6 installed.

Tracks the high-level UI state:
    IDLE | LISTENING | THINKING | SPEAKING | ERROR

Notifies registered listeners synchronously when the state changes.

Public API:
    from app.gui.gui_state import GUIState, GUIStatus
    gs = GUIState()
    gs.subscribe(lambda old, new: print(old, "->", new))
    gs.set(GUIStatus.LISTENING)
"""
from __future__ import annotations

import threading
from enum import Enum
from typing import Callable, List, Optional, Tuple


class GUIStatus(str, Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    ERROR = "ERROR"


Transition = Tuple[GUIStatus, GUIStatus]
Listener = Callable[[GUIStatus, GUIStatus], None]


class GUIState:
    """Thread-safe state holder with change notifications."""

    def __init__(self, initial: GUIStatus = GUIStatus.IDLE) -> None:
        self._status: GUIStatus = initial
        self._listeners: List[Listener] = []
        self._lock = threading.RLock()
        self._current_task: str = ""
        self._last_error: str = ""

    # ------------------------------------------------------------------ #
    # Subscription
    # ------------------------------------------------------------------ #
    def subscribe(self, listener: Listener) -> None:
        with self._lock:
            if listener not in self._listeners:
                self._listeners.append(listener)

    def unsubscribe(self, listener: Listener) -> None:
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)

    # ------------------------------------------------------------------ #
    # Accessors
    # ------------------------------------------------------------------ #
    @property
    def status(self) -> GUIStatus:
        return self._status

    @property
    def current_task(self) -> str:
        return self._current_task

    @property
    def last_error(self) -> str:
        return self._last_error

    def is_busy(self) -> bool:
        return self._status in (
            GUIStatus.LISTENING, GUIStatus.THINKING, GUIStatus.SPEAKING,
        )

    # ------------------------------------------------------------------ #
    # Mutations
    # ------------------------------------------------------------------ #
    def set(self, new_status: GUIStatus) -> None:
        if not isinstance(new_status, GUIStatus):
            try:
                new_status = GUIStatus(str(new_status))
            except ValueError:
                return

        old: GUIStatus
        with self._lock:
            if self._status == new_status:
                return
            old = self._status
            self._status = new_status
            if new_status != GUIStatus.ERROR:
                self._last_error = ""
            listeners = list(self._listeners)

        for fn in listeners:
            try:
                fn(old, new_status)
            except Exception:  # noqa: BLE001
                pass

    def set_task(self, description: str) -> None:
        with self._lock:
            self._current_task = (description or "").strip()

    def clear_task(self) -> None:
        with self._lock:
            self._current_task = ""

    def set_error(self, message: str) -> None:
        with self._lock:
            self._last_error = (message or "").strip()
        self.set(GUIStatus.ERROR)

    def reset(self) -> None:
        with self._lock:
            self._current_task = ""
            self._last_error = ""
        self.set(GUIStatus.IDLE)
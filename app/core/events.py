"""
Lightweight in-process publish/subscribe event bus.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional


# Event type constants (Phase 1 + reserved names for future phases)
THINKING_STARTED = "THINKING_STARTED"
RESPONSE_READY = "RESPONSE_READY"
ERROR = "ERROR"

# Reserved (declared here as documentation only; no logic in Phase 1):
# WAKE_WORD_DETECTED, LISTENING_STARTED, LISTENING_STOPPED,
# TRANSCRIPTION_READY, TOOL_REQUESTED, TOOL_STARTED, TOOL_FINISHED,
# TOOL_FAILED, CONFIRMATION_REQUIRED, SPEAKING_STARTED,
# SPEAKING_FINISHED, DEVICE_CONNECTED, DEVICE_DISCONNECTED,
# REMOTE_COMMAND_RECEIVED, KNOWLEDGE_EXTRACTED, STORAGE_CLEANUP


@dataclass
class Event:
    type: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class EventBus:
    """Simple synchronous pub/sub bus."""

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Callable[[Event], None]]] = {}

    def subscribe(
        self,
        callback: Callable[[Event], None],
        event_type: Optional[str] = None,
    ) -> None:
        key = event_type or "__all__"
        self._subscribers.setdefault(key, []).append(callback)

    def unsubscribe(
        self,
        callback: Callable[[Event], None],
        event_type: Optional[str] = None,
    ) -> None:
        key = event_type or "__all__"
        if key in self._subscribers and callback in self._subscribers[key]:
            self._subscribers[key].remove(callback)

    def publish(self, event: Event) -> None:
        for cb in list(self._subscribers.get(event.type, [])):
            try:
                cb(event)
            except Exception:  # noqa: BLE001 - never break publishing
                pass
        for cb in list(self._subscribers.get("__all__", [])):
            try:
                cb(event)
            except Exception:  # noqa: BLE001
                pass
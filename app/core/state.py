"""
Global application state (Phase 1 minimum).
Includes `device_id` placeholder for the future multi-device architecture.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TaskState(str, Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    WAITING = "WAITING"
    VERIFYING = "VERIFYING"
    RECOVERING = "RECOVERING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class AppState:
    """Process-wide mutable state."""
    task_state: TaskState = TaskState.IDLE
    device_id: str = "local"       # reserved for multi-device phase
    active_provider: str = ""      # set after registry resolves
    active_model: str = ""         # informational


# Singleton instance
app_state = AppState()
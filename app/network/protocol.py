"""
Wire-protocol primitives - Phase 1 stub.

Only enums and a dataclass are defined here so future phases can import
the shared vocabulary without redefining it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class MessageType(str, Enum):
    AUTH_REQUEST = "AUTH_REQUEST"
    AUTH_RESPONSE = "AUTH_RESPONSE"
    PAIRING_REQUEST = "PAIRING_REQUEST"
    CAPABILITY_REPORT = "CAPABILITY_REPORT"
    COMMAND = "COMMAND"
    COMMAND_RESULT = "COMMAND_RESULT"
    EVENT = "EVENT"
    STATUS_REQUEST = "STATUS_REQUEST"
    STATUS_RESPONSE = "STATUS_RESPONSE"
    SYNC_REQUEST = "SYNC_REQUEST"
    SYNC_RESPONSE = "SYNC_RESPONSE"
    PING = "PING"
    PONG = "PONG"


@dataclass
class Envelope:
    """Canonical envelope for every EVA network message."""
    version: str = "1.0"
    id: str = ""
    type: MessageType = MessageType.PING
    source_device: str = ""
    target_device: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    payload: Dict[str, Any] = field(default_factory=dict)
    auth: Optional[str] = None
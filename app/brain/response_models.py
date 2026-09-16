"""Normalized response structures shared across providers."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AIResponse:
    text: Optional[str] = None
    tool_calls: List[ToolCall] = field(default_factory=list)
    reasoning: Optional[str] = None
    finish_reason: str = "stop"
    provider_name: str = "unknown"
    model_used: str = "unknown"
    usage: Dict[str, int] = field(default_factory=dict)
    raw: Optional[Any] = None

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)
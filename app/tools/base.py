"""
Tool system base classes (Phase 2).

Every tool must subclass `Tool` and implement `run()`.
Tool results are always returned as a `ToolResult`.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class RiskLevel(str, Enum):
    """How dangerous a tool is to execute."""
    LOW = "LOW"           # Safe, no confirmation needed
    MEDIUM = "MEDIUM"     # Ask before executing
    HIGH = "HIGH"         # Always ask, show exact action
    CRITICAL = "CRITICAL" # Always ask, require explicit "yes"


@dataclass
class ToolResult:
    """Standard result returned by every tool."""
    success: bool
    tool: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, str]] = None
    duration_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "tool": self.tool,
            "data": self.data,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


class Tool(ABC):
    """Abstract base class for every EVA tool."""

    # Subclasses override these
    name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = {}
    risk_level: RiskLevel = RiskLevel.LOW
    requires_confirmation: bool = False

    @abstractmethod
    async def run(self, **kwargs: Any) -> ToolResult:
        """Execute the tool. Must return a ToolResult."""
        raise NotImplementedError

    def schema(self) -> Dict[str, Any]:
        """Return the OpenAI/DeepSeek tool-calling schema for this tool."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def __repr__(self) -> str:
        return f"<Tool {self.name} risk={self.risk_level.value}>"
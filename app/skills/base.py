"""
Skill primitives (Phase 15).

A Skill is a list of SkillStep objects. Each step maps to a registered
Tool call. The SkillExecutor runs steps sequentially via ToolRegistry.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


class SkillExecutionError(Exception):
    """Raised when a skill step fails unrecoverably."""


class SkillDefinitionError(Exception):
    """Raised when a skill definition is invalid."""


# ---------------------------------------------------------------------- #
# Step
# ---------------------------------------------------------------------- #
@dataclass
class SkillStep:
    index: int
    action: str
    tool_name: str = ""
    arguments: Dict[str, Any] = field(default_factory=dict)
    verification: Optional[str] = None
    timeout_seconds: int = 60
    optional: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkillStep":
        return cls(
            index=int(data.get("index", 0)),
            action=str(data.get("action", "")),
            tool_name=str(data.get("tool_name") or data.get("tool_hint") or ""),
            arguments=dict(data.get("arguments") or {}),
            verification=data.get("verification"),
            timeout_seconds=int(data.get("timeout_seconds", 60)),
            optional=bool(data.get("optional", False)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "action": self.action,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "verification": self.verification,
            "timeout_seconds": self.timeout_seconds,
            "optional": self.optional,
        }


# ---------------------------------------------------------------------- #
# Skill
# ---------------------------------------------------------------------- #
@dataclass
class Skill:
    name: str
    description: str = ""
    version: str = "1.0.0"
    steps: List[SkillStep] = field(default_factory=list)
    required_tools: List[str] = field(default_factory=list)
    source: str = "manual"       # manual | demo | video | user
    tags: List[str] = field(default_factory=list)
    verification: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Skill":
        steps_raw = data.get("steps", []) or []
        steps = [SkillStep.from_dict(s) for s in steps_raw]
        return cls(
            name=str(data.get("name", "")).strip(),
            description=str(data.get("description", "")),
            version=str(data.get("version", "1.0.0")),
            steps=steps,
            required_tools=list(data.get("required_tools") or []),
            source=str(data.get("source", "manual")),
            tags=list(data.get("tags") or []),
            verification=data.get("verification"),
            created_at=data.get("created_at") or datetime.now().isoformat(),
            updated_at=data.get("updated_at") or datetime.now().isoformat(),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "steps": [s.to_dict() for s in self.steps],
            "required_tools": list(self.required_tools),
            "source": self.source,
            "tags": list(self.tags),
            "verification": self.verification,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def validate(self) -> None:
        if not self.name:
            raise SkillDefinitionError("Skill name is required")
        if not self.steps:
            raise SkillDefinitionError("Skill must have at least one step")
        for i, s in enumerate(self.steps):
            if not s.action:
                raise SkillDefinitionError(f"Step {i + 1} has empty action")
            if not s.tool_name and not s.optional:
                # steps without a tool are allowed if they're purely informational,
                # but we flag them so the executor knows to skip.
                pass


# ---------------------------------------------------------------------- #
# Result
# ---------------------------------------------------------------------- #
@dataclass
class SkillResult:
    success: bool
    skill_name: str
    steps_total: int
    steps_completed: int
    results: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[Dict[str, str]] = None
    duration_ms: int = 0
    cancelled: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "skill_name": self.skill_name,
            "steps_total": self.steps_total,
            "steps_completed": self.steps_completed,
            "results": self.results,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "cancelled": self.cancelled,
        }
"""
Data models for EVA memory (Phase 12 + 15).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class Message:
    id: Optional[int] = None
    conversation_id: str = ""
    role: str = ""
    content: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    tool_name: Optional[str] = None
    tool_arguments: Optional[Dict[str, Any]] = None
    tool_result: Optional[Dict[str, Any]] = None


@dataclass
class Preference:
    key: str
    value: str
    category: str = "general"
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class KnowledgeEntry:
    id: Optional[int] = None
    title: str = ""
    content: str = ""
    source_type: str = "manual"
    source_path: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    embedding: Optional[bytes] = None
    confidence: float = 1.0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class SkillStep:
    """One step inside a skill."""
    index: int = 0
    action: str = ""
    tool_name: str = ""
    arguments: Dict[str, Any] = field(default_factory=dict)
    verification: Optional[str] = None
    timeout_seconds: int = 60
    optional: bool = False


@dataclass
class Skill:
    id: Optional[int] = None
    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    steps: List[Dict[str, Any]] = field(default_factory=list)
    required_tools: List[str] = field(default_factory=list)
    verification: Optional[str] = None
    source: str = "manual"
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class TaskRecord:
    id: Optional[int] = None
    description: str = ""
    status: str = "pending"
    result: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None


@dataclass
class Fact:
    id: Optional[int] = None
    category: str = "general"
    key: str = ""
    value: str = ""
    source: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
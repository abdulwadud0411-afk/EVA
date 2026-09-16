"""
Unified MemoryStore facade (Phase 12).
"""
from __future__ import annotations

from typing import Optional

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger
from app.memory.database import Database
from app.memory.conversation_memory import ConversationMemory
from app.memory.user_memory import UserMemory
from app.memory.knowledge_memory import KnowledgeMemory
from app.memory.skill_memory import SkillMemory
from app.memory.task_history import TaskHistory
from app.memory.vector_store import VectorStore, NullVectorStore

logger = get_logger(__name__)


class MemoryError(Exception):
    """Raised when memory operations fail."""


class MemoryStore:
    """Facade over all memory layers."""

    _initialized = False
    _conversation: Optional[ConversationMemory] = None
    _vector_store: VectorStore = NullVectorStore()

    user = UserMemory()
    knowledge = KnowledgeMemory()
    skills = SkillMemory()
    tasks = TaskHistory()

    @classmethod
    def init(cls) -> None:
        if cls._initialized:
            return
        if not ConfigManager.get("memory.enabled", True):
            logger.info("memory_disabled")
            return
        Database.init()
        cls._initialized = True
        logger.info("memory_store_initialized")

    @classmethod
    def reset(cls) -> None:
        cls._initialized = False
        cls._conversation = None

    @classmethod
    def conversation(cls, conversation_id: Optional[str] = None) -> ConversationMemory:
        if not cls._initialized:
            cls.init()
        if conversation_id is not None:
            return ConversationMemory(conversation_id)
        if cls._conversation is None:
            cls._conversation = ConversationMemory()
        return cls._conversation

    @classmethod
    def new_conversation(cls) -> ConversationMemory:
        cls._conversation = ConversationMemory()
        return cls._conversation

    @classmethod
    def set_vector_store(cls, store: VectorStore) -> None:
        cls._vector_store = store

    @classmethod
    def vector(cls) -> VectorStore:
        return cls._vector_store
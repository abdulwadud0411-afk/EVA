"""
EVA Persistent Memory (Phase 12).

Modular memory system stored in SQLite. Five independent layers:

    - ConversationMemory  : recent chat history
    - UserMemory          : long-term preferences
    - KnowledgeMemory     : learned facts
    - SkillMemory         : learned procedures
    - TaskHistory         : record of past tasks

Plus a unified facade:

    from app.memory.memory import MemoryStore
    MemoryStore.init()

Everything is 100% local. No cloud, no telemetry.
"""
from app.memory.memory import MemoryStore, MemoryError  # noqa: F401
from app.memory.database import Database  # noqa: F401
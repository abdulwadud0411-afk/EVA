"""Settings tabs package (Phase 21 Batch 3)."""
from app.gui.dialogs.tabs.ai_tab import AITab  # noqa: F401
from app.gui.dialogs.tabs.voice_tab import VoiceTab  # noqa: F401
from app.gui.dialogs.tabs.memory_tab import MemoryTab  # noqa: F401
from app.gui.dialogs.tabs.knowledge_tab import KnowledgeTab  # noqa: F401
from app.gui.dialogs.tabs.skills_tab import SkillsTab  # noqa: F401
from app.gui.dialogs.tabs.storage_tab import StorageTab  # noqa: F401
from app.gui.dialogs.tabs.security_tab import SecurityTab  # noqa: F401

__all__ = [
    "AITab", "VoiceTab", "MemoryTab", "KnowledgeTab",
    "SkillsTab", "StorageTab", "SecurityTab",
]
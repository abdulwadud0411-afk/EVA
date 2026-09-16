"""
Skill registry (Phase 15).

Loads skills from SQLite (MemoryStore.skills) and exposes a stable
API for list/get/save/delete. Also registers any skills found in
`app/skills/builtins/` (future).
"""
from __future__ import annotations

from typing import Dict, List, Optional

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger
from app.skills.base import Skill, SkillDefinitionError

logger = get_logger(__name__)


class SkillRegistry:
    """Stateless wrapper around MemoryStore.skills + a local cache."""

    _cache: Dict[str, Skill] = {}

    # ------------------------------------------------------------------ #
    # Query
    # ------------------------------------------------------------------ #
    @classmethod
    def list_skills(cls) -> List[str]:
        try:
            from app.memory.memory import MemoryStore
            return [s.name for s in MemoryStore.skills.list(limit=1000)]
        except Exception as exc:  # noqa: BLE001
            logger.warning("skill_registry_list_failed", error=str(exc))
            return []

    @classmethod
    def get_skill(cls, name: str) -> Optional[Skill]:
        if not name:
            return None
        if name in cls._cache:
            return cls._cache[name]

        try:
            from app.memory.memory import MemoryStore
            stored = MemoryStore.skills.get(name)
            if stored is None:
                return None
            # stored.steps is already a list of dicts (from Phase 12)
            skill = Skill.from_dict({
                "name": stored.name,
                "description": stored.description,
                "version": stored.version,
                "steps": stored.steps,
                "required_tools": stored.required_tools,
                "source": getattr(stored, "source", "manual"),
                "tags": getattr(stored, "tags", []),
                "verification": stored.verification,
                "created_at": stored.created_at,
                "updated_at": stored.updated_at,
            })
            cls._cache[name] = skill
            return skill
        except Exception as exc:  # noqa: BLE001
            logger.error("skill_registry_get_failed", name=name, error=str(exc))
            return None

    # ------------------------------------------------------------------ #
    # Save / delete
    # ------------------------------------------------------------------ #
    @classmethod
    def save_skill(cls, skill: Skill) -> Skill:
        skill.validate()
        try:
            from app.memory.memory import MemoryStore
            MemoryStore.skills.add(
                name=skill.name,
                description=skill.description,
                version=skill.version,
                steps=[s.to_dict() for s in skill.steps],
                required_tools=skill.required_tools,
                verification=skill.verification,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("skill_registry_save_failed", name=skill.name, error=str(exc))
            raise SkillDefinitionError(f"Cannot save skill: {exc}") from exc

        cls._cache[skill.name] = skill
        logger.info("skill_registered", name=skill.name, steps=len(skill.steps))
        return skill

    @classmethod
    def delete_skill(cls, name: str) -> bool:
        cls._cache.pop(name, None)
        try:
            from app.memory.memory import MemoryStore
            return MemoryStore.skills.delete(name)
        except Exception as exc:  # noqa: BLE001
            logger.warning("skill_registry_delete_failed", name=name, error=str(exc))
            return False

    @classmethod
    def clear_cache(cls) -> None:
        cls._cache.clear()

    @classmethod
    def count(cls) -> int:
        return len(cls.list_skills())
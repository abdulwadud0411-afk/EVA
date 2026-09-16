"""
Retention policies for EVA storage (Phase 11).

A policy describes how long a given category of files is kept and
whether it is protected from automatic cleanup.

Categories:
    - protected  : knowledge, memory, skills, user exports
    - ephemeral  : temp screenshots, temp recordings, cache, raw media
    - archivable : old knowledge, cold media (moved to HDD, not deleted)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger

logger = get_logger(__name__)


class PolicyError(Exception):
    """Raised when a retention policy is invalid."""


class ContentClass(str, Enum):
    """How the content is treated by the lifecycle manager."""
    PROTECTED = "protected"      # never auto-deleted
    EPHEMERAL = "ephemeral"      # auto-deleted after N days
    ARCHIVABLE = "archivable"    # moved to cold storage after N days


@dataclass
class CategoryPolicy:
    """Policy for one storage category."""
    name: str
    content_class: ContentClass
    retention_days: int = 0              # 0 = never delete
    archive_after_days: int = 0          # 0 = never archive
    max_size_mb: int = 0                 # 0 = no per-category quota
    protected: bool = False              # hard protection flag

    def is_expired(self, age_days: float) -> bool:
        if self.protected:
            return False
        if self.retention_days <= 0:
            return False
        return age_days >= self.retention_days

    def should_archive(self, age_days: float) -> bool:
        if self.content_class != ContentClass.ARCHIVABLE:
            return False
        if self.archive_after_days <= 0:
            return False
        return age_days >= self.archive_after_days


class RetentionPolicy:
    """Loads and exposes retention policies from config."""

    # Categories the manager knows how to handle.
    KNOWN_CATEGORIES = {
        "temp_screenshots": CategoryPolicy(
            name="temp_screenshots",
            content_class=ContentClass.EPHEMERAL,
            retention_days=2,
        ),
        "user_screenshots": CategoryPolicy(
            name="user_screenshots",
            content_class=ContentClass.PROTECTED,
            protected=True,
        ),
        "temp_recordings": CategoryPolicy(
            name="temp_recordings",
            content_class=ContentClass.EPHEMERAL,
            retention_days=3,
        ),
        "user_recordings": CategoryPolicy(
            name="user_recordings",
            content_class=ContentClass.PROTECTED,
            protected=True,
        ),
        "temp_media": CategoryPolicy(
            name="temp_media",
            content_class=ContentClass.EPHEMERAL,
            retention_days=7,
        ),
        "cache": CategoryPolicy(
            name="cache",
            content_class=ContentClass.EPHEMERAL,
            retention_days=1,
        ),
        "logs": CategoryPolicy(
            name="logs",
            content_class=ContentClass.EPHEMERAL,
            retention_days=30,
        ),
        "exports": CategoryPolicy(
            name="exports",
            content_class=ContentClass.PROTECTED,
            protected=True,
        ),
        "knowledge": CategoryPolicy(
            name="knowledge",
            content_class=ContentClass.PROTECTED,
            protected=True,
        ),
        "skills": CategoryPolicy(
            name="skills",
            content_class=ContentClass.PROTECTED,
            protected=True,
        ),
        "memory": CategoryPolicy(
            name="memory",
            content_class=ContentClass.PROTECTED,
            protected=True,
        ),
        "workspace": CategoryPolicy(
            name="workspace",
            content_class=ContentClass.PROTECTED,
            protected=True,
        ),
    }

    def __init__(self) -> None:
        self._policies: Dict[str, CategoryPolicy] = dict(self.KNOWN_CATEGORIES)
        self._load_from_config()

    def _load_from_config(self) -> None:
        """Override defaults with values from config.yaml."""
        cfg = ConfigManager.get("storage.retention", {}) or {}

        # Map config keys to category names
        overrides = {
            "screenshots_days": "temp_screenshots",
            "raw_audio_days": "temp_recordings",
            "raw_video_days": "temp_media",
            "cache_days": "cache",
            "extracted_frames_days": "temp_media",
        }

        for cfg_key, category in overrides.items():
            if cfg_key in cfg:
                try:
                    days = int(cfg[cfg_key])
                except (TypeError, ValueError):
                    continue
                if category in self._policies:
                    self._policies[category].retention_days = max(0, days)

        # User screenshots: if explicitly protected, keep as is
        if cfg.get("protect_user_memory", True) is False:
            for name in ("knowledge", "skills", "memory"):
                if name in self._policies:
                    self._policies[name].protected = False

        # Archive after N days for cold data
        try:
            archive_days = int(ConfigManager.get("storage.archive_after_days", 30))
            if archive_days > 0:
                for name in ("knowledge", "temp_media"):
                    if name in self._policies:
                        self._policies[name].archive_after_days = archive_days
        except (TypeError, ValueError):
            pass

    # ------------------------------------------------------------------ #
    # API
    # ------------------------------------------------------------------ #
    def get(self, category: str) -> CategoryPolicy:
        policy = self._policies.get(category)
        if policy is None:
            raise PolicyError(f"Unknown storage category: {category}")
        return policy

    def all_categories(self) -> Dict[str, CategoryPolicy]:
        return dict(self._policies)

    def is_protected(self, category: str) -> bool:
        p = self._policies.get(category)
        return bool(p and p.protected)

    def retention_days(self, category: str) -> int:
        p = self._policies.get(category)
        return int(p.retention_days) if p else 0
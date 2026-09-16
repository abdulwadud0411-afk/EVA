"""
Protection rules (Phase 11).

Marks specific files or items as permanently protected from cleanup,
even if their category is ephemeral. Also enforces global protection
categories (knowledge, memory, skills).

Protection metadata is stored in a JSON sidecar file so it survives
across sessions.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List, Set

from app.core.logger import get_logger

logger = get_logger(__name__)


class ProtectionError(Exception):
    """Raised when a protection operation fails."""


# Global protected categories (never cleaned)
GLOBAL_PROTECTED_CATEGORIES: Set[str] = {
    "knowledge",
    "skills",
    "memory",
    "exports",
    "user_screenshots",
    "user_recordings",
    "workspace",
}


class ProtectionManager:
    """Track manually protected file paths."""

    _protected_paths: Set[str] = set()
    _loaded: bool = False
    _sidecar_path: Path = Path("./data/.protection.json")

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #
    @classmethod
    def _sidecar(cls) -> Path:
        from app.core.config_manager import ConfigManager
        return ConfigManager.get_data_dir() / ".protection.json"

    @classmethod
    def load(cls) -> None:
        """Load protected paths from disk."""
        if cls._loaded:
            return
        path = cls._sidecar()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                cls._protected_paths = set(data.get("paths", []))
                logger.info("protection_loaded", count=len(cls._protected_paths))
            except Exception as exc:  # noqa: BLE001
                logger.warning("protection_load_failed", error=str(exc))
                cls._protected_paths = set()
        cls._loaded = True

    @classmethod
    def _save(cls) -> None:
        path = cls._sidecar()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {"paths": sorted(cls._protected_paths), "updated": time.time()},
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.error("protection_save_failed", error=str(exc))

    # ------------------------------------------------------------------ #
    # API
    # ------------------------------------------------------------------ #
    @classmethod
    def protect(cls, path: Path | str) -> None:
        """Mark a file as protected (never auto-deleted)."""
        cls.load()
        cls._protected_paths.add(str(Path(path).resolve()))
        cls._save()
        logger.info("protection_added", path=str(path))

    @classmethod
    def unprotect(cls, path: Path | str) -> None:
        cls.load()
        cls._protected_paths.discard(str(Path(path).resolve()))
        cls._save()

    @classmethod
    def is_protected(cls, path: Path | str) -> bool:
        cls.load()
        return str(Path(path).resolve()) in cls._protected_paths

    @classmethod
    def is_category_protected(cls, category: str) -> bool:
        return category in GLOBAL_PROTECTED_CATEGORIES

    @classmethod
    def list_protected(cls) -> List[str]:
        cls.load()
        return sorted(cls._protected_paths)
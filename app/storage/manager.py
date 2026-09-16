"""
Storage Manager (Phase 11).

The single gateway for every write into EVA's data directory.
Automatically routes files to the correct sub-folder based on
category, applies retention policy, and enforces protection.

Usage:
    from app.storage.manager import StorageManager

    path = StorageManager.save(
        category="temp_screenshots",
        filename="shot.png",
        content=b"...",
    )

    StorageManager.cleanup()
    StorageManager.stats()
"""
from __future__ import annotations

import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger
from app.storage.policies import RetentionPolicy, PolicyError

logger = get_logger(__name__)


class StorageError(Exception):
    """Raised when a storage operation fails."""


# Mapping: category -> sub-folder under data_dir
_CATEGORY_FOLDERS: Dict[str, str] = {
    "temp_screenshots": "screenshots/temp",
    "user_screenshots": "screenshots/user",
    "temp_recordings": "recordings/temp",
    "user_recordings": "recordings/user",
    "temp_media": "media/temp",
    "cache": "cache",
    "logs": "logs",
    "exports": "exports",
    "knowledge": "knowledge",
    "skills": "skills",
    "memory": "memory",
    "workspace": "workspace",
    "archive": "archive",
}


class StorageManager:
    """Centralized storage operations."""

    _policy: Optional[RetentionPolicy] = None

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @classmethod
    def _get_policy(cls) -> RetentionPolicy:
        if cls._policy is None:
            cls._policy = RetentionPolicy()
        return cls._policy

    @classmethod
    def reload_policy(cls) -> None:
        """Re-read policies from config (used after config change)."""
        cls._policy = RetentionPolicy()

    @classmethod
    def data_root(cls) -> Path:
        return ConfigManager.get_data_dir()

    @classmethod
    def folder_for(cls, category: str) -> Path:
        """Return the absolute directory for a category, creating it if needed."""
        sub = _CATEGORY_FOLDERS.get(category)
        if sub is None:
            raise StorageError(f"Unknown storage category: {category}")
        d = cls.data_root() / sub
        d.mkdir(parents=True, exist_ok=True)
        return d

    # ------------------------------------------------------------------ #
    # Save
    # ------------------------------------------------------------------ #
    @classmethod
    def save(
        cls,
        category: str,
        filename: str,
        content: bytes,
        timestamp: Optional[float] = None,
    ) -> Path:
        """
        Write a file to the correct category folder.

        Returns the absolute path to the created file.
        """
        if not filename or "/" in filename or "\\" in filename:
            raise StorageError(f"Invalid filename: {filename!r}")

        # Ensure policy knows this category
        try:
            cls._get_policy().get(category)
        except PolicyError as exc:
            raise StorageError(str(exc)) from exc

        folder = cls.folder_for(category)
        target = folder / filename

        # If timestamp is provided, back-date the mtime (used by tests)
        try:
            target.write_bytes(content)
        except OSError as exc:
            raise StorageError(f"Failed to write {target}: {exc}") from exc

        if timestamp is not None:
            try:
                import os
                os.utime(target, (timestamp, timestamp))
            except OSError:
                pass

        logger.info(
            "storage_saved",
            category=category,
            path=str(target),
            size=len(content),
        )
        return target

    @classmethod
    def save_text(
        cls,
        category: str,
        filename: str,
        text: str,
        timestamp: Optional[float] = None,
    ) -> Path:
        return cls.save(category, filename, text.encode("utf-8"), timestamp=timestamp)

    # ------------------------------------------------------------------ #
    # Info
    # ------------------------------------------------------------------ #
    @classmethod
    def stats(cls) -> Dict[str, Any]:
        """Return a per-category summary of files and bytes."""
        result: Dict[str, Any] = {
            "data_root": str(cls.data_root()),
            "total_files": 0,
            "total_bytes": 0,
            "categories": {},
        }
        for category, sub in _CATEGORY_FOLDERS.items():
            folder = cls.data_root() / sub
            if not folder.exists():
                continue
            count = 0
            size = 0
            for p in folder.rglob("*"):
                if p.is_file():
                    try:
                        size += p.stat().st_size
                        count += 1
                    except OSError:
                        continue
            result["categories"][category] = {
                "folder": str(folder),
                "files": count,
                "bytes": size,
            }
            result["total_files"] += count
            result["total_bytes"] += size
        return result

    @classmethod
    def age_days(cls, path: Path) -> float:
        """Return the file's age in days."""
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return 0.0
        return (time.time() - mtime) / 86400.0

    # ------------------------------------------------------------------ #
    # Cleanup (basic — extended in cleaner.py)
    # ------------------------------------------------------------------ #
    @classmethod
    def cleanup_category(cls, category: str, dry_run: bool = False) -> Dict[str, Any]:
        """
        Delete expired files in a single category.

        Protected categories are skipped entirely.
        Returns a summary dict.
        """
        policy = cls._get_policy().get(category)
        summary = {
            "category": category,
            "removed": 0,
            "removed_bytes": 0,
            "skipped_protected": policy.protected,
        }
        if policy.protected:
            return summary

        folder = cls.folder_for(category)
        for p in list(folder.rglob("*")):
            if not p.is_file():
                continue
            age = cls.age_days(p)
            if not policy.is_expired(age):
                continue
            try:
                size = p.stat().st_size
            except OSError:
                size = 0
            if not dry_run:
                try:
                    p.unlink()
                except OSError as exc:
                    logger.warning(
                        "cleanup_unlink_failed",
                        path=str(p),
                        error=str(exc),
                    )
                    continue
            summary["removed"] += 1
            summary["removed_bytes"] += size

        if summary["removed"] > 0:
            logger.info(
                "cleanup_done",
                category=category,
                removed=summary["removed"],
                bytes=summary["removed_bytes"],
                dry_run=dry_run,
            )
        return summary

    @classmethod
    def cleanup_all(cls, dry_run: bool = False) -> Dict[str, Any]:
        """Run cleanup across every category."""
        results = {}
        for category in _CATEGORY_FOLDERS.keys():
            if category == "archive":
                continue
            results[category] = cls.cleanup_category(category, dry_run=dry_run)
        return results
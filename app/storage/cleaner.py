"""
Scheduled cleanup (Phase 11).

Runs on startup and optionally daily. Uses StorageManager for
retention enforcement and TieredStorage for cold archival.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger
from app.storage.manager import StorageManager, _CATEGORY_FOLDERS
from app.storage.policies import ContentClass
from app.storage.tiers import TieredStorage

logger = get_logger(__name__)


class Cleaner:
    """High-level cleanup orchestrator."""

    @classmethod
    def run_startup(cls) -> Dict[str, Any]:
        """Runs on EVA startup if configured."""
        if not ConfigManager.get("storage.maintenance.run_on_startup", True):
            return {"skipped": True, "reason": "disabled"}
        return cls.run_full()

    @classmethod
    def run_full(cls) -> Dict[str, Any]:
        """Full cleanup: retention + archive + compaction (delegates)."""
        results: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "retention": {},
            "archive": {},
            "vacuum": None,
        }

        # 1. Retention cleanup per category
        for category in _CATEGORY_FOLDERS.keys():
            if category == "archive":
                continue
            try:
                results["retention"][category] = StorageManager.cleanup_category(category)
            except Exception as exc:  # noqa: BLE001
                logger.warning("cleanup_category_failed", category=category, error=str(exc))
                results["retention"][category] = {"error": str(exc)}

        # 2. Archival (move cold data to HDD)
        if TieredStorage.is_available():
            archive_days = int(ConfigManager.get("storage.archive_after_days", 30))
            archived = cls._archive_old(categories=("knowledge", "temp_media"), age_days=archive_days)
            results["archive"] = {"moved": archived, "age_days": archive_days}

        # 3. Compaction (SQLite VACUUM + log rotate)
        try:
            from app.storage.compactor import Compactor
            results["vacuum"] = Compactor.run_all()
        except Exception as exc:  # noqa: BLE001
            logger.warning("compaction_failed", error=str(exc))
            results["vacuum"] = {"error": str(exc)}

        logger.info("cleanup_full_done", summary=results)
        return results

    @classmethod
    def _archive_old(cls, categories: tuple, age_days: int) -> int:
        """Move files older than age_days to cold tier."""
        if age_days <= 0:
            return 0
        moved = 0
        for category in categories:
            try:
                folder = StorageManager.folder_for(category)
            except Exception:  # noqa: BLE001
                continue
            policy = StorageManager._get_policy().get(category)
            if policy.content_class != ContentClass.ARCHIVABLE and not policy.should_archive(0):
                # allow archiving even if not explicitly archivable
                pass
            for p in list(folder.rglob("*")):
                if not p.is_file():
                    continue
                age = StorageManager.age_days(p)
                if age < age_days:
                    continue
                new_path = TieredStorage.move_to_cold(p)
                if new_path is not None:
                    moved += 1
        return moved
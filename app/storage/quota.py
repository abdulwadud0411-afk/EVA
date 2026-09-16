"""
Quota enforcement (Phase 11).

Warns at N% of quota, blocks new writes at M%. Never deletes data
to satisfy a quota. If quota is exceeded, callers must clean manually.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger

logger = get_logger(__name__)


class QuotaError(Exception):
    """Raised when a write would exceed a hard quota."""


class QuotaGuard:
    """Check per-category and total quota limits."""

    @staticmethod
    def _bytes_of(path: Path) -> int:
        total = 0
        if not path.exists():
            return 0
        for p in path.rglob("*"):
            if p.is_file():
                try:
                    total += p.stat().st_size
                except OSError:
                    continue
        return total

    @classmethod
    def category_usage_mb(cls, folder: Path) -> float:
        return cls._bytes_of(folder) / (1024 * 1024)

    @classmethod
    def check_write_allowed(
        cls,
        category: str,
        additional_bytes: int,
        folder: Path,
    ) -> Dict[str, Any]:
        """
        Check whether adding `additional_bytes` to `category` is allowed.

        Returns:
            {"allowed": bool, "warn": bool, "usage_mb": float, "quota_mb": int}
        """
        quota_map = {
            "temp_screenshots": "storage.quotas.screenshots_mb",
            "user_screenshots": "storage.quotas.screenshots_mb",
            "temp_recordings": "storage.quotas.media_mb",
            "temp_media": "storage.quotas.media_mb",
            "cache": "storage.quotas.cache_mb",
        }
        quota_key = quota_map.get(category)
        quota_mb = 0
        if quota_key:
            try:
                quota_mb = int(ConfigManager.get(quota_key, 0))
            except (TypeError, ValueError):
                quota_mb = 0

        warn_pct = int(ConfigManager.get("storage.quotas.warn_at_percent", 80))
        block_pct = int(ConfigManager.get("storage.quotas.block_at_percent", 95))

        usage_mb = cls.category_usage_mb(folder) + (additional_bytes / (1024 * 1024))

        if quota_mb <= 0:
            return {"allowed": True, "warn": False, "usage_mb": usage_mb, "quota_mb": 0}

        used_pct = (usage_mb / quota_mb) * 100.0
        allowed = used_pct < block_pct
        warn = used_pct >= warn_pct

        if not allowed:
            logger.warning(
                "quota_blocked",
                category=category,
                used_pct=round(used_pct, 1),
                quota_mb=quota_mb,
            )
        elif warn:
            logger.warning(
                "quota_warning",
                category=category,
                used_pct=round(used_pct, 1),
                quota_mb=quota_mb,
            )

        return {
            "allowed": allowed,
            "warn": warn,
            "usage_mb": round(usage_mb, 2),
            "quota_mb": quota_mb,
            "used_pct": round(used_pct, 1),
        }

    @classmethod
    def disk_free_mb(cls, path: Path) -> float:
        try:
            usage = shutil.disk_usage(path)
            return usage.free / (1024 * 1024)
        except OSError:
            return 0.0
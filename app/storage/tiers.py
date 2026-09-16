"""
Tiered storage routing (Phase 11).

EVA can store data on two tiers:
    - HOT   : SSD (fast, limited) — active data
    - COLD  : HDD (slow, large)   — archives, old knowledge

If `storage.hdd_root` is not configured, everything stays on SSD.
"""
from __future__ import annotations

import shutil
from enum import Enum
from pathlib import Path
from typing import Optional

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger

logger = get_logger(__name__)


class Tier(str, Enum):
    HOT = "hot"       # SSD
    COLD = "cold"     # HDD


class TierError(Exception):
    """Raised when a tier operation fails."""


class TieredStorage:
    """Route data between SSD and HDD based on configuration."""

    @staticmethod
    def hot_root() -> Path:
        """SSD root (data dir)."""
        return ConfigManager.get_data_dir()

    @staticmethod
    def cold_root() -> Optional[Path]:
        """HDD root if configured, else None."""
        raw = str(ConfigManager.get("storage.hdd_root", "") or "").strip()
        if not raw:
            return None
        p = Path(raw)
        try:
            p.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.warning("hdd_root_unavailable", path=str(p), error=str(exc))
            return None
        return p

    @classmethod
    def is_available(cls) -> bool:
        return cls.cold_root() is not None

    @classmethod
    def archive_path(cls, source: Path) -> Optional[Path]:
        """
        Return the corresponding path on the cold tier for a hot file.

        Returns None if the cold tier is not configured.
        """
        cold = cls.cold_root()
        if cold is None:
            return None
        try:
            rel = source.relative_to(cls.hot_root())
        except ValueError:
            return None
        return cold / rel

    @classmethod
    def move_to_cold(cls, source: Path) -> Optional[Path]:
        """
        Move a file from hot tier to cold tier.

        Returns the new path, or None if cold tier unavailable.
        """
        target = cls.archive_path(source)
        if target is None:
            return None
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(target))
            logger.info(
                "tier_moved_to_cold",
                source=str(source),
                target=str(target),
            )
            return target
        except OSError as exc:
            logger.error("tier_move_failed", source=str(source), error=str(exc))
            return None
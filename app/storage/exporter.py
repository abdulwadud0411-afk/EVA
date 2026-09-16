"""
User-driven export (Phase 11).

Exports protected content (knowledge, memory, skills, user files)
to a user-chosen directory. Never touched by auto-cleanup.
"""
from __future__ import annotations

import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger

logger = get_logger(__name__)


class Exporter:
    """Export protected content to a ZIP archive."""

    PROTECTED_CATEGORIES = (
        "knowledge",
        "skills",
        "memory",
        "exports",
        "user_screenshots",
        "user_recordings",
        "workspace",
    )

    @classmethod
    def export_to_zip(
        cls,
        destination: Path,
        categories: List[str] | None = None,
    ) -> Path:
        """
        Create a ZIP of the chosen categories.

        Returns the ZIP path.
        """
        data_root = ConfigManager.get_data_dir()
        destination = Path(destination).expanduser()
        destination.parent.mkdir(parents=True, exist_ok=True)

        if categories is None:
            categories = list(cls.PROTECTED_CATEGORIES)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_path = destination / f"eva_export_{timestamp}.zip"

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for cat in categories:
                folder = data_root / cat
                if not folder.exists() or not folder.is_dir():
                    continue
                for p in folder.rglob("*"):
                    if p.is_file():
                        rel = p.relative_to(data_root)
                        zf.write(p, arcname=str(rel))

        logger.info(
            "export_created",
            path=str(zip_path),
            categories=categories,
            size=zip_path.stat().st_size,
        )
        return zip_path

    @classmethod
    def export_stats(cls) -> Dict[str, Any]:
        """Summary of what would be exported."""
        data_root = ConfigManager.get_data_dir()
        result: Dict[str, Any] = {"categories": {}, "total_bytes": 0}
        for cat in cls.PROTECTED_CATEGORIES:
            folder = data_root / cat
            if not folder.exists():
                continue
            size = 0
            count = 0
            for p in folder.rglob("*"):
                if p.is_file():
                    try:
                        size += p.stat().st_size
                        count += 1
                    except OSError:
                        continue
            result["categories"][cat] = {"files": count, "bytes": size}
            result["total_bytes"] += size
        return result
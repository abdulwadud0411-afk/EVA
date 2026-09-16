"""
Database and log compaction (Phase 11).

Tasks:
    - SQLite VACUUM (reclaim space after deletes)
    - Log rotation (delete logs older than N days)
    - Cache purge (safe)
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any, Dict

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger

logger = get_logger(__name__)


class Compactor:
    """Run database and log maintenance."""

    @classmethod
    def run_all(cls) -> Dict[str, Any]:
        results: Dict[str, Any] = {
            "sqlite_vacuum": None,
            "log_rotation": None,
        }
        if ConfigManager.get("storage.maintenance.vacuum_sqlite", True):
            results["sqlite_vacuum"] = cls.vacuum_sqlite()
        results["log_rotation"] = cls.rotate_logs()
        return results

    # ------------------------------------------------------------------ #
    # SQLite
    # ------------------------------------------------------------------ #
    @classmethod
    def vacuum_sqlite(cls) -> Dict[str, Any]:
        db_path = ConfigManager.get_data_dir() / "eva.db"
        if not db_path.exists():
            return {"skipped": True, "reason": "db_not_found"}

        size_before = db_path.stat().st_size
        try:
            conn = sqlite3.connect(str(db_path))
            try:
                conn.execute("VACUUM")
                conn.commit()
            finally:
                conn.close()
        except sqlite3.Error as exc:
            logger.warning("sqlite_vacuum_failed", error=str(exc))
            return {"error": str(exc)}
        size_after = db_path.stat().st_size
        return {
            "size_before": size_before,
            "size_after": size_after,
            "saved_bytes": size_before - size_after,
        }

    # ------------------------------------------------------------------ #
    # Log rotation
    # ------------------------------------------------------------------ #
    @classmethod
    def rotate_logs(cls) -> Dict[str, Any]:
        days = int(ConfigManager.get("storage.maintenance.rotate_logs_days", 30))
        if days <= 0:
            return {"skipped": True, "reason": "disabled"}

        log_dir = ConfigManager.get_data_dir() / "logs"
        if not log_dir.exists():
            return {"removed": 0}

        cutoff = time.time() - days * 86400
        removed = 0
        for p in list(log_dir.glob("eva-*.jsonl")):
            try:
                if p.stat().st_mtime < cutoff:
                    p.unlink()
                    removed += 1
            except OSError:
                continue
        logger.info("log_rotation_done", removed=removed, days=days)
        return {"removed": removed, "days": days}
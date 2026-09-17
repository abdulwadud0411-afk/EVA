"""
Skill execution logger (Phase 15).

Records every skill execution into the `skill_runs` table in eva.db.
Enables audit + future learning-from-failures.

Note:
    The `skill_runs` table is created by `app.memory.database.SCHEMA`
    on every fresh DB init, so this module does NOT create its own
    schema. It only reads/writes rows.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.logger import get_logger
from app.memory.database import Database

logger = get_logger(__name__)


class SkillLogger:
    """Persist skill execution records to SQLite."""

    # ------------------------------------------------------------------ #
    # Log
    # ------------------------------------------------------------------ #
    @classmethod
    def log_result(cls, result: Any) -> Optional[int]:
        """Save a SkillResult (or dict) and return the row id."""
        try:
            data = result.to_dict() if hasattr(result, "to_dict") else dict(result)
        except Exception:  # noqa: BLE001
            return None

        try:
            now = datetime.now().isoformat()
            cur = Database.execute(
                """
                INSERT INTO skill_runs
                    (skill_name, success, steps_total, steps_completed,
                     duration_ms, error, results, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(data.get("skill_name", "")),
                    1 if data.get("success") else 0,
                    int(data.get("steps_total", 0)),
                    int(data.get("steps_completed", 0)),
                    int(data.get("duration_ms", 0)),
                    json.dumps(data.get("error")) if data.get("error") else None,
                    json.dumps(data.get("results") or [], ensure_ascii=False)[:20000],
                    now,
                ),
            )
            return cur.lastrowid
        except Exception as exc:  # noqa: BLE001
            logger.warning("skill_logger_save_failed", error=str(exc))
            return None

    # ------------------------------------------------------------------ #
    # Query
    # ------------------------------------------------------------------ #
    @classmethod
    def recent(cls, limit: int = 20) -> List[Dict[str, Any]]:
        try:
            rows = Database.fetchall(
                "SELECT * FROM skill_runs ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            return [dict(r) for r in rows]
        except Exception as exc:  # noqa: BLE001
            logger.warning("skill_logger_query_failed", error=str(exc))
            return []

    @classmethod
    def stats_for(cls, skill_name: str) -> Dict[str, Any]:
        try:
            row = Database.fetchone(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) AS successes,
                    AVG(duration_ms) AS avg_ms
                FROM skill_runs
                WHERE skill_name = ?
                """,
                (skill_name,),
            )
            if row is None:
                return {"total": 0, "successes": 0, "avg_ms": 0}
            return {
                "total": int(row["total"] or 0),
                "successes": int(row["successes"] or 0),
                "avg_ms": float(row["avg_ms"] or 0),
            }
        except Exception:  # noqa: BLE001
            return {"total": 0, "successes": 0, "avg_ms": 0}
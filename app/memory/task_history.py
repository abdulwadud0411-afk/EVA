"""
Task history (Phase 12).
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from app.core.logger import get_logger
from app.memory.database import Database
from app.memory.models import TaskRecord

logger = get_logger(__name__)


class TaskHistory:
    """CRUD for task records."""

    def start(self, description: str) -> TaskRecord:
        description = (description or "").strip()
        if not description:
            raise ValueError("Task description is required")
        now = datetime.now().isoformat()
        cur = Database.execute(
            "INSERT INTO tasks (description, status, created_at) VALUES (?, ?, ?)",
            (description, "running", now),
        )
        logger.info("task_started", id=cur.lastrowid, description=description[:80])
        return TaskRecord(
            id=cur.lastrowid,
            description=description,
            status="running",
            created_at=now,
        )

    def finish(self, task_id: int, status: str, result: Optional[str] = None) -> bool:
        if status not in ("completed", "failed", "cancelled"):
            raise ValueError(f"Invalid status: {status}")
        now = datetime.now().isoformat()
        cur = Database.execute(
            "UPDATE tasks SET status = ?, result = ?, completed_at = ? WHERE id = ?",
            (status, result, now, task_id),
        )
        logger.info("task_finished", id=task_id, status=status)
        return cur.rowcount > 0

    def get(self, task_id: int) -> Optional[TaskRecord]:
        row = Database.fetchone("SELECT * FROM tasks WHERE id = ?", (task_id,))
        return self._row_to_task(row) if row else None

    def recent(self, limit: int = 20) -> List[TaskRecord]:
        rows = Database.fetchall(
            "SELECT * FROM tasks ORDER BY id DESC LIMIT ?", (limit,)
        )
        return [self._row_to_task(r) for r in rows]

    def count(self) -> int:
        row = Database.fetchone("SELECT COUNT(*) AS c FROM tasks")
        return int(row["c"]) if row else 0

    @staticmethod
    def _row_to_task(row) -> TaskRecord:
        return TaskRecord(
            id=row["id"],
            description=row["description"],
            status=row["status"],
            result=row["result"],
            created_at=row["created_at"],
            completed_at=row["completed_at"],
        )
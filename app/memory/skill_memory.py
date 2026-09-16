"""
Skill memory (Phase 12).
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.logger import get_logger
from app.memory.database import Database
from app.memory.models import Skill

logger = get_logger(__name__)


class SkillMemory:
    """CRUD for skills."""

    def add(
        self,
        name: str,
        description: str = "",
        version: str = "1.0.0",
        steps: Optional[List[Dict[str, Any]]] = None,
        required_tools: Optional[List[str]] = None,
        verification: Optional[str] = None,
    ) -> Skill:
        name = (name or "").strip()
        if not name:
            raise ValueError("Skill name is required")

        now = datetime.now().isoformat()
        steps_json = json.dumps(steps or [])
        tools_json = json.dumps(required_tools or [])

        Database.execute(
            """
            INSERT INTO skills
                (name, description, version, steps, required_tools, verification, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                description = excluded.description,
                version = excluded.version,
                steps = excluded.steps,
                required_tools = excluded.required_tools,
                verification = excluded.verification,
                updated_at = excluded.updated_at
            """,
            (name, description, version, steps_json, tools_json, verification, now, now),
        )
        logger.info("skill_saved", name=name, version=version)
        return Skill(
            name=name,
            description=description,
            version=version,
            steps=steps or [],
            required_tools=required_tools or [],
            verification=verification,
            created_at=now,
            updated_at=now,
        )

    def get(self, name: str) -> Optional[Skill]:
        row = Database.fetchone("SELECT * FROM skills WHERE name = ?", (name,))
        return self._row_to_skill(row) if row else None

    def list(self, limit: int = 100) -> List[Skill]:
        rows = Database.fetchall(
            "SELECT * FROM skills ORDER BY updated_at DESC LIMIT ?", (limit,)
        )
        return [self._row_to_skill(r) for r in rows]

    def count(self) -> int:
        row = Database.fetchone("SELECT COUNT(*) AS c FROM skills")
        return int(row["c"]) if row else 0

    def delete(self, name: str) -> bool:
        cur = Database.execute("DELETE FROM skills WHERE name = ?", (name,))
        return cur.rowcount > 0

    @staticmethod
    def _row_to_skill(row) -> Skill:
        try:
            steps = json.loads(row["steps"]) if row["steps"] else []
        except json.JSONDecodeError:
            steps = []
        try:
            tools = json.loads(row["required_tools"]) if row["required_tools"] else []
        except json.JSONDecodeError:
            tools = []
        return Skill(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            version=row["version"],
            steps=steps,
            required_tools=tools,
            verification=row["verification"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
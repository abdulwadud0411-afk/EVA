"""
Knowledge memory (Phase 12).
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import List, Optional

from app.core.logger import get_logger
from app.memory.database import Database
from app.memory.models import KnowledgeEntry

logger = get_logger(__name__)


class KnowledgeMemory:
    """CRUD for knowledge entries."""

    def add(
        self,
        title: str,
        content: str,
        source_type: str = "manual",
        source_path: Optional[str] = None,
        tags: Optional[List[str]] = None,
        confidence: float = 1.0,
    ) -> KnowledgeEntry:
        title = (title or "").strip()
        content = (content or "").strip()
        if not title or not content:
            raise ValueError("Knowledge title and content are required")

        tags_json = json.dumps(tags or [])
        created = datetime.now().isoformat()

        cur = Database.execute(
            """
            INSERT INTO knowledge_entries
                (title, content, source_type, source_path, tags, confidence, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (title, content, source_type, source_path, tags_json, confidence, created),
        )
        logger.info("knowledge_added", title=title, source=source_type)
        return KnowledgeEntry(
            id=cur.lastrowid,
            title=title,
            content=content,
            source_type=source_type,
            source_path=source_path,
            tags=tags or [],
            confidence=confidence,
            created_at=created,
        )

    def get(self, entry_id: int) -> Optional[KnowledgeEntry]:
        row = Database.fetchone(
            "SELECT * FROM knowledge_entries WHERE id = ?", (entry_id,)
        )
        return self._row_to_entry(row) if row else None

    def list(self, limit: int = 100, offset: int = 0) -> List[KnowledgeEntry]:
        rows = Database.fetchall(
            "SELECT * FROM knowledge_entries ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return [self._row_to_entry(r) for r in rows]

    def search_text(self, query: str, limit: int = 20) -> List[KnowledgeEntry]:
        q = f"%{query}%"
        rows = Database.fetchall(
            """
            SELECT * FROM knowledge_entries
            WHERE title LIKE ? OR content LIKE ? OR tags LIKE ?
            ORDER BY id DESC LIMIT ?
            """,
            (q, q, q, limit),
        )
        return [self._row_to_entry(r) for r in rows]

    def count(self) -> int:
        row = Database.fetchone("SELECT COUNT(*) AS c FROM knowledge_entries")
        return int(row["c"]) if row else 0

    def delete(self, entry_id: int) -> bool:
        cur = Database.execute(
            "DELETE FROM knowledge_entries WHERE id = ?", (entry_id,)
        )
        return cur.rowcount > 0

    @staticmethod
    def _row_to_entry(row) -> KnowledgeEntry:
        try:
            tags = json.loads(row["tags"]) if row["tags"] else []
        except json.JSONDecodeError:
            tags = []
        return KnowledgeEntry(
            id=row["id"],
            title=row["title"],
            content=row["content"],
            source_type=row["source_type"],
            source_path=row["source_path"],
            tags=tags,
            confidence=float(row["confidence"] or 1.0),
            created_at=row["created_at"],
        )
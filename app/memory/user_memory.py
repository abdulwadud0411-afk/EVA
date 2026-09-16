"""
User memory (Phase 12).
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import List, Optional

from app.core.logger import get_logger
from app.memory.database import Database
from app.memory.models import Preference

logger = get_logger(__name__)


_FORBIDDEN_KEYS = re.compile(
    r"(password|passwd|secret|token|api[_-]?key|credit[_-]?card|cvv|ssn)",
    re.IGNORECASE,
)


class UserMemory:
    """Get/set user preferences with safety checks."""

    def set(self, key: str, value: str, category: str = "general") -> Preference:
        key = (key or "").strip()
        value = str(value or "").strip()
        if not key:
            raise ValueError("Preference key cannot be empty")
        if _FORBIDDEN_KEYS.search(key):
            raise ValueError(f"Refusing to store sensitive key: {key}")

        now = datetime.now().isoformat()
        Database.execute(
            """
            INSERT INTO preferences (key, value, category, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                category = excluded.category,
                updated_at = excluded.updated_at
            """,
            (key, value, category, now),
        )
        logger.info("user_preference_saved", key=key, category=category)
        return Preference(key=key, value=value, category=category, updated_at=now)

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        row = Database.fetchone(
            "SELECT value FROM preferences WHERE key = ?",
            (key,),
        )
        return row["value"] if row else default

    def all(self) -> List[Preference]:
        rows = Database.fetchall(
            "SELECT key, value, category, updated_at FROM preferences ORDER BY updated_at DESC"
        )
        return [
            Preference(
                key=r["key"],
                value=r["value"],
                category=r["category"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ]

    def delete(self, key: str) -> bool:
        cur = Database.execute("DELETE FROM preferences WHERE key = ?", (key,))
        return cur.rowcount > 0

    def set_preferred_name(self, name: str) -> Preference:
        return self.set("preferred_name", name, category="identity")

    def get_preferred_name(self) -> Optional[str]:
        return self.get("preferred_name")

    def set_language(self, lang: str) -> Preference:
        return self.set("language", lang, category="identity")

    def get_language(self) -> Optional[str]:
        return self.get("language")
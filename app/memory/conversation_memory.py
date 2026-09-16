"""
Conversation memory (Phase 12).
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.logger import get_logger
from app.memory.database import Database
from app.memory.models import Message

logger = get_logger(__name__)


class ConversationMemory:
    """CRUD for messages and conversations."""

    def __init__(self, conversation_id: Optional[str] = None) -> None:
        self.conversation_id = conversation_id or str(uuid.uuid4())
        self._ensure_conversation()

    def _ensure_conversation(self) -> None:
        row = Database.fetchone(
            "SELECT id FROM conversations WHERE id = ?",
            (self.conversation_id,),
        )
        if row is None:
            Database.execute(
                "INSERT INTO conversations (id, started_at) VALUES (?, ?)",
                (self.conversation_id, datetime.now().isoformat()),
            )

    def append(
        self,
        role: str,
        content: str,
        tool_name: Optional[str] = None,
        tool_arguments: Optional[Dict[str, Any]] = None,
        tool_result: Optional[Dict[str, Any]] = None,
    ) -> Message:
        timestamp = datetime.now().isoformat()
        args_json = json.dumps(tool_arguments, ensure_ascii=False) if tool_arguments else None
        res_json = json.dumps(tool_result, ensure_ascii=False) if tool_result else None

        cur = Database.execute(
            """
            INSERT INTO messages
                (conversation_id, role, content, timestamp, tool_name, tool_arguments, tool_result)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (self.conversation_id, role, content, timestamp, tool_name, args_json, res_json),
        )
        return Message(
            id=cur.lastrowid,
            conversation_id=self.conversation_id,
            role=role,
            content=content,
            timestamp=timestamp,
            tool_name=tool_name,
            tool_arguments=tool_arguments,
            tool_result=tool_result,
        )

    def append_user(self, content: str) -> Message:
        return self.append("user", content)

    def append_assistant(self, content: str) -> Message:
        return self.append("assistant", content)

    def append_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
        result: Dict[str, Any],
    ) -> Message:
        return self.append("tool", "", tool_name=name, tool_arguments=arguments, tool_result=result)

    def recent(self, limit: int = 20) -> List[Message]:
        rows = Database.fetchall(
            """
            SELECT * FROM messages
            WHERE conversation_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (self.conversation_id, limit),
        )
        messages = [self._row_to_message(r) for r in rows]
        messages.reverse()
        return messages

    def count(self) -> int:
        row = Database.fetchone(
            "SELECT COUNT(*) AS c FROM messages WHERE conversation_id = ?",
            (self.conversation_id,),
        )
        return int(row["c"]) if row else 0

    def close(self) -> None:
        Database.execute(
            "UPDATE conversations SET ended_at = ? WHERE id = ?",
            (datetime.now().isoformat(), self.conversation_id),
        )

    @staticmethod
    def _row_to_message(row) -> Message:
        args = None
        if row["tool_arguments"]:
            try:
                args = json.loads(row["tool_arguments"])
            except json.JSONDecodeError:
                args = None
        result = None
        if row["tool_result"]:
            try:
                result = json.loads(row["tool_result"])
            except json.JSONDecodeError:
                result = None
        return Message(
            id=row["id"],
            conversation_id=row["conversation_id"],
            role=row["role"],
            content=row["content"],
            timestamp=row["timestamp"],
            tool_name=row["tool_name"],
            tool_arguments=args,
            tool_result=result,
        )
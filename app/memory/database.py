"""
SQLite database layer for EVA memory (Phase 12).

Creates and manages `data/eva.db` with all required tables.
Thread-safe through a lock and short-lived connections.
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import List, Optional, Tuple

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger

logger = get_logger(__name__)


SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    ended_at TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    tool_name TEXT,
    tool_arguments TEXT,
    tool_result TEXT,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);
CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON messages(conversation_id, id);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp
    ON messages(timestamp);

CREATE TABLE IF NOT EXISTS preferences (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'general',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS knowledge_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    source_type TEXT NOT NULL DEFAULT 'manual',
    source_path TEXT,
    tags TEXT,
    embedding BLOB,
    confidence REAL NOT NULL DEFAULT 1.0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_knowledge_source
    ON knowledge_entries(source_type);
CREATE INDEX IF NOT EXISTS idx_knowledge_created
    ON knowledge_entries(created_at);

CREATE TABLE IF NOT EXISTS skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    version TEXT NOT NULL DEFAULT '1.0.0',
    steps TEXT,
    required_tools TEXT,
    verification TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_skills_name ON skills(name);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    result TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at);

CREATE TABLE IF NOT EXISTS facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL DEFAULT 'general',
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    source TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_facts_category ON facts(category);
CREATE INDEX IF NOT EXISTS idx_facts_key ON facts(key);
"""


class Database:
    """Low-level SQLite access layer."""

    _lock = threading.RLock()
    _initialized = False

    @classmethod
    def db_path(cls) -> Path:
        raw = str(ConfigManager.get("memory.database_path", "./data/eva.db"))
        p = Path(raw)
        if not p.is_absolute():
            p = ConfigManager.get_data_dir() / p.name
        return p

    @classmethod
    def connect(cls) -> sqlite3.Connection:
        path = cls.db_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    @classmethod
    def init(cls) -> None:
        if cls._initialized:
            return
        with cls._lock:
            try:
                conn = cls.connect()
                try:
                    conn.executescript(SCHEMA)
                    conn.commit()
                finally:
                    conn.close()
                cls._initialized = True
                logger.info("memory_db_initialized", path=str(cls.db_path()))
            except sqlite3.Error as exc:
                logger.error("memory_db_init_failed", error=str(exc))
                raise

    @classmethod
    def reset(cls) -> None:
        cls._initialized = False

    @classmethod
    def execute(cls, sql: str, params: Tuple = ()) -> sqlite3.Cursor:
        cls.init()
        with cls._lock:
            conn = cls.connect()
            try:
                cur = conn.execute(sql, params)
                conn.commit()
                return cur
            finally:
                conn.close()

    @classmethod
    def fetchone(cls, sql: str, params: Tuple = ()) -> Optional[sqlite3.Row]:
        cls.init()
        with cls._lock:
            conn = cls.connect()
            try:
                cur = conn.execute(sql, params)
                return cur.fetchone()
            finally:
                conn.close()

    @classmethod
    def fetchall(cls, sql: str, params: Tuple = ()) -> List[sqlite3.Row]:
        cls.init()
        with cls._lock:
            conn = cls.connect()
            try:
                cur = conn.execute(sql, params)
                return cur.fetchall()
            finally:
                conn.close()

    @classmethod
    def vacuum(cls) -> None:
        try:
            conn = cls.connect()
            try:
                conn.execute("VACUUM")
                conn.commit()
            finally:
                conn.close()
            logger.info("memory_db_vacuumed")
        except sqlite3.Error as exc:
            logger.warning("memory_db_vacuum_failed", error=str(exc))
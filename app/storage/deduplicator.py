"""
Content-based deduplication (Phase 11).

Prevents storing the same file multiple times. Uses SHA-256 hash
of file content as the key. A tiny SQLite-free JSON index tracks
hashes -> paths.

Usage:
    from app.storage.deduplicator import Deduplicator
    existing = Deduplicator.find_duplicate(content)
    if existing is None:
        Deduplicator.register(content, path)
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Dict, Optional

from app.core.logger import get_logger

logger = get_logger(__name__)


class Deduplicator:
    """Track content hashes to detect duplicates."""

    _index: Dict[str, str] = {}        # hash -> path
    _loaded: bool = False
    _algorithm: str = "sha256"

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #
    @classmethod
    def _index_path(cls) -> Path:
        from app.core.config_manager import ConfigManager
        return ConfigManager.get_data_dir() / ".dedup_index.json"

    @classmethod
    def load(cls) -> None:
        if cls._loaded:
            return
        path = cls._index_path()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                cls._index = dict(data.get("hashes", {}))
                cls._algorithm = data.get("algorithm", "sha256")
                logger.info("dedup_loaded", count=len(cls._index))
            except Exception as exc:  # noqa: BLE001
                logger.warning("dedup_load_failed", error=str(exc))
                cls._index = {}
        cls._loaded = True

    @classmethod
    def _save(cls) -> None:
        path = cls._index_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {
                        "algorithm": cls._algorithm,
                        "hashes": cls._index,
                        "updated": time.time(),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.error("dedup_save_failed", error=str(exc))

    # ------------------------------------------------------------------ #
    # API
    # ------------------------------------------------------------------ #
    @classmethod
    def hash_bytes(cls, content: bytes) -> str:
        return hashlib.new(cls._algorithm, content).hexdigest()

    @classmethod
    def hash_file(cls, path: Path) -> Optional[str]:
        try:
            h = hashlib.new(cls._algorithm)
            with open(path, "rb") as fh:
                for chunk in iter(lambda: fh.read(65536), b""):
                    h.update(chunk)
            return h.hexdigest()
        except OSError as exc:
            logger.warning("dedup_hash_file_failed", path=str(path), error=str(exc))
            return None

    @classmethod
    def find_duplicate(cls, content: bytes) -> Optional[str]:
        """Return existing path if content already exists, else None."""
        cls.load()
        digest = cls.hash_bytes(content)
        return cls._index.get(digest)

    @classmethod
    def register(cls, content: bytes, path: Path) -> str:
        """Record a hash -> path mapping."""
        cls.load()
        digest = cls.hash_bytes(content)
        cls._index[digest] = str(path)
        cls._save()
        return digest

    @classmethod
    def remove(cls, path: Path) -> None:
        """Remove an entry by path."""
        cls.load()
        target = str(path)
        to_remove = [h for h, p in cls._index.items() if p == target]
        for h in to_remove:
            cls._index.pop(h, None)
        if to_remove:
            cls._save()

    @classmethod
    def stats(cls) -> Dict[str, Any]:
        cls.load()
        return {
            "algorithm": cls._algorithm,
            "tracked": len(cls._index),
        }
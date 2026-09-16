"""
High-level KnowledgeStore facade (Phase 13).

Usage:
    from app.knowledge.knowledge_store import KnowledgeStore
    KnowledgeStore.ingest_file("C:/docs/manual.pdf")
    results = KnowledgeStore.query("how do I reset?")
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger
from app.knowledge.base import ExtractionError
from app.knowledge.orchestrator import Orchestrator

logger = get_logger(__name__)


class KnowledgeError(Exception):
    """Raised when knowledge operations fail."""


class KnowledgeStore:
    _orchestrator: Optional[Orchestrator] = None

    @classmethod
    def _get(cls) -> Orchestrator:
        if cls._orchestrator is None:
            if not ConfigManager.get("knowledge.enabled", True):
                raise KnowledgeError("Knowledge system is disabled in config")
            cls._orchestrator = Orchestrator()
        return cls._orchestrator

    @classmethod
    def reset(cls) -> None:
        cls._orchestrator = None

    # ------------------------------------------------------------------ #
    # Ingest
    # ------------------------------------------------------------------ #
    @classmethod
    def ingest_file(cls, path: str) -> Dict[str, Any]:
        try:
            return cls._get().ingest_file(path)
        except ExtractionError as exc:
            raise KnowledgeError(str(exc)) from exc

    @classmethod
    def ingest_url(cls, url: str) -> Dict[str, Any]:
        try:
            return cls._get().ingest_url(url)
        except ExtractionError as exc:
            raise KnowledgeError(str(exc)) from exc

    # ------------------------------------------------------------------ #
    # Query
    # ------------------------------------------------------------------ #
    @classmethod
    def query(cls, text: str, top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        return cls._get().query(text, top_k=top_k)

    @classmethod
    def clear(cls) -> None:
        cls._get().reset()
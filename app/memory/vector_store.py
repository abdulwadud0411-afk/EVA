"""
Vector store interface (Phase 12 placeholder).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class VectorStore(ABC):
    """Abstract interface for semantic search backends."""

    @abstractmethod
    def add(self, entry_id: int, embedding: bytes) -> None:
        ...

    @abstractmethod
    def search(
        self,
        query_embedding: bytes,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def delete(self, entry_id: int) -> None:
        ...


class NullVectorStore(VectorStore):
    """No-op vector store used until Phase 13."""

    def add(self, entry_id: int, embedding: bytes) -> None:
        return None

    def search(
        self,
        query_embedding: bytes,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        return []

    def delete(self, entry_id: int) -> None:
        return None
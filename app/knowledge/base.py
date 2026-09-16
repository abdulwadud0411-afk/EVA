"""
Abstract interfaces for the knowledge pipeline.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np


class ExtractionError(Exception):
    """Raised when a document cannot be extracted."""


@dataclass
class ExtractedDocument:
    """Result of extracting text from a source file."""
    title: str
    text: str
    source_type: str
    source_path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Chunk:
    """A piece of a document ready for embedding."""
    text: str
    index: int
    source_path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResult:
    """One match from semantic search."""
    chunk_id: int
    text: str
    score: float
    source_path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class DocumentExtractor(ABC):
    """Extract plain text from a file."""

    @abstractmethod
    def supports(self, path: Path) -> bool:
        ...

    @abstractmethod
    def extract(self, path: Path) -> ExtractedDocument:
        ...


class Embedder(ABC):
    """Convert text into vectors."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        ...

    @abstractmethod
    def embed(self, texts: List[str]) -> np.ndarray:
        """Return shape (len(texts), dimension) float32 array."""
        ...


class VectorStore(ABC):
    """Store and search vectors."""

    @abstractmethod
    def add(
        self,
        chunk_ids: List[int],
        embeddings: np.ndarray,
    ) -> None:
        ...

    @abstractmethod
    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 5,
    ) -> List[tuple]:
        """Return list of (chunk_id, score)."""
        ...

    @abstractmethod
    def save(self) -> None:
        ...

    @abstractmethod
    def load(self) -> bool:
        ...
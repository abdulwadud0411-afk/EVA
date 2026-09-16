"""
Embedder for RAG (Phase 13).

Two backends:
    - "fastembed" : local ONNX embeddings (default, ~150 MB model)
    - "hash"      : deterministic hash-based (no ML, used for tests/offline)

Config:
    knowledge.embedding.backend
    knowledge.embedding.model
    knowledge.embedding.dimension
"""
from __future__ import annotations

import hashlib
from typing import List, Optional

import numpy as np

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger
from app.knowledge.base import Embedder as BaseEmbedder

logger = get_logger(__name__)


class FastEmbedBackend(BaseEmbedder):
    """Local ONNX embedder using fastembed."""

    def __init__(self, model_name: Optional[str] = None, dimension: int = 384) -> None:
        self.model_name = model_name or str(
            ConfigManager.get("knowledge.embedding.model", "BAAI/bge-small-en-v1.5")
        )
        self._dimension = int(dimension)
        self._model = None

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        try:
            from fastembed import TextEmbedding  # type: ignore
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "fastembed not installed. Run: pip install fastembed"
            ) from exc
        cache_dir = str(ConfigManager.get("knowledge.embedding.cache_dir", "./models/embeddings"))
        self._model = TextEmbedding(model_name=self.model_name, cache_dir=cache_dir)
        try:
            # Detect dimension from a probe
            probe = list(self._model.embed(["dimension probe"]))
            self._dimension = int(np.asarray(probe[0]).shape[0])
        except Exception:  # noqa: BLE001
            pass
        logger.info("fastembed_loaded", model=self.model_name, dim=self._dimension)

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts: List[str]) -> np.ndarray:
        self._ensure_model()
        vectors = list(self._model.embed(texts))
        arr = np.asarray(vectors, dtype=np.float32)
        # L2 normalize for cosine similarity via inner product
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return arr / norms


class HashEmbedder(BaseEmbedder):
    """
    Deterministic bag-of-words hash embedder.

    Not truly semantic, but each *word* is hashed individually and
    summed. Documents that share words have non-zero similarity, which
    is enough for offline/testing use.
    """

    def __init__(self, dimension: int = 384) -> None:
        self._dimension = int(dimension)

    @property
    def dimension(self) -> int:
        return self._dimension

    def _word_vector(self, word: str) -> np.ndarray:
        h = hashlib.sha256(word.lower().encode("utf-8")).digest()
        reps = (self._dimension * 4 // len(h)) + 2
        expanded = (h * reps)[: self._dimension * 4]
        vals = np.frombuffer(expanded, dtype=np.uint32).astype(np.float32)
        return (vals / 0xFFFFFFFF) * 2.0 - 1.0

    def embed(self, texts: List[str]) -> np.ndarray:
        arr = np.zeros((len(texts), self._dimension), dtype=np.float32)
        for i, text in enumerate(texts):
            words = (text or "").lower().split()
            if not words:
                continue
            for w in words:
                arr[i] += self._word_vector(w)
            n = np.linalg.norm(arr[i])
            if n > 0:
                arr[i] /= n
        return arr


class Embedder:
    """Facade that returns the configured backend."""

    _instance: Optional[BaseEmbedder] = None

    @classmethod
    def get(cls) -> BaseEmbedder:
        if cls._instance is not None:
            return cls._instance
        backend = str(ConfigManager.get("knowledge.embedding.backend", "fastembed")).lower()
        dim = int(ConfigManager.get("knowledge.embedding.dimension", 384))
        if backend == "hash":
            cls._instance = HashEmbedder(dimension=dim)
            logger.info("embedder_backend_hash")
        else:
            try:
                cls._instance = FastEmbedBackend(dimension=dim)
                logger.info("embedder_backend_fastembed")
            except Exception as exc:  # noqa: BLE001
                logger.warning("fastembed_init_failed", error=str(exc))
                cls._instance = HashEmbedder(dimension=dim)
                logger.info("embedder_backend_fallback_hash")
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None
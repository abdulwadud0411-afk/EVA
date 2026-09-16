"""
FAISS-backed vector store with numpy fallback (Phase 13).

Persists to:
    <path>/<index_name>.index       (FAISS binary)
    <path>/<index_name>.meta.json   (chunk_id → source_path metadata)

If FAISS is not installed, uses brute-force numpy search.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger
from app.knowledge.base import VectorStore as BaseVectorStore

logger = get_logger(__name__)

try:
    import faiss  # type: ignore
    _FAISS_AVAILABLE = True
except Exception:  # noqa: BLE001
    faiss = None  # type: ignore
    _FAISS_AVAILABLE = False


class VectorStore(BaseVectorStore):
    def __init__(
        self,
        dimension: int = 384,
        path: Optional[str] = None,
        index_name: Optional[str] = None,
        backend: Optional[str] = None,
    ) -> None:
        self.dimension = int(dimension)
        base_path = path or str(ConfigManager.get("knowledge.vector_store.path", "./data/knowledge/vectors"))
        self.index_name = index_name or str(ConfigManager.get("knowledge.vector_store.index_name", "eva_knowledge"))
        self.path = Path(base_path)
        self.path.mkdir(parents=True, exist_ok=True)

        requested = (backend or str(ConfigManager.get("knowledge.vector_store.backend", "faiss"))).lower()
        if requested == "faiss" and _FAISS_AVAILABLE:
            self.backend = "faiss"
        else:
            self.backend = "numpy"

        self._index = None
        self._numpy_vectors: Optional[np.ndarray] = None
        self._chunk_ids: List[int] = []
        self._metadata: Dict[int, Dict] = {}

    # ------------------------------------------------------------------ #
    # File paths
    # ------------------------------------------------------------------ #
    def _index_path(self) -> Path:
        return self.path / f"{self.index_name}.index"

    def _meta_path(self) -> Path:
        return self.path / f"{self.index_name}.meta.json"

    # ------------------------------------------------------------------ #
    # Add
    # ------------------------------------------------------------------ #
    def add(
        self,
        chunk_ids: List[int],
        embeddings: np.ndarray,
    ) -> None:
        if embeddings.size == 0:
            return
        arr = np.asarray(embeddings, dtype=np.float32)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        if arr.shape[1] != self.dimension:
            raise ValueError(
                f"Embedding dim mismatch: got {arr.shape[1]}, expected {self.dimension}"
            )

        if self.backend == "faiss":
            if self._index is None:
                self._index = faiss.IndexFlatIP(self.dimension)
            self._index.add(arr)
        else:
            if self._numpy_vectors is None:
                self._numpy_vectors = arr
            else:
                self._numpy_vectors = np.vstack([self._numpy_vectors, arr])

        self._chunk_ids.extend(chunk_ids)
        for cid in chunk_ids:
            self._metadata[cid] = {}

        logger.info("vector_store_added", count=len(chunk_ids), total=len(self._chunk_ids))

    def set_metadata(self, chunk_id: int, metadata: Dict) -> None:
        self._metadata[chunk_id] = dict(metadata)

    # ------------------------------------------------------------------ #
    # Search
    # ------------------------------------------------------------------ #
    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 5,
    ) -> List[Tuple[int, float]]:
        if not self._chunk_ids:
            return []

        q = np.asarray(query_embedding, dtype=np.float32).reshape(1, -1)
        if q.shape[1] != self.dimension:
            raise ValueError("Query embedding dim mismatch")

        top_k = max(1, min(top_k, len(self._chunk_ids)))

        if self.backend == "faiss":
            if self._index is None or self._index.ntotal == 0:
                return []
            scores, ids = self._index.search(q, top_k)
            scores = scores[0]
            ids = ids[0]
            results: List[Tuple[int, float]] = []
            for idx, score in zip(ids, scores):
                if idx < 0 or idx >= len(self._chunk_ids):
                    continue
                results.append((self._chunk_ids[idx], float(score)))
            return results

        # Numpy brute-force (cosine = inner product on normalized vectors)
        if self._numpy_vectors is None or self._numpy_vectors.size == 0:
            return []
        scores = (self._numpy_vectors @ q.T).flatten()
        order = np.argsort(-scores)[:top_k]
        return [(self._chunk_ids[i], float(scores[i])) for i in order]

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #
    def save(self) -> None:
        try:
            if self.backend == "faiss" and self._index is not None:
                faiss.write_index(self._index, str(self._index_path()))
            else:
                np_path = self.path / f"{self.index_name}.npy"
                if self._numpy_vectors is not None:
                    np.save(str(np_path), self._numpy_vectors)

            meta = {
                "backend": self.backend,
                "dimension": self.dimension,
                "chunk_ids": self._chunk_ids,
                "metadata": {str(k): v for k, v in self._metadata.items()},
            }
            self._meta_path().write_text(
                json.dumps(meta, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.info("vector_store_saved", path=str(self.path))
        except Exception as exc:  # noqa: BLE001
            logger.error("vector_store_save_failed", error=str(exc))

    def load(self) -> bool:
        try:
            if not self._meta_path().exists():
                return False
            meta = json.loads(self._meta_path().read_text(encoding="utf-8"))
            self.dimension = int(meta.get("dimension", self.dimension))
            self._chunk_ids = [int(x) for x in meta.get("chunk_ids", [])]
            self._metadata = {int(k): v for k, v in (meta.get("metadata") or {}).items()}

            if self.backend == "faiss" and self._index_path().exists():
                self._index = faiss.read_index(str(self._index_path()))
            else:
                np_path = self.path / f"{self.index_name}.npy"
                if np_path.exists():
                    self._numpy_vectors = np.load(str(np_path))
            logger.info("vector_store_loaded", count=len(self._chunk_ids))
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("vector_store_load_failed", error=str(exc))
            return False

    def clear(self) -> None:
        self._index = None
        self._numpy_vectors = None
        self._chunk_ids = []
        self._metadata = {}

    def count(self) -> int:
        return len(self._chunk_ids)

    def get_metadata(self, chunk_id: int) -> Dict:
        return self._metadata.get(chunk_id, {})
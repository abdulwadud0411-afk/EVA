"""
Knowledge orchestrator (Phase 13).

Coordinates: Extractor → Chunker → Embedder → VectorStore → SQLite.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger
from app.knowledge.base import Chunk, ExtractedDocument, ExtractionError
from app.knowledge.chunker import Chunker
from app.knowledge.embedder import Embedder
from app.knowledge.vector_store import VectorStore
from app.knowledge.extractors import TextExtractor, DocumentExtractor, WebExtractor

logger = get_logger(__name__)


class Orchestrator:
    def __init__(self) -> None:
        self.chunker = Chunker()
        self.embedder = Embedder.get()
        self.store = VectorStore(dimension=self.embedder.dimension)
        self.store.load()
        self._text_ext = TextExtractor()
        self._doc_ext = DocumentExtractor()
        self._web_ext = WebExtractor()

    # ------------------------------------------------------------------ #
    # Public
    # ------------------------------------------------------------------ #
    def ingest_file(self, path: str) -> Dict[str, Any]:
        p = Path(path).expanduser()
        if not p.exists():
            raise ExtractionError(f"File not found: {p}")

        if self._doc_ext.supports(p):
            doc = self._doc_ext.extract(p)
        elif self._text_ext.supports(p):
            doc = self._text_ext.extract(p)
        else:
            raise ExtractionError(f"Unsupported file type: {p.suffix}")

        return self._ingest_document(doc)

    def ingest_url(self, url: str) -> Dict[str, Any]:
        text = self._web_ext.extract_url(url)
        doc = ExtractedDocument(
            title=url,
            text=text,
            source_type="web",
            source_path=url,
        )
        return self._ingest_document(doc)

    def query(self, text: str, top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        if not text.strip():
            return []
        k = int(top_k or ConfigManager.get("knowledge.retrieval.top_k", 5))
        min_score = float(ConfigManager.get("knowledge.retrieval.min_score", 0.30))

        q = self.embedder.embed([text])
        hits = self.store.search(q, top_k=k)
        results = []
        for chunk_id, score in hits:
            if score < min_score:
                continue
            meta = self.store.get_metadata(chunk_id)
            results.append({
                "chunk_id": chunk_id,
                "score": round(score, 4),
                "text": meta.get("text", ""),
                "source_path": meta.get("source_path"),
            })
        return results

    def reset(self) -> None:
        self.store.clear()
        self.store.save()

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #
    def _ingest_document(self, doc: ExtractedDocument) -> Dict[str, Any]:
        chunks = self.chunker.split(
            doc.text,
            source_path=doc.source_path,
            metadata={"source_type": doc.source_type, "title": doc.title},
        )
        if not chunks:
            return {"chunks": 0, "message": "No text extracted"}

        texts = [c.text for c in chunks]
        vectors = self.embedder.embed(texts)

        # We assign internal chunk IDs as sequential integers.
        start_id = self.store.count()
        chunk_ids = list(range(start_id, start_id + len(chunks)))

        self.store.add(chunk_ids, vectors)
        for cid, chunk in zip(chunk_ids, chunks):
            self.store.set_metadata(cid, {
                "text": chunk.text,
                "source_path": chunk.source_path,
                **(chunk.metadata or {}),
            })

        # Persist SQLite record for the document
        try:
            from app.memory.memory import MemoryStore
            MemoryStore.knowledge.add(
                title=doc.title or "untitled",
                content=doc.text[:5000],   # truncate for DB
                source_type=doc.source_type,
                source_path=doc.source_path,
                tags=[],
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("knowledge_sqlite_save_failed", error=str(exc))

        self.store.save()

        logger.info("ingest_done", chunks=len(chunks), source=doc.source_path)
        return {
            "chunks": len(chunks),
            "source": doc.source_path,
            "title": doc.title,
        }
"""
Text chunker for RAG (Phase 13).

Splits long text into overlapping chunks of ~chunk_size characters,
respecting paragraph boundaries where possible.
"""
from __future__ import annotations

from typing import List, Optional

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger
from app.knowledge.base import Chunk

logger = get_logger(__name__)


class Chunker:
    def __init__(
        self,
        chunk_size: Optional[int] = None,
        overlap: Optional[int] = None,
        max_chunks: Optional[int] = None,
    ) -> None:
        self.chunk_size = int(chunk_size or ConfigManager.get("knowledge.chunk_size", 500))
        self.overlap = int(overlap or ConfigManager.get("knowledge.chunk_overlap", 50))
        self.max_chunks = int(max_chunks or ConfigManager.get("knowledge.max_chunks_per_doc", 2000))
        if self.overlap >= self.chunk_size:
            self.overlap = max(0, self.chunk_size // 5)

    def split(
        self,
        text: str,
        source_path: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> List[Chunk]:
        text = (text or "").strip()
        if not text:
            return []

        # Split by paragraph first, then pack into chunks
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            paragraphs = [text]

        chunks: List[Chunk] = []
        buffer = ""

        def flush(buf: str) -> None:
            if not buf.strip():
                return
            chunks.append(Chunk(
                text=buf.strip(),
                index=len(chunks),
                source_path=source_path,
                metadata=metadata or {},
            ))

        for para in paragraphs:
            # Very large single paragraph -> hard split
            if len(para) > self.chunk_size:
                if buffer:
                    flush(buffer)
                    buffer = ""
                start = 0
                while start < len(para):
                    end = min(start + self.chunk_size, len(para))
                    chunks.append(Chunk(
                        text=para[start:end].strip(),
                        index=len(chunks),
                        source_path=source_path,
                        metadata=metadata or {},
                    ))
                    if end >= len(para):
                        break
                    start = end - self.overlap
                continue

            # Normal: append to buffer
            if not buffer:
                buffer = para
            elif len(buffer) + len(para) + 2 <= self.chunk_size:
                buffer = buffer + "\n\n" + para
            else:
                flush(buffer)
                buffer = para

        if buffer:
            flush(buffer)

        if len(chunks) > self.max_chunks:
            logger.warning("chunks_truncated", original=len(chunks), kept=self.max_chunks)
            chunks = chunks[: self.max_chunks]

        return chunks
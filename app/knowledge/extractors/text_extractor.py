"""
Plain-text extractor (.txt, .md, .log, .csv, .json).
"""
from __future__ import annotations

from pathlib import Path

from app.core.logger import get_logger
from app.knowledge.base import DocumentExtractor as BaseExtractor, ExtractedDocument, ExtractionError

logger = get_logger(__name__)


_TEXT_EXTENSIONS = {".txt", ".md", ".log", ".csv", ".json", ".yaml", ".yml", ".xml", ".html", ".htm"}


class TextExtractor(BaseExtractor):
    def supports(self, path: Path) -> bool:
        return path.suffix.lower() in _TEXT_EXTENSIONS

    def extract(self, path: Path) -> ExtractedDocument:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise ExtractionError(f"Cannot read {path}: {exc}") from exc
        return ExtractedDocument(
            title=path.stem,
            text=text,
            source_type="text",
            source_path=str(path),
            metadata={"extension": path.suffix.lower()},
        )
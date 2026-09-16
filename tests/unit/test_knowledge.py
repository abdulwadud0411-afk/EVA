"""
Tests for Phase 13 knowledge / RAG system.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app.core.config_manager import ConfigManager
from app.knowledge.base import Chunk, ExtractedDocument, ExtractionError
from app.knowledge.chunker import Chunker
from app.knowledge.embedder import Embedder, HashEmbedder
from app.knowledge.vector_store import VectorStore
from app.knowledge.extractors import TextExtractor, DocumentExtractor
from app.knowledge.knowledge_store import KnowledgeStore, KnowledgeError


@pytest.fixture(autouse=True)
def hash_embedder(tmp_path, monkeypatch):
    """Force the hash embedder + a temp vector store for tests."""
    ConfigManager.load()
    ConfigManager.set("knowledge.enabled", True, persist=False)
    ConfigManager.set("knowledge.embedding.backend", "hash", persist=False)
    ConfigManager.set("knowledge.embedding.dimension", 384, persist=False)
    ConfigManager.set("knowledge.vector_store.backend", "numpy", persist=False)
    ConfigManager.set("knowledge.vector_store.path", str(tmp_path / "vectors"), persist=False)
    Embedder.reset()
    KnowledgeStore.reset()
    yield
    Embedder.reset()
    KnowledgeStore.reset()


# ---------------------------------------------------------------------- #
# Chunker
# ---------------------------------------------------------------------- #
def test_chunker_empty():
    c = Chunker(chunk_size=100, overlap=10)
    assert c.split("") == []


def test_chunker_short_text():
    c = Chunker(chunk_size=1000, overlap=50)
    chunks = c.split("hello world")
    assert len(chunks) == 1
    assert chunks[0].text == "hello world"
    assert chunks[0].index == 0


def test_chunker_splits_long_text():
    c = Chunker(chunk_size=100, overlap=20)
    text = ("A" * 500) + "\n\n" + ("B" * 500)
    chunks = c.split(text)
    assert len(chunks) >= 2
    for ch in chunks:
        assert len(ch.text) <= 150


def test_chunker_max_chunks():
    c = Chunker(chunk_size=10, overlap=2, max_chunks=5)
    text = "x" * 1000
    chunks = c.split(text)
    assert len(chunks) <= 5


# ---------------------------------------------------------------------- #
# Embedder
# ---------------------------------------------------------------------- #
def test_hash_embedder_dimension():
    e = HashEmbedder(dimension=128)
    assert e.dimension == 128


def test_hash_embedder_output_shape():
    e = HashEmbedder(dimension=64)
    arr = e.embed(["hello", "world"])
    assert arr.shape == (2, 64)
    assert arr.dtype == np.float32


def test_hash_embedder_deterministic():
    e = HashEmbedder(dimension=32)
    a = e.embed(["same text"])[0]
    b = e.embed(["same text"])[0]
    np.testing.assert_allclose(a, b)


def test_hash_embedder_normalized():
    e = HashEmbedder(dimension=64)
    arr = e.embed(["normalize me"])
    n = np.linalg.norm(arr[0])
    assert abs(n - 1.0) < 1e-4


# ---------------------------------------------------------------------- #
# Vector store (numpy backend)
# ---------------------------------------------------------------------- #
def test_vector_store_add_and_search(tmp_path):
    vs = VectorStore(dimension=8, path=str(tmp_path), backend="numpy")
    vectors = np.eye(8, dtype=np.float32)
    vs.add([10, 20, 30], vectors[:3])
    assert vs.count() == 3

    q = np.eye(8, dtype=np.float32)[0:1]
    hits = vs.search(q, top_k=2)
    assert len(hits) == 2
    assert hits[0][0] == 10


def test_vector_store_save_load(tmp_path):
    vs = VectorStore(dimension=8, path=str(tmp_path), backend="numpy")
    vs.add([1, 2], np.eye(8, dtype=np.float32)[:2])
    vs.set_metadata(1, {"text": "one", "source_path": "x.txt"})
    vs.save()

    vs2 = VectorStore(dimension=8, path=str(tmp_path), backend="numpy")
    assert vs2.load() is True
    assert vs2.count() == 2
    assert vs2.get_metadata(1)["text"] == "one"


def test_vector_store_dim_mismatch(tmp_path):
    vs = VectorStore(dimension=8, path=str(tmp_path), backend="numpy")
    with pytest.raises(ValueError):
        vs.add([1], np.ones((1, 4), dtype=np.float32))


# ---------------------------------------------------------------------- #
# Extractors
# ---------------------------------------------------------------------- #
def test_text_extractor_supports_txt():
    te = TextExtractor()
    assert te.supports(Path("notes.txt"))
    assert te.supports(Path("readme.md"))
    assert not te.supports(Path("image.png"))


def test_text_extractor_reads(tmp_path):
    f = tmp_path / "note.txt"
    f.write_text("hello eva", encoding="utf-8")
    te = TextExtractor()
    doc = te.extract(f)
    assert doc.text == "hello eva"
    assert doc.source_type == "text"


def test_document_extractor_supports_pdf_docx():
    de = DocumentExtractor()
    assert de.supports(Path("a.pdf"))
    assert de.supports(Path("a.docx"))
    assert not de.supports(Path("a.txt"))


# ---------------------------------------------------------------------- #
# End-to-end: ingest + query
# ---------------------------------------------------------------------- #
def test_knowledge_ingest_and_query(tmp_path):
    f = tmp_path / "manual.txt"
    f.write_text(
        "How to reset the device.\n\n"
        "Press the reset button for 5 seconds.\n\n"
        "Then release and wait for the LED to turn green.",
        encoding="utf-8",
    )

    result = KnowledgeStore.ingest_file(str(f))
    assert result["chunks"] >= 1

    hits = KnowledgeStore.query("how do I reset")
    assert len(hits) >= 1
    assert any("reset" in h["text"].lower() for h in hits)


def test_knowledge_missing_file():
    with pytest.raises(KnowledgeError):
        KnowledgeStore.ingest_file("C:/does/not/exist.pdf")


def test_knowledge_unsupported_extension(tmp_path):
    f = tmp_path / "image.png"
    f.write_bytes(b"fake")
    with pytest.raises(KnowledgeError):
        KnowledgeStore.ingest_file(str(f))


def test_knowledge_query_empty():
    assert KnowledgeStore.query("") == []
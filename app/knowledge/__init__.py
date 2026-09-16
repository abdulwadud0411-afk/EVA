"""
EVA Knowledge / RAG System (Phase 13).

Local document ingestion + semantic retrieval.

Pipeline:
    Source → Extractor → Chunker → Embedder → VectorStore
                                              ↓
    Query → Embedder → VectorStore.search → top_k chunks

Public API:
    from app.knowledge.knowledge_store import KnowledgeStore
    KnowledgeStore.ingest_file("manual.pdf")
    KnowledgeStore.query("how do I reset?")
"""
from app.knowledge.knowledge_store import KnowledgeStore, KnowledgeError  # noqa: F401
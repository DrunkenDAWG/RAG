"""
app/services/ingestion.py
──────────────────────────
Document ingestion pipeline:
  1. Parse uploaded file (PDF / DOCX / plain-text)
  2. Chunk text with token-aware splitter
  3. Embed chunks via SentenceTransformer
  4. Upsert into ChromaDB collection

All public functions are async-safe; CPU-bound embedding is offloaded
to a thread-pool executor so the event loop remains unblocked.
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import uuid
from pathlib import Path
from typing import List, Optional

import chromadb
from chromadb import Collection
from sentence_transformers import SentenceTransformer

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Module-level singletons ───────────────────────────────────────────────────
_chroma_client: Optional[chromadb.PersistentClient] = None
_collection: Optional[Collection] = None
_embedder: Optional[SentenceTransformer] = None

CHUNK_SIZE_TOKENS = 512
CHUNK_OVERLAP_TOKENS = 64


# ── Initialisation ────────────────────────────────────────────────────────────

def init_chroma() -> None:
    """Initialise ChromaDB client & default collection (called from lifespan)."""
    global _chroma_client, _collection
    settings = get_settings()
    Path(settings.chroma_persist_dir).mkdir(parents=True, exist_ok=True)
    _chroma_client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    _collection = _chroma_client.get_or_create_collection(
        name=settings.chroma_collection_name,
        metadata={"hnsw:space": "cosine"},
    )
    logger.info(
        "chroma.ready",
        collection=settings.chroma_collection_name,
        path=settings.chroma_persist_dir,
    )


def get_collection() -> Collection:
    if _collection is None:
        raise RuntimeError("ChromaDB not initialised. Call init_chroma() first.")
    return _collection


def _get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        settings = get_settings()
        _embedder = SentenceTransformer(settings.embedding_model_name)
        logger.info("embedder.loaded", model=settings.embedding_model_name)
    return _embedder


# ── Text extraction ───────────────────────────────────────────────────────────

def _extract_text_pdf(data: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_text_docx(data: bytes) -> str:
    from docx import Document
    doc = Document(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs)


def _extract_text(filename: str, data: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return _extract_text_pdf(data)
    if ext in {".docx", ".doc"}:
        return _extract_text_docx(data)
    # Fallback: treat as UTF-8 plain text
    return data.decode("utf-8", errors="replace")


# ── Chunking ──────────────────────────────────────────────────────────────────

def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE_TOKENS, overlap: int = CHUNK_OVERLAP_TOKENS) -> List[str]:
    """
    Simple word-boundary chunker. For production consider tiktoken-based
    splitting for exact token counts.
    """
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(text)
    chunks: List[str] = []
    start = 0
    while start < len(tokens):
        end = start + chunk_size
        chunk_tokens = tokens[start:end]
        chunks.append(enc.decode(chunk_tokens))
        start += chunk_size - overlap
    return chunks


# ── Embedding ─────────────────────────────────────────────────────────────────

def _embed_sync(texts: List[str]) -> List[List[float]]:
    embedder = _get_embedder()
    vectors = embedder.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return vectors.tolist()


async def _embed_async(texts: List[str]) -> List[List[float]]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _embed_sync, texts)


# ── Public API ────────────────────────────────────────────────────────────────

async def ingest_document(
    filename: str,
    data: bytes,
    metadata: Optional[dict] = None,
) -> dict:
    """
    Parse, chunk, embed, and store a document.

    Returns a summary dict with document_id and chunk_count.
    """
    doc_id = _stable_doc_id(filename, data)
    collection = get_collection()

    # Check for duplicate (idempotent upsert)
    existing = collection.get(where={"document_id": doc_id}, limit=1)
    if existing["ids"]:
        logger.info("ingestion.duplicate_skipped", doc_id=doc_id, filename=filename)
        return {"document_id": doc_id, "chunk_count": 0, "status": "already_exists"}

    # Extract & chunk
    loop = asyncio.get_event_loop()
    text = await loop.run_in_executor(None, _extract_text, filename, data)
    chunks = _chunk_text(text)
    if not chunks:
        raise ValueError(f"No text could be extracted from '{filename}'.")

    logger.info("ingestion.chunked", doc_id=doc_id, chunk_count=len(chunks))

    # Embed (offloaded to thread-pool)
    embeddings = await _embed_async(chunks)

    # Build ChromaDB payload
    chunk_ids = [f"{doc_id}__chunk_{i}" for i in range(len(chunks))]
    meta_base = {
        "document_id": doc_id,
        "filename": filename,
        **(metadata or {}),
    }
    metas = [{**meta_base, "chunk_index": i} for i in range(len(chunks))]

    collection.upsert(
        ids=chunk_ids,
        embeddings=embeddings,
        documents=chunks,
        metadatas=metas,
    )

    logger.info("ingestion.complete", doc_id=doc_id, chunk_count=len(chunks))
    return {"document_id": doc_id, "chunk_count": len(chunks), "status": "ingested"}


async def delete_document(document_id: str) -> int:
    """Remove all chunks belonging to a document. Returns deleted chunk count."""
    collection = get_collection()
    existing = collection.get(where={"document_id": document_id})
    ids = existing["ids"]
    if ids:
        collection.delete(ids=ids)
    logger.info("ingestion.deleted", document_id=document_id, chunks_removed=len(ids))
    return len(ids)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _stable_doc_id(filename: str, data: bytes) -> str:
    digest = hashlib.sha256(data).hexdigest()[:24]
    safe_name = Path(filename).stem[:32]
    return f"{safe_name}_{digest}"

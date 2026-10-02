"""
app/services/ingestion.py
──────────────────────────
Phase 2 — Multi-tenant ingestion pipeline.

Design:
  • Each session gets its own ChromaDB collection scoped by session_id.
  • A per-session BM25Okapi index is kept in-memory and rebuilt on every
    ingest so that sparse retrieval always reflects the current corpus.
  • Chunking uses tiktoken (cl100k_base) at exactly 500 tokens with a
    50-token overlap — no word-boundary approximations.
  • Embedding and text-extraction are offloaded via run_in_threadpool so
    the FastAPI event loop is never blocked.
  • Metadata attached to every chunk:
      session_id      – tenant scope
      doc_id          – stable SHA-256 fingerprint of file content
      chunk_id        – "{doc_id}__chunk_{index}"
      corpus_version  – monotonically incremented per session on each ingest
"""
from __future__ import annotations

import hashlib
import io
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import chromadb
import tiktoken
from chromadb import Collection
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
CHUNK_SIZE_TOKENS: int = 500
CHUNK_OVERLAP_TOKENS: int = 50
_TIKTOKEN_ENCODING: str = "cl100k_base"

# ── Module-level singletons ───────────────────────────────────────────────────
_chroma_client: Optional[chromadb.PersistentClient] = None
_embedder: Optional[SentenceTransformer] = None

# Per-session state
# { session_id -> Collection }
_session_collections: Dict[str, Collection] = {}
# { session_id -> BM25Okapi }
_session_bm25: Dict[str, BM25Okapi] = {}
# { session_id -> corpus_version }
_session_versions: Dict[str, int] = {}
# { session_id -> tokenised corpus for BM25 rebuilds }
_session_corpus_tokens: Dict[str, List[List[str]]] = {}


# ── Initialisation ────────────────────────────────────────────────────────────

def init_chroma() -> None:
    """Create the persistent ChromaDB client. Called once from app lifespan."""
    global _chroma_client
    settings = get_settings()
    Path(settings.chroma_persist_dir).mkdir(parents=True, exist_ok=True)
    _chroma_client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    logger.info("chroma.client_ready", path=settings.chroma_persist_dir)


def _require_chroma() -> chromadb.PersistentClient:
    if _chroma_client is None:
        raise RuntimeError("ChromaDB not initialised — call init_chroma() first.")
    return _chroma_client


def _get_or_create_session_collection(session_id: str) -> Collection:
    """Return (or lazily create) the ChromaDB collection for a session."""
    if session_id not in _session_collections:
        client = _require_chroma()
        # Collection name must be 3-63 chars and match [a-zA-Z0-9_-]
        safe_name = f"s_{hashlib.sha256(session_id.encode()).hexdigest()[:32]}"
        col = client.get_or_create_collection(
            name=safe_name,
            metadata={"hnsw:space": "cosine", "session_id": session_id},
        )
        _session_collections[session_id] = col
        logger.info("chroma.session_collection_ready", session_id=session_id, name=safe_name)
    return _session_collections[session_id]


def get_session_collection(session_id: str) -> Collection:
    return _get_or_create_session_collection(session_id)


def get_session_bm25(session_id: str) -> Optional[BM25Okapi]:
    """Return the current BM25 index for a session, or None if empty."""
    return _session_bm25.get(session_id)


# ── Embedder ──────────────────────────────────────────────────────────────────

def _load_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        settings = get_settings()
        _embedder = SentenceTransformer(settings.embedding_model_name)
        logger.info("embedder.loaded", model=settings.embedding_model_name)
    return _embedder


def _embed_sync(texts: List[str]) -> List[List[float]]:
    embedder = _load_embedder()
    vectors = embedder.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return vectors.tolist()


# ── Text extraction ───────────────────────────────────────────────────────────

def _extract_text_pdf(data: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_text_docx(data: bytes) -> str:
    from docx import Document  # type: ignore[import]
    doc = Document(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs)


def _extract_text_sync(filename: str, data: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return _extract_text_pdf(data)
    if ext in {".docx", ".doc"}:
        return _extract_text_docx(data)
    return data.decode("utf-8", errors="replace")


# ── Chunking ──────────────────────────────────────────────────────────────────

def _chunk_text_sync(text: str) -> List[str]:
    """
    Token-exact chunker: 500-token windows with 50-token overlap.
    Uses tiktoken cl100k_base (GPT-4 / text-embedding-3 vocabulary).
    """
    enc = tiktoken.get_encoding(_TIKTOKEN_ENCODING)
    token_ids = enc.encode(text)
    chunks: List[str] = []
    start = 0
    step = CHUNK_SIZE_TOKENS - CHUNK_OVERLAP_TOKENS  # 450 tokens per step

    while start < len(token_ids):
        end = min(start + CHUNK_SIZE_TOKENS, len(token_ids))
        chunk_text = enc.decode(token_ids[start:end])
        if chunk_text.strip():
            chunks.append(chunk_text)
        if end == len(token_ids):
            break
        start += step

    return chunks


# ── BM25 management ───────────────────────────────────────────────────────────

def _tokenise_for_bm25(text: str) -> List[str]:
    return text.lower().split()


def _rebuild_bm25(session_id: str, new_chunks: List[str]) -> None:
    """
    Append new chunk tokens to the session corpus and rebuild BM25Okapi.
    Rebuilding is O(N) but N (total chunks per session) stays manageable.
    """
    existing = _session_corpus_tokens.get(session_id, [])
    new_tokenised = [_tokenise_for_bm25(c) for c in new_chunks]
    merged = existing + new_tokenised
    _session_corpus_tokens[session_id] = merged
    _session_bm25[session_id] = BM25Okapi(merged)
    logger.debug(
        "bm25.rebuilt",
        session_id=session_id,
        total_chunks=len(merged),
        new_chunks=len(new_tokenised),
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _stable_doc_id(filename: str, data: bytes) -> str:
    digest = hashlib.sha256(data).hexdigest()[:24]
    safe_name = Path(filename).stem[:32]
    return f"{safe_name}_{digest}"


def _next_corpus_version(session_id: str) -> int:
    version = _session_versions.get(session_id, 0) + 1
    _session_versions[session_id] = version
    return version


# ── Public API ────────────────────────────────────────────────────────────────

async def ingest_document(
    filename: str,
    data: bytes,
    session_id: str,
    extra_metadata: Optional[Dict] = None,
) -> Dict:
    """
    Parse, chunk, embed, and store a document scoped to *session_id*.

    Metadata stored per chunk:
        session_id      str   – tenant scope
        doc_id          str   – SHA-256 content fingerprint
        chunk_id        str   – "{doc_id}__chunk_{i}"
        corpus_version  int   – monotonically incremented per session

    Returns a summary dict: {doc_id, chunk_count, corpus_version, status}.
    """
    doc_id = _stable_doc_id(filename, data)
    collection = _get_or_create_session_collection(session_id)

    # Idempotency: skip if this exact document is already in this session
    existing = collection.get(where={"doc_id": doc_id}, limit=1)
    if existing["ids"]:
        logger.info(
            "ingestion.duplicate_skipped",
            session_id=session_id,
            doc_id=doc_id,
            filename=filename,
        )
        return {
            "doc_id": doc_id,
            "chunk_count": 0,
            "corpus_version": _session_versions.get(session_id, 0),
            "status": "already_exists",
        }

    # ── CPU-bound work in thread-pool ─────────────────────────────────────────
    text: str = await run_in_threadpool(_extract_text_sync, filename, data)
    chunks: List[str] = await run_in_threadpool(_chunk_text_sync, text)

    if not chunks:
        raise ValueError(f"No extractable text found in '{filename}'.")

    embeddings: List[List[float]] = await run_in_threadpool(_embed_sync, chunks)
    # ─────────────────────────────────────────────────────────────────────────

    corpus_version = _next_corpus_version(session_id)

    chunk_ids = [f"{doc_id}__chunk_{i}" for i in range(len(chunks))]
    metadatas = [
        {
            "session_id": session_id,
            "doc_id": doc_id,
            "chunk_id": f"{doc_id}__chunk_{i}",
            "corpus_version": corpus_version,
            "filename": filename,
            "chunk_index": i,
            **(extra_metadata or {}),
        }
        for i in range(len(chunks))
    ]

    collection.upsert(
        ids=chunk_ids,
        embeddings=embeddings,
        documents=chunks,
        metadatas=metadatas,
    )

    # Update in-memory BM25 index (sync, fast)
    _rebuild_bm25(session_id, chunks)

    logger.info(
        "ingestion.complete",
        session_id=session_id,
        doc_id=doc_id,
        filename=filename,
        chunk_count=len(chunks),
        corpus_version=corpus_version,
    )
    return {
        "doc_id": doc_id,
        "chunk_count": len(chunks),
        "corpus_version": corpus_version,
        "status": "ingested",
    }


async def delete_document(session_id: str, doc_id: str) -> int:
    """
    Remove all chunks for *doc_id* from *session_id*'s collection and
    rebuild the BM25 index without those chunks.

    Returns number of chunks removed.
    """
    collection = _get_or_create_session_collection(session_id)
    result = collection.get(where={"doc_id": doc_id})
    ids = result["ids"]

    if not ids:
        return 0

    collection.delete(ids=ids)

    # Rebuild BM25 from the remaining corpus by re-querying ChromaDB
    remaining = collection.get(include=["documents"])
    remaining_docs: List[str] = remaining.get("documents") or []
    _session_corpus_tokens[session_id] = []  # reset
    if remaining_docs:
        _rebuild_bm25(session_id, remaining_docs)
    else:
        _session_bm25.pop(session_id, None)

    logger.info(
        "ingestion.deleted",
        session_id=session_id,
        doc_id=doc_id,
        chunks_removed=len(ids),
    )
    return len(ids)

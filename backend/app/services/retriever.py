"""
app/services/retriever.py
──────────────────────────
Phase 2 — Session-scoped hybrid search with true async concurrency.

Pipeline per query:
  1. Dense path  — embed query → ChromaDB ANN (cosine, top_k results)
                   scoped to the caller's session collection.
  2. Sparse path — BM25Okapi.get_scores() against the session's in-memory
                   index; returns top_k results by BM25 score.
  Both paths are launched concurrently with asyncio.gather().

  3. RRF fusion  — Reciprocal Rank Fusion (k=60) merges both ranked lists
                   into a single ordering.

Public surface:
    async def hybrid_search(
        query: str,
        session_id: str,
        top_k: int = 20,
    ) -> list[Document]
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from starlette.concurrency import run_in_threadpool

from app.core.logging import get_logger
from app.services.ingestion import (
    _embed_sync,
    _tokenise_for_bm25,
    get_session_bm25,
    get_session_collection,
)

logger = get_logger(__name__)

RRF_K: int = 60  # standard RRF constant


# ── Domain model ──────────────────────────────────────────────────────────────

@dataclass
class Document:
    """Unified retrieval result returned by hybrid_search and reranker."""
    chunk_id: str
    doc_id: str
    session_id: str
    filename: str
    text: str
    chunk_index: int
    score: float                         # RRF-fused score (pre-rerank) or cross-encoder score (post-rerank)
    corpus_version: int = 0
    metadata: Dict = field(default_factory=dict)


# ── Dense path ────────────────────────────────────────────────────────────────

def _chroma_query_sync(
    session_id: str,
    query_embedding: List[List[float]],
    top_k: int,
) -> List[Document]:
    """Blocking ChromaDB ANN query — runs in threadpool."""
    collection = get_session_collection(session_id)
    count = collection.count()
    if count == 0:
        return []

    n = min(top_k, count)
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=n,
        include=["documents", "metadatas", "distances"],
    )

    docs: List[Document] = []
    if not results["ids"] or not results["ids"][0]:
        return docs

    for cid, text, meta, dist in zip(
        results["ids"][0],
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        # ChromaDB cosine distance ∈ [0, 2]; similarity = 1 - distance
        score = 1.0 - float(dist)
        docs.append(
            Document(
                chunk_id=cid,
                doc_id=meta.get("doc_id", ""),
                session_id=meta.get("session_id", session_id),
                filename=meta.get("filename", ""),
                text=text,
                chunk_index=int(meta.get("chunk_index", 0)),
                corpus_version=int(meta.get("corpus_version", 0)),
                score=score,
                metadata=meta,
            )
        )
    return docs


async def _dense_search(
    query: str,
    session_id: str,
    top_k: int,
) -> List[Document]:
    """Async wrapper: embed query + ANN query, both offloaded to threadpool."""
    query_embedding: List[List[float]] = await run_in_threadpool(_embed_sync, [query])
    return await run_in_threadpool(_chroma_query_sync, session_id, query_embedding, top_k)


# ── Sparse path ───────────────────────────────────────────────────────────────

def _bm25_search_sync(
    query: str,
    session_id: str,
    top_k: int,
) -> List[Document]:
    """
    Blocking BM25 search against the session's in-memory index.
    Returns an ordered list of Documents ranked by BM25 score.
    Runs in threadpool.
    """
    bm25 = get_session_bm25(session_id)
    if bm25 is None:
        return []

    query_tokens = _tokenise_for_bm25(query)
    scores = bm25.get_scores(query_tokens)

    # bm25 corpus is parallel to the stored chunks —
    # we need the actual text to build Document objects.
    # Fetch all docs from the collection to align with corpus index.
    collection = get_session_collection(session_id)
    stored = collection.get(include=["documents", "metadatas"])

    if not stored["ids"]:
        return []

    # Sort by BM25 score descending, take top_k
    ranked_indices = sorted(
        range(len(scores)), key=lambda i: scores[i], reverse=True
    )[:top_k]

    docs: List[Document] = []
    for idx in ranked_indices:
        if idx >= len(stored["ids"]):
            continue
        meta = stored["metadatas"][idx]
        docs.append(
            Document(
                chunk_id=stored["ids"][idx],
                doc_id=meta.get("doc_id", ""),
                session_id=meta.get("session_id", session_id),
                filename=meta.get("filename", ""),
                text=stored["documents"][idx],
                chunk_index=int(meta.get("chunk_index", 0)),
                corpus_version=int(meta.get("corpus_version", 0)),
                score=float(scores[idx]),
                metadata=meta,
            )
        )
    return docs


async def _sparse_search(
    query: str,
    session_id: str,
    top_k: int,
) -> List[Document]:
    """Async wrapper for BM25 search, offloaded to threadpool."""
    return await run_in_threadpool(_bm25_search_sync, query, session_id, top_k)


# ── Reciprocal Rank Fusion ────────────────────────────────────────────────────

def _rrf_fuse(
    dense_ranked: List[Document],
    sparse_ranked: List[Document],
    top_k: int,
) -> List[Document]:
    """
    Merge two ranked lists using Reciprocal Rank Fusion.

    RRF score(d) = Σ  1 / (k + rank_i(d))    k = 60
                  lists

    Returns up to top_k documents sorted by descending RRF score.
    """
    rrf_scores: Dict[str, float] = {}
    doc_map: Dict[str, Document] = {}

    for rank, doc in enumerate(dense_ranked, start=1):
        rrf_scores[doc.chunk_id] = rrf_scores.get(doc.chunk_id, 0.0) + 1.0 / (RRF_K + rank)
        doc_map[doc.chunk_id] = doc

    for rank, doc in enumerate(sparse_ranked, start=1):
        rrf_scores[doc.chunk_id] = rrf_scores.get(doc.chunk_id, 0.0) + 1.0 / (RRF_K + rank)
        doc_map.setdefault(doc.chunk_id, doc)

    top = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    return [
        Document(**{**doc_map[cid].__dict__, "score": rrf_score})
        for cid, rrf_score in top
    ]


# ── Public API ────────────────────────────────────────────────────────────────

async def hybrid_search(
    query: str,
    session_id: str,
    top_k: int = 20,
) -> List[Document]:
    """
    Concurrent hybrid search for a specific session.

    Dense (ChromaDB ANN) and sparse (BM25) retrieval are launched
    concurrently via asyncio.gather; their results are fused with RRF (k=60).

    Args:
        query:      Natural-language search query.
        session_id: Tenant identifier; restricts search to that session's data.
        top_k:      Number of candidates to fetch from each retrieval path
                    (and the maximum size of the fused result list).

    Returns:
        Up to top_k Documents sorted by descending RRF score.
    """
    dense_results, sparse_results = await asyncio.gather(
        _dense_search(query, session_id, top_k),
        _sparse_search(query, session_id, top_k),
    )

    if not dense_results and not sparse_results:
        logger.warning(
            "retriever.empty",
            session_id=session_id,
            query_preview=query[:80],
        )
        return []

    fused = _rrf_fuse(dense_results, sparse_results, top_k=top_k)

    logger.info(
        "retriever.hybrid_search_done",
        session_id=session_id,
        query_preview=query[:60],
        dense_count=len(dense_results),
        sparse_count=len(sparse_results),
        fused_count=len(fused),
    )
    return fused

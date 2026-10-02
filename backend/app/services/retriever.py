"""
app/services/retriever.py
──────────────────────────
Hybrid retrieval: dense (ChromaDB cosine similarity) + sparse (BM25).
Results are merged using Reciprocal Rank Fusion (RRF).
"""
from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from rank_bm25 import BM25Okapi

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.ingestion import _embed_async, get_collection

logger = get_logger(__name__)

RRF_K = 60  # standard RRF constant


@dataclass
class RetrievedChunk:
    chunk_id: str
    document_id: str
    filename: str
    text: str
    chunk_index: int
    score: float  # RRF-fused score
    metadata: Dict = field(default_factory=dict)


# ── Dense retrieval ───────────────────────────────────────────────────────────

async def _dense_retrieve(query: str, top_k: int) -> List[RetrievedChunk]:
    settings = get_settings()
    collection = get_collection()

    query_embedding = await _embed_async([query])

    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(
        None,
        lambda: collection.query(
            query_embeddings=query_embedding,
            n_results=min(top_k, collection.count() or 1),
            include=["documents", "metadatas", "distances"],
        ),
    )

    chunks: List[RetrievedChunk] = []
    if not results["ids"] or not results["ids"][0]:
        return chunks

    for cid, doc, meta, dist in zip(
        results["ids"][0],
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        # ChromaDB cosine distance → similarity
        score = 1.0 - float(dist)
        chunks.append(
            RetrievedChunk(
                chunk_id=cid,
                document_id=meta.get("document_id", ""),
                filename=meta.get("filename", ""),
                text=doc,
                chunk_index=int(meta.get("chunk_index", 0)),
                score=score,
                metadata=meta,
            )
        )
    return chunks


# ── Sparse retrieval (BM25) ───────────────────────────────────────────────────

def _tokenise(text: str) -> List[str]:
    return text.lower().split()


async def _sparse_retrieve(query: str, candidates: List[RetrievedChunk]) -> List[RetrievedChunk]:
    """Re-score the dense candidate pool with BM25 and return re-ranked list."""
    if not candidates:
        return []

    corpus = [_tokenise(c.text) for c in candidates]
    bm25 = BM25Okapi(corpus)
    scores = bm25.get_scores(_tokenise(query))

    ranked = sorted(
        zip(candidates, scores), key=lambda x: x[1], reverse=True
    )
    # Return new list with BM25 scores set
    result = []
    for chunk, sc in ranked:
        result.append(RetrievedChunk(**{**chunk.__dict__, "score": float(sc)}))
    return result


# ── Reciprocal Rank Fusion ────────────────────────────────────────────────────

def _rrf_merge(
    dense_ranked: List[RetrievedChunk],
    sparse_ranked: List[RetrievedChunk],
    top_n: int,
) -> List[RetrievedChunk]:
    rrf_scores: Dict[str, float] = {}
    chunk_map: Dict[str, RetrievedChunk] = {}

    for rank, chunk in enumerate(dense_ranked, start=1):
        rrf_scores[chunk.chunk_id] = rrf_scores.get(chunk.chunk_id, 0.0) + 1 / (RRF_K + rank)
        chunk_map[chunk.chunk_id] = chunk

    for rank, chunk in enumerate(sparse_ranked, start=1):
        rrf_scores[chunk.chunk_id] = rrf_scores.get(chunk.chunk_id, 0.0) + 1 / (RRF_K + rank)
        chunk_map[chunk.chunk_id] = chunk

    merged = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:top_n]
    return [
        RetrievedChunk(**{**chunk_map[cid].__dict__, "score": sc})
        for cid, sc in merged
    ]


# ── Public API ────────────────────────────────────────────────────────────────

async def hybrid_retrieve(
    query: str,
    top_k: Optional[int] = None,
    top_n: Optional[int] = None,
    document_ids: Optional[List[str]] = None,
) -> List[RetrievedChunk]:
    """
    Perform hybrid dense + sparse retrieval with RRF fusion.

    Args:
        query:        The user's natural-language query.
        top_k:        Number of candidates fetched from ChromaDB (dense stage).
        top_n:        Final number of chunks after fusion (pre-rerank).
        document_ids: Optional allowlist to restrict search to specific docs.

    Returns:
        List of RetrievedChunk ordered by descending RRF score.
    """
    settings = get_settings()
    top_k = top_k or settings.retriever_top_k
    top_n = top_n or settings.reranker_top_n

    dense_results = await _dense_retrieve(query, top_k)

    if not dense_results:
        logger.warning("retriever.empty", query=query[:80])
        return []

    # Filter by document_ids if provided
    if document_ids:
        allowed = set(document_ids)
        dense_results = [c for c in dense_results if c.document_id in allowed]

    sparse_results = await _sparse_retrieve(query, dense_results)
    fused = _rrf_merge(dense_results, sparse_results, top_n=top_k)

    logger.info(
        "retriever.done",
        query_preview=query[:60],
        dense_count=len(dense_results),
        fused_count=len(fused),
    )
    return fused[:top_n]

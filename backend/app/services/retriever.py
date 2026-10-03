"""
app/services/retriever.py
--------------------------
Hybrid search with BGE query prefix, HyDE dense path, and parent expansion.

Pipeline per query:
  1. Receive (search_query, hyde_passage) from llm.rewrite_query_and_hyde().
  2. Dense path:  embed hyde_passage with BGE query prefix -> ChromaDB ANN.
  3. Sparse path: BM25 search using search_query (exact keyword matching).
  Both launched concurrently via asyncio.gather().
  4. RRF fusion of child chunk results.
  5. Cross-encoder reranks child chunks (short, within 512-token limit).
  6. Parent expansion: deduplicate parent_ids of top-N children, fetch full
     parent texts from Redis, build expanded Document list for LLM generation.

Public surface:
    async def hybrid_search(
        search_query: str,
        hyde_passage: str,
        session_id: str,
        top_k: int = 20,
    ) -> list[Document]

    async def expand_to_parents(
        child_docs: list[Document],
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
    embed_query_sync,
    get_session_bm25,
    get_session_collection,
)

logger = get_logger(__name__)

RRF_K: int = 60  # standard RRF constant


# -- Domain model -------------------------------------------------------------

@dataclass
class Document:
    """Unified retrieval result returned by hybrid_search and reranker."""
    chunk_id: str
    doc_id: str
    session_id: str
    filename: str
    text: str
    chunk_index: int
    score: float          # RRF score (pre-rerank) or cross-encoder score (post-rerank)
    corpus_version: int = 0
    parent_id: str = ""   # Redis key suffix for parent text lookup
    metadata: Dict = field(default_factory=dict)

    @property
    def page(self) -> Optional[int]:
        """First 1-based PDF page of the chunk, or None if unknown."""
        page = self.metadata.get("page")
        return int(page) if page is not None else None

    @property
    def page_end(self) -> Optional[int]:
        """Last 1-based PDF page of the chunk (== page unless it spans pages)."""
        page_end = self.metadata.get("page_end", self.metadata.get("page"))
        return int(page_end) if page_end is not None else None


def to_sources(docs: List[Document]) -> List[Dict]:
    """
    User-facing citation payload, one entry per context passage (index i
    matches the LLM's [i+1] marker). Chunk ids and retrieval scores are
    deliberately excluded — they stay internal (logs / Document objects).
    """
    return [
        {
            "doc_id": doc.doc_id,
            "filename": doc.filename,
            "page": doc.page,
            "page_end": doc.page_end,
        }
        for doc in docs
    ]


# -- Dense path ---------------------------------------------------------------

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
        score = 1.0 - float(dist)  # cosine distance -> similarity
        docs.append(Document(
            chunk_id=cid,
            doc_id=meta.get("doc_id", ""),
            session_id=meta.get("session_id", session_id),
            filename=meta.get("filename", ""),
            text=text,
            chunk_index=int(meta.get("chunk_index", 0)),
            corpus_version=int(meta.get("corpus_version", 0)),
            parent_id=meta.get("parent_id", ""),
            score=score,
            metadata=meta,
        ))
    return docs


async def _dense_search(
    hyde_passage: str,
    session_id: str,
    top_k: int,
) -> List[Document]:
    """
    Embed the HyDE passage with the BGE query prefix, then run ANN search.
    CRITICAL: embed_query_sync() prepends the required BGE instruction prefix.
    """
    query_embedding: List[List[float]] = await run_in_threadpool(
        embed_query_sync, hyde_passage
    )
    return await run_in_threadpool(_chroma_query_sync, session_id, query_embedding, top_k)


# -- Sparse path --------------------------------------------------------------

def _bm25_search_sync(
    search_query: str,
    session_id: str,
    top_k: int,
) -> List[Document]:
    """
    Blocking BM25 search using the keyword search_query.
    Runs in threadpool.
    """
    bm25 = get_session_bm25(session_id)
    if bm25 is None:
        return []

    query_tokens = _tokenise_for_bm25(search_query)
    scores = bm25.get_scores(query_tokens)

    collection = get_session_collection(session_id)
    stored = collection.get(include=["documents", "metadatas"])

    if not stored["ids"]:
        return []

    ranked_indices = sorted(
        range(len(scores)), key=lambda i: scores[i], reverse=True
    )[:top_k]

    docs: List[Document] = []
    for idx in ranked_indices:
        if idx >= len(stored["ids"]):
            continue
        meta = stored["metadatas"][idx]
        docs.append(Document(
            chunk_id=stored["ids"][idx],
            doc_id=meta.get("doc_id", ""),
            session_id=meta.get("session_id", session_id),
            filename=meta.get("filename", ""),
            text=stored["documents"][idx],
            chunk_index=int(meta.get("chunk_index", 0)),
            corpus_version=int(meta.get("corpus_version", 0)),
            parent_id=meta.get("parent_id", ""),
            score=float(scores[idx]),
            metadata=meta,
        ))
    return docs


async def _sparse_search(
    search_query: str,
    session_id: str,
    top_k: int,
) -> List[Document]:
    """Async wrapper for BM25 search, offloaded to threadpool."""
    return await run_in_threadpool(_bm25_search_sync, search_query, session_id, top_k)


# -- Reciprocal Rank Fusion ---------------------------------------------------

def _rrf_fuse(
    dense_ranked: List[Document],
    sparse_ranked: List[Document],
    top_k: int,
) -> List[Document]:
    """
    Merge two ranked lists using Reciprocal Rank Fusion (k=60).
    RRF score(d) = sum(1 / (RRF_K + rank_i(d))) over all lists.
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


# -- Parent expansion ---------------------------------------------------------

async def expand_to_parents(child_docs: List[Document]) -> List[Document]:
    """
    After reranking, deduplicate parent_ids from top child chunks and fetch
    the full Parent texts from Redis.

    Returns a list of Document objects where .text is the full parent passage
    (800 tokens), ordered by the best child score per parent.
    Falls back to child text if Redis lookup fails.
    """
    try:
        from app.core.redis import get_redis_client
        client = get_redis_client()
    except Exception as exc:
        logger.warning("retriever.redis_unavailable", error=str(exc))
        return child_docs  # graceful degradation

    # Collect unique parent_ids preserving order of best child score
    seen: Dict[str, Document] = {}
    for doc in child_docs:
        pid = doc.parent_id
        if not pid:
            pid = doc.chunk_id  # fallback for docs without parent_id
        if pid not in seen or doc.score > seen[pid].score:
            seen[pid] = doc

    expanded: List[Document] = []
    for pid, representative_child in seen.items():
        try:
            parent_text = await client.get(f"parent:{pid}")
        except Exception as exc:
            logger.warning("retriever.parent_fetch_failed", parent_id=pid, error=str(exc))
            parent_text = None

        expanded.append(Document(
            chunk_id=pid,
            doc_id=representative_child.doc_id,
            session_id=representative_child.session_id,
            filename=representative_child.filename,
            text=parent_text if parent_text else representative_child.text,
            chunk_index=representative_child.chunk_index,
            corpus_version=representative_child.corpus_version,
            parent_id=pid,
            score=representative_child.score,
            metadata=representative_child.metadata,
        ))

    logger.info("retriever.parent_expansion_done",
                child_count=len(child_docs), parent_count=len(expanded))
    return expanded


# -- Public API ---------------------------------------------------------------

async def hybrid_search(
    session_id: str,
    top_k: int = 20,
    query: str = "",           # kept for backward compat (used as search_query)
    search_query: str = "",    # BM25 keyword query from rewrite_query_and_hyde
    hyde_passage: str = "",    # hypothetical passage for dense embedding
) -> List[Document]:
    """
    Concurrent hybrid search: dense (HyDE + BGE) + sparse (BM25) + RRF fusion.

    Callers should pass search_query and hyde_passage explicitly.
    Falls back to query for both if the new kwargs are empty (backward compat).

    Args:
        session_id:    Tenant identifier.
        top_k:         Candidates per retrieval path.
        query:         Legacy fallback query string.
        search_query:  Keyword query for BM25.
        hyde_passage:  Hypothetical passage for dense embedding.

    Returns:
        Up to top_k child Documents sorted by descending RRF score.
    """
    _search_q = search_query or query
    _hyde_p = hyde_passage or query

    dense_results, sparse_results = await asyncio.gather(
        _dense_search(_hyde_p, session_id, top_k),
        _sparse_search(_search_q, session_id, top_k),
    )

    if not dense_results and not sparse_results:
        logger.warning("retriever.empty", session_id=session_id,
                       query_preview=_search_q[:80])
        return []

    fused = _rrf_fuse(dense_results, sparse_results, top_k=top_k)

    logger.info("retriever.hybrid_search_done", session_id=session_id,
                query_preview=_search_q[:60], dense_count=len(dense_results),
                sparse_count=len(sparse_results), fused_count=len(fused))
    return fused

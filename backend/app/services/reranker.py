"""
app/services/reranker.py
─────────────────────────
Cross-encoder reranker that scores each (query, chunk) pair and returns the
top-N chunks ordered by relevance.

Uses a lightweight cross-encoder from sentence-transformers so no additional
API calls are needed. Scoring is offloaded to a thread-pool executor.
"""
from __future__ import annotations

import asyncio
from typing import List, Optional

from sentence_transformers import CrossEncoder

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.retriever import RetrievedChunk

logger = get_logger(__name__)

# Default cross-encoder model — small and fast, works offline
_CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

_cross_encoder: Optional[CrossEncoder] = None


def _get_cross_encoder() -> CrossEncoder:
    global _cross_encoder
    if _cross_encoder is None:
        logger.info("reranker.loading_model", model=_CROSS_ENCODER_MODEL)
        _cross_encoder = CrossEncoder(_CROSS_ENCODER_MODEL, max_length=512)
        logger.info("reranker.model_ready", model=_CROSS_ENCODER_MODEL)
    return _cross_encoder


def _score_sync(query: str, texts: List[str]) -> List[float]:
    encoder = _get_cross_encoder()
    pairs = [(query, t) for t in texts]
    scores = encoder.predict(pairs, show_progress_bar=False)
    return scores.tolist()


async def rerank(
    query: str,
    candidates: List[RetrievedChunk],
    top_n: Optional[int] = None,
) -> List[RetrievedChunk]:
    """
    Rerank candidates using a cross-encoder and return the top_n results.

    Args:
        query:      The user query.
        candidates: Chunks from the hybrid retriever.
        top_n:      Maximum chunks to return (defaults to settings.reranker_top_n).

    Returns:
        Sorted list of RetrievedChunk with updated cross-encoder scores.
    """
    settings = get_settings()
    top_n = top_n or settings.reranker_top_n

    if not candidates:
        return []

    texts = [c.text for c in candidates]
    loop = asyncio.get_event_loop()
    scores = await loop.run_in_executor(None, _score_sync, query, texts)

    scored = sorted(
        zip(candidates, scores),
        key=lambda x: x[1],
        reverse=True,
    )

    results = []
    for chunk, sc in scored[:top_n]:
        reranked = RetrievedChunk(**{**chunk.__dict__, "score": float(sc)})
        results.append(reranked)

    logger.info(
        "reranker.done",
        input_count=len(candidates),
        output_count=len(results),
        top_score=results[0].score if results else None,
    )
    return results

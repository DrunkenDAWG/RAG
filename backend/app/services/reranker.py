"""
app/services/reranker.py
─────────────────────────
Phase 2 — Non-blocking cross-encoder reranking.

Design:
  • The CrossEncoder model (cross-encoder/ms-marco-MiniLM-L-6-v2) is loaded
    ONCE at module import time via warm_up_reranker(), called from the app
    lifespan, so cold-start latency never leaks into request handling.

  • The synchronous model.predict() call — which runs PyTorch inference on
    the CPU — is wrapped in starlette.concurrency.run_in_threadpool.
    This means FastAPI's asyncio event loop is NEVER blocked: other requests
    continue to be served while the reranker works in a background thread.

  • Return type is List[Document] (same as hybrid_search), with the `.score`
    field replaced by the cross-encoder logit so downstream code stays uniform.
"""
import os
import tempfile
from typing import List, Optional

_cache_dir = os.path.join(tempfile.gettempdir(), "rag_hf_cache")
os.makedirs(_cache_dir, exist_ok=True)
os.environ["HF_HOME"] = _cache_dir
os.environ["SENTENCE_TRANSFORMERS_HOME"] = _cache_dir
os.environ["TRANSFORMERS_CACHE"] = _cache_dir
os.environ["TORCH_HOME"] = _cache_dir

from sentence_transformers import CrossEncoder
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.retriever import Document

logger = get_logger(__name__)

# ── Model identifier ──────────────────────────────────────────────────────────
_CROSS_ENCODER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# Module-level singleton — populated by warm_up_reranker()
_cross_encoder: Optional[CrossEncoder] = None


# ── Lifecycle ─────────────────────────────────────────────────────────────────

def warm_up_reranker() -> None:
    """
    Load and cache the CrossEncoder model.
    Call this once from the FastAPI lifespan so the model is hot before
    the first real request arrives. Subsequent calls are no-ops.
    """
    global _cross_encoder
    if _cross_encoder is not None:
        return
    logger.info("reranker.loading", model=_CROSS_ENCODER_MODEL)
    _cross_encoder = CrossEncoder(
        _CROSS_ENCODER_MODEL,
        max_length=512,
    )
    # Run a dummy prediction to JIT-compile torch ops and warm up CPU cache
    _cross_encoder.predict([("warmup query", "warmup passage")])
    logger.info("reranker.ready", model=_CROSS_ENCODER_MODEL)


def _require_model() -> CrossEncoder:
    if _cross_encoder is None:
        # Lazy load as fallback if warm_up_reranker() was skipped
        warm_up_reranker()
    return _cross_encoder  # type: ignore[return-value]


# ── Synchronous scoring (runs in thread-pool) ─────────────────────────────────

def _score_pairs_sync(query: str, texts: List[str]) -> List[float]:
    """
    Build (query, passage) pairs and run CrossEncoder.predict().
    This function is CPU-bound and MUST NOT be awaited directly —
    it is always called via run_in_threadpool.
    """
    model = _require_model()
    pairs = [(query, text) for text in texts]
    scores = model.predict(pairs, show_progress_bar=False)
    return scores.tolist()


# ── Public API ────────────────────────────────────────────────────────────────

async def rerank(
    query: str,
    docs: List[Document],
    top_n: int = 5,
) -> List[Document]:
    """
    Rerank *docs* for *query* using the cross-encoder; return top *top_n*.

    The CPU-intensive model.predict() call runs inside run_in_threadpool,
    ensuring FastAPI's event loop is never blocked.

    Args:
        query:  The user's natural-language query.
        docs:   Candidate documents from hybrid_search (RRF-fused).
        top_n:  Maximum number of documents to return (default 5).

    Returns:
        List of Documents sorted by descending cross-encoder score,
        truncated to top_n. The .score field holds the cross-encoder logit.
    """
    if not docs:
        return []

    texts = [doc.text for doc in docs]

    # ── CRITICAL: offload blocking inference to threadpool ────────────────────
    scores: List[float] = await run_in_threadpool(_score_pairs_sync, query, texts)
    # ─────────────────────────────────────────────────────────────────────────

    scored_pairs = sorted(
        zip(docs, scores),
        key=lambda pair: pair[1],
        reverse=True,
    )

    results: List[Document] = []
    for doc, score in scored_pairs[:top_n]:
        results.append(
            Document(
                chunk_id=doc.chunk_id,
                doc_id=doc.doc_id,
                session_id=doc.session_id,
                filename=doc.filename,
                text=doc.text,
                chunk_index=doc.chunk_index,
                corpus_version=doc.corpus_version,
                score=float(score),
                metadata=doc.metadata,
            )
        )

    logger.info(
        "reranker.done",
        input_count=len(docs),
        output_count=len(results),
        top_score=round(results[0].score, 4) if results else None,
        bottom_score=round(results[-1].score, 4) if results else None,
    )
    return results

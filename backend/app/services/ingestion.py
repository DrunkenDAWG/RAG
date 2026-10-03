"""
app/services/ingestion.py
--------------------------
Parent-Child Semantic Chunking pipeline.

Design:
  - Each session gets its own ChromaDB collection scoped by session_id.
  - Documents split into Parent chunks (~800 tokens) on structural boundaries
    (double-newlines / Markdown headings), then each Parent into Child chunks
    (max 400 tokens, 50-token overlap).
  - Only Child chunks stored in ChromaDB (small = precise vector match).
  - Full Parent texts stored in Redis as parent:{pid} â€” never in ChromaDB
    metadata to avoid HNSW payload bloat.
  - BM25 built from Child texts for keyword-level granularity.
  - Images embedded in PDFs (figures, diagrams, scans) and standalone image
    uploads are converted to text via app.services.vision (Gemini) before
    chunking; PDF figure text is appended to its own page.
  - AutoTokenizer from BAAI/bge-small-en-v1.5 for accurate token counting,
    consistent with the embedding model vocabulary.
  - Metadata per Child in ChromaDB:
      session_id, doc_id, parent_id, chunk_id, chunk_index, corpus_version,
      filename, page / page_end (1-based PDF page span; PDFs only).
"""
from __future__ import annotations

import bisect
import hashlib
import io
import os
import re
import tempfile
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_cache_dir = os.environ.get("HF_HOME", "")
if not _cache_dir or _cache_dir.startswith("/nonexistent"):
    _cache_dir = os.path.join(tempfile.gettempdir(), "rag_hf_cache")
    os.makedirs(_cache_dir, exist_ok=True)
    os.environ["HF_HOME"] = _cache_dir
    os.environ["SENTENCE_TRANSFORMERS_HOME"] = _cache_dir
    os.environ["TRANSFORMERS_CACHE"] = _cache_dir
    os.environ["TORCH_HOME"] = _cache_dir

import chromadb
from chromadb.api.models.Collection import Collection
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer
from starlette.concurrency import run_in_threadpool
from transformers import AutoTokenizer  # type: ignore[import-untyped]

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.vision import (
    describe_image,
    describe_images,
    prepare_image,
    vision_available,
)

logger = get_logger(__name__)

# -- Chunking constants -------------------------------------------------------
_TOKENIZER_NAME: str = "BAAI/bge-small-en-v1.5"
PARENT_MAX_TOKENS: int = 800
CHILD_MAX_TOKENS: int = 400
CHILD_OVERLAP_TOKENS: int = 50

# -- Module-level singletons --------------------------------------------------
_chroma_client: Optional[chromadb.PersistentClient] = None
_embedder: Optional[SentenceTransformer] = None
_tokenizer = None  # AutoTokenizer instance, type-ignored for brevity

# Per-session state
_session_collections: Dict[str, Collection] = {}
_session_bm25: Dict[str, BM25Okapi] = {}
_session_versions: Dict[str, int] = {}
_session_corpus_tokens: Dict[str, List[List[str]]] = {}


# -- Initialisation -----------------------------------------------------------

def init_chroma() -> None:
    """Create the persistent ChromaDB client. Called once from app lifespan."""
    global _chroma_client
    settings = get_settings()
    Path(settings.chroma_persist_dir).mkdir(parents=True, exist_ok=True)
    _chroma_client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    logger.info("chroma.client_ready", path=settings.chroma_persist_dir)


def _require_chroma() -> chromadb.PersistentClient:
    if _chroma_client is None:
        raise RuntimeError("ChromaDB not initialised â€” call init_chroma() first.")
    return _chroma_client


def _get_or_create_session_collection(session_id: str) -> Collection:
    """Return (or lazily create) the ChromaDB collection for a session."""
    if session_id not in _session_collections:
        client = _require_chroma()
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


# -- Tokenizer ----------------------------------------------------------------

def _load_tokenizer():
    global _tokenizer
    if _tokenizer is None:
        _tokenizer = AutoTokenizer.from_pretrained(_TOKENIZER_NAME)
        logger.info("tokenizer.loaded", model=_TOKENIZER_NAME)
    return _tokenizer


def _encode_text(text: str) -> List[int]:
    tok = _load_tokenizer()
    return tok.encode(text, add_special_tokens=False)


def _decode_token_window(token_ids: List[int]) -> str:
    tok = _load_tokenizer()
    return tok.decode(token_ids, skip_special_tokens=True)


# -- Embedder -----------------------------------------------------------------

def _load_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        settings = get_settings()
        _embedder = SentenceTransformer(settings.embedding_model_name)
        logger.info("embedder.loaded", model=settings.embedding_model_name)
    return _embedder


def _embed_sync(texts: List[str]) -> List[List[float]]:
    """Embed document texts â€” no prefix (BGE: NEVER prefix documents)."""
    embedder = _load_embedder()
    vectors = embedder.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return vectors.tolist()


def embed_query_sync(text: str) -> List[List[float]]:
    """
    Embed a query with the mandatory BGE instruction prefix.
    CRITICAL: prefix queries only, NEVER documents.
    """
    prefixed = f"Represent this sentence for searching relevant passages: {text}"
    return _embed_sync([prefixed])


# -- Text extraction ----------------------------------------------------------

IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp"})

# (0-based page index, prepared JPEG bytes)
PdfImage = Tuple[int, bytes]


def _collect_pdf_images(reader) -> List[PdfImage]:
    """
    Pull embedded raster images (figures, diagrams, scanned pages) from a PDF,
    skipping tiny/undecodable ones and repeats (e.g. a logo on every page).
    Capped at settings.vision_max_images_per_doc.
    """
    limit = get_settings().vision_max_images_per_doc
    seen: set = set()
    images: List[PdfImage] = []
    for p_idx, page in enumerate(reader.pages):
        try:
            page_images = list(page.images)
        except Exception as exc:
            logger.debug("ingestion.pdf_page_images_failed", page=p_idx + 1, error=str(exc))
            continue
        for img in page_images:
            if len(images) >= limit:
                logger.info("ingestion.pdf_image_limit_reached", limit=limit)
                return images
            try:
                raw = img.data
            except Exception:
                continue
            digest = hashlib.sha1(raw).hexdigest()
            if digest in seen:
                continue
            seen.add(digest)
            prepared = prepare_image(raw)
            if prepared is not None:
                images.append((p_idx, prepared))
    return images


def _read_pdf_sync(
    data: bytes,
    collect_images: bool,
) -> Tuple[Optional[List[str]], List[PdfImage]]:
    """Returns (page_texts, images); page_texts is None if parsing failed."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        page_texts = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:
        logger.warning("ingestion.pdf_extraction_failed", error=str(exc))
        return None, []
    images = _collect_pdf_images(reader) if collect_images else []
    return page_texts, images


def _join_pages(page_texts: List[str]) -> Tuple[str, List[int]]:
    """
    Returns (text, page_starts) where page_starts[i] is the char offset in
    text at which page i+1 begins.
    """
    page_starts: List[int] = []
    offset = 0
    for page_text in page_texts:
        page_starts.append(offset)
        offset += len(page_text) + 1  # +1 for the "\n" joiner
    return "\n".join(page_texts), page_starts


def _extract_text_pdf(data: bytes) -> Tuple[str, Optional[List[int]]]:
    """Text layer only. page_starts is None if parsing failed."""
    page_texts, _ = _read_pdf_sync(data, collect_images=False)
    if page_texts is None:
        return data.decode("utf-8", errors="replace"), None
    return _join_pages(page_texts)


async def _extract_pdf_with_figures(data: bytes) -> Tuple[str, Optional[List[int]]]:
    """
    PDF text layer plus vision-generated text for embedded images. Each
    figure's text is appended to its own page, so page citations still point
    at the page the figure is on.
    """
    page_texts, images = await run_in_threadpool(
        _read_pdf_sync, data, vision_available()
    )
    if page_texts is None:
        return data.decode("utf-8", errors="replace"), None

    if images:
        descriptions = await describe_images([jpeg for _, jpeg in images])
        for (p_idx, _), desc in zip(images, descriptions):
            if desc:
                # One paragraph per figure so the chunker keeps it together
                desc = re.sub(r"\n\s*\n+", "\n", desc.strip())
                page_texts[p_idx] += f"\n\n[Figure on page {p_idx + 1}]\n{desc}"
    return _join_pages(page_texts)


async def _extract_image_text(data: bytes) -> str:
    """Standalone image upload → text via the vision model."""
    if not vision_available():
        raise ValueError("Image uploads need GEMINI_API_KEY set (vision is unavailable).")
    jpeg = await run_in_threadpool(prepare_image, data)
    if jpeg is None:
        raise ValueError("Unsupported, corrupt, or too-small image.")
    text = await describe_image(jpeg)
    if not text:
        raise ValueError("Could not extract any text or diagram content from the image.")
    return text


def _extract_text_docx(data: bytes) -> str:
    try:
        import docx  # type: ignore[import-untyped,import-not-found]
        doc = docx.Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception as exc:
        logger.warning("ingestion.docx_extraction_failed", error=str(exc))
        return data.decode("utf-8", errors="replace")


def _extract_text_sync(filename: str, data: bytes) -> Tuple[str, Optional[List[int]]]:
    """Returns (text, page_starts); page_starts is only set for parsed PDFs."""
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return _extract_text_pdf(data)
    if ext in {".docx", ".doc"}:
        return _extract_text_docx(data), None
    return data.decode("utf-8", errors="replace"), None


# -- Page tracking ------------------------------------------------------------

def _encode_with_pages(
    text: str,
    char_offset: int,
    page_starts: Optional[List[int]],
) -> Tuple[List[int], List[int]]:
    """
    Encode text and label every token with its 1-based PDF page number.
    char_offset is the position of text within the full document text.
    Returns (token_ids, token_pages); token_pages is empty without page_starts.
    """
    if not page_starts:
        return _encode_text(text), []
    tok = _load_tokenizer()
    enc = tok(text, add_special_tokens=False, return_offsets_mapping=True)
    pages = [
        bisect.bisect_right(page_starts, char_offset + start)
        for start, _ in enc["offset_mapping"]
    ]
    return list(enc["input_ids"]), pages


PageSpan = Tuple[int, int]  # (first_page, last_page), 1-based inclusive

# A page must hold at least this share of a chunk's tokens to count toward
# its span, so a few trailing tokens from the previous page don't shift it.
_PAGE_SPAN_MIN_SHARE: float = 0.15


def _page_span(token_pages: List[int]) -> Optional[PageSpan]:
    """Page range a token window meaningfully covers, or None if unknown."""
    if not token_pages:
        return None
    min_count = max(1, int(len(token_pages) * _PAGE_SPAN_MIN_SHARE))
    significant = [p for p, c in Counter(token_pages).items() if c >= min_count]
    if not significant:  # pathological spread â€” fall back to the majority page
        significant = [Counter(token_pages).most_common(1)[0][0]]
    return min(significant), max(significant)


# -- Parent-Child Chunking ----------------------------------------------------

def _split_into_parents(
    text: str,
    page_starts: Optional[List[int]] = None,
) -> Tuple[List[str], List[List[int]]]:
    """
    Split raw text into Parent chunks (at most PARENT_MAX_TOKENS tokens).

    1. Split on structural boundaries (double newlines / Markdown headings).
    2. Greedily merge adjacent paragraphs until Parent token budget is reached.
    3. Single paragraphs exceeding PARENT_MAX_TOKENS are sub-split on a
       sliding window with no overlap (parents serve LLM context, not search).

    Returns (parent_texts, parent_token_pages); each token_pages list labels
    the parent's tokens with PDF page numbers (empty when page_starts is None).
    """
    pieces = re.split(r"(\n\n+|\n#{1,6}\s)", text)

    parents: List[str] = []
    parent_pages: List[List[int]] = []
    current_tokens: List[int] = []
    current_pages: List[int] = []

    def _flush(tokens: List[int], pages: List[int]) -> None:
        parents.append(_decode_token_window(tokens))
        parent_pages.append(pages)

    pos = 0
    for piece in pieces:
        piece = piece or ""
        piece_start = pos
        pos += len(piece)
        para = piece.strip()
        if not para:
            continue
        para_start = piece_start + len(piece) - len(piece.lstrip())
        para_tokens, para_pages = _encode_with_pages(para, para_start, page_starts)

        if len(para_tokens) > PARENT_MAX_TOKENS:
            if current_tokens:
                _flush(current_tokens, current_pages)
                current_tokens, current_pages = [], []
            for start in range(0, len(para_tokens), PARENT_MAX_TOKENS):
                _flush(para_tokens[start: start + PARENT_MAX_TOKENS],
                       para_pages[start: start + PARENT_MAX_TOKENS])
            continue

        if len(current_tokens) + len(para_tokens) <= PARENT_MAX_TOKENS:
            current_tokens.extend(para_tokens)
            current_pages.extend(para_pages)
        else:
            if current_tokens:
                _flush(current_tokens, current_pages)
            current_tokens, current_pages = para_tokens, para_pages

    if current_tokens:
        _flush(current_tokens, current_pages)

    kept = [i for i, p in enumerate(parents) if p.strip()]
    return [parents[i] for i in kept], [parent_pages[i] for i in kept]


def _split_parent_into_children(
    parent_text: str,
    parent_token_pages: Optional[List[int]] = None,
) -> List[Tuple[str, Optional[PageSpan]]]:
    """
    Split one Parent into Child chunks (max CHILD_MAX_TOKENS,
    CHILD_OVERLAP_TOKENS sliding overlap) for embedding in ChromaDB.

    Returns (child_text, page_span) pairs. The parent is re-encoded from its
    decoded text, so child windows are mapped proportionally onto the
    parent's original token page labels.
    """
    token_ids = _encode_text(parent_text)
    if not token_ids:
        return []

    n_tokens = len(token_ids)
    n_pages = len(parent_token_pages or [])

    def _window_page(start: int, end: int) -> Optional[PageSpan]:
        if not n_pages:
            return None
        p_start = min(start * n_pages // n_tokens, n_pages - 1)
        p_end = max(end * n_pages // n_tokens, p_start + 1)
        return _page_span(parent_token_pages[p_start:p_end])  # type: ignore[index]

    children: List[Tuple[str, Optional[PageSpan]]] = []
    step = CHILD_MAX_TOKENS - CHILD_OVERLAP_TOKENS  # 350 tokens per step
    start = 0

    while start < n_tokens:
        end = min(start + CHILD_MAX_TOKENS, n_tokens)
        child_text = _decode_token_window(token_ids[start:end])
        if child_text.strip():
            children.append((child_text, _window_page(start, end)))
        if end == n_tokens:
            break
        start += step

    return children


def _build_parent_child_chunks(
    text: str,
    doc_id: str,
    page_starts: Optional[List[int]] = None,
) -> Tuple[List[str], List[str], List[str], List[str], List[Optional[PageSpan]]]:
    """
    Returns (parent_ids, parent_texts, child_ids, child_texts, child_pages).
    parent_id = "{doc_id}__parent_{p_idx}"
    child_id  = "{doc_id}__child_{p_idx}_{c_idx}"
    child_pages[i] is the (first, last) PDF page span of child i, or None.
    """
    parents, parents_token_pages = _split_into_parents(text, page_starts)
    parent_ids: List[str] = []
    parent_texts: List[str] = []
    child_ids: List[str] = []
    child_texts: List[str] = []
    child_pages: List[Optional[PageSpan]] = []

    for p_idx, (parent_text, token_pages) in enumerate(zip(parents, parents_token_pages)):
        pid = f"{doc_id}__parent_{p_idx}"
        parent_ids.append(pid)
        parent_texts.append(parent_text)
        children = _split_parent_into_children(parent_text, token_pages)
        for c_idx, (child_text, page) in enumerate(children):
            child_ids.append(f"{doc_id}__child_{p_idx}_{c_idx}")
            child_texts.append(child_text)
            child_pages.append(page)

    return parent_ids, parent_texts, child_ids, child_texts, child_pages


# -- BM25 management ----------------------------------------------------------

def _tokenise_for_bm25(text: str) -> List[str]:
    return text.lower().split()


def _rebuild_bm25(session_id: str, new_chunks: List[str]) -> None:
    """Append new child chunk tokens and rebuild BM25Okapi index."""
    existing = _session_corpus_tokens.get(session_id, [])
    new_tokenised = [_tokenise_for_bm25(c) for c in new_chunks]
    merged = existing + new_tokenised
    _session_corpus_tokens[session_id] = merged
    _session_bm25[session_id] = BM25Okapi(merged)
    logger.debug("bm25.rebuilt", session_id=session_id,
                 total_chunks=len(merged), new_chunks=len(new_tokenised))


# -- Helpers ------------------------------------------------------------------

def _stable_doc_id(filename: str, data: bytes) -> str:
    digest = hashlib.sha256(data).hexdigest()[:24]
    safe_name = Path(filename).stem[:32]
    return f"{safe_name}_{digest}"


def _next_corpus_version(session_id: str) -> int:
    version = _session_versions.get(session_id, 0) + 1
    _session_versions[session_id] = version
    return version


# -- Redis parent storage -----------------------------------------------------

async def _store_parents_in_redis(parent_ids: List[str], parent_texts: List[str]) -> None:
    """Store parent:{pid} -> full parent text in Redis with 7-day TTL."""
    try:
        from app.core.redis import get_redis_client
        client = get_redis_client()
        pipe = client.pipeline()
        for pid, txt in zip(parent_ids, parent_texts):
            pipe.set(f"parent:{pid}", txt, ex=86_400 * 7)
        await pipe.execute()
        logger.debug("ingestion.parents_stored_redis", count=len(parent_ids))
    except Exception as exc:
        logger.warning("ingestion.redis_parent_store_failed", error=str(exc))


async def _delete_parents_from_redis(parent_ids: List[str]) -> None:
    """Remove parent texts from Redis when a document is deleted."""
    try:
        from app.core.redis import get_redis_client
        client = get_redis_client()
        keys = [f"parent:{pid}" for pid in parent_ids]
        if keys:
            await client.delete(*keys)
    except Exception as exc:
        logger.warning("ingestion.redis_parent_delete_failed", error=str(exc))


# -- Public API ---------------------------------------------------------------

async def ingest_document(
    filename: str,
    data: bytes,
    session_id: str,
    extra_metadata: Optional[Dict] = None,
) -> Dict:
    """
    Parse, chunk (parent-child), embed children, and store.

    Child metadata in ChromaDB:
        session_id, doc_id, parent_id, chunk_id, chunk_index,
        corpus_version, filename, page, page_end (PDFs only).
    Parent texts stored in Redis as parent:{parent_id}.

    Returns: {doc_id, chunk_count, corpus_version, status}
    """
    doc_id = _stable_doc_id(filename, data)
    collection = _get_or_create_session_collection(session_id)

    existing = collection.get(where={"doc_id": doc_id}, limit=1)
    if existing["ids"]:
        logger.info("ingestion.duplicate_skipped", session_id=session_id,
                    doc_id=doc_id, filename=filename)
        return {"doc_id": doc_id, "chunk_count": 0,
                "corpus_version": _session_versions.get(session_id, 0),
                "status": "already_exists"}

    # CPU-bound work offloaded to threadpool; images/figures → text via vision
    ext = Path(filename).suffix.lower()
    page_starts: Optional[List[int]] = None
    if ext == ".pdf":
        text, page_starts = await _extract_pdf_with_figures(data)
    elif ext in IMAGE_EXTENSIONS:
        text = await _extract_image_text(data)
    else:
        text, page_starts = await run_in_threadpool(_extract_text_sync, filename, data)
    parent_ids, parent_texts, child_ids, child_texts, child_pages = await run_in_threadpool(
        _build_parent_child_chunks, text, doc_id, page_starts
    )

    if not child_texts:
        raise ValueError(f"No extractable text found in '{filename}'.")

    # Embed children â€” NO prefix (BGE: documents are never prefixed)
    embeddings: List[List[float]] = await run_in_threadpool(_embed_sync, child_texts)

    corpus_version = _next_corpus_version(session_id)

    # Derive parent_id from child_id naming convention:
    #   child_id:  {doc_id}__child_{p_idx}_{c_idx}
    #   parent_id: {doc_id}__parent_{p_idx}
    metadatas = []
    for c_idx, child_id in enumerate(child_ids):
        p_idx_str = child_id.rsplit("_", 1)[0].rsplit("_", 1)[1]
        parent_id = f"{doc_id}__parent_{p_idx_str}"
        meta = {
            "session_id": session_id,
            "doc_id": doc_id,
            "parent_id": parent_id,
            "chunk_id": child_id,
            "chunk_index": c_idx,
            "corpus_version": corpus_version,
            "filename": filename,
            **(extra_metadata or {}),
        }
        # ChromaDB rejects None metadata values â€” omit pages when unknown
        span = child_pages[c_idx]
        if span is not None:
            meta["page"], meta["page_end"] = span
        metadatas.append(meta)

    collection.upsert(ids=child_ids, embeddings=embeddings,
                      documents=child_texts, metadatas=metadatas)

    await _store_parents_in_redis(parent_ids, parent_texts)
    _rebuild_bm25(session_id, child_texts)

    try:
        from app.core.cache import increment_corpus_version
        await increment_corpus_version(session_id)
    except Exception as exc:
        logger.warning("ingestion.cache_version_bump_failed", error=str(exc))

    logger.info("ingestion.complete", session_id=session_id, doc_id=doc_id,
                filename=filename, parent_count=len(parent_ids),
                chunk_count=len(child_ids), corpus_version=corpus_version)
    return {"doc_id": doc_id, "chunk_count": len(child_ids),
            "corpus_version": corpus_version, "status": "ingested"}


async def delete_document(session_id: str, doc_id: str) -> int:
    """
    Remove all Child chunks for doc_id from ChromaDB, delete their Parent
    texts from Redis, and rebuild the BM25 index.
    Returns number of chunks removed.
    """
    collection = _get_or_create_session_collection(session_id)
    result = collection.get(where={"doc_id": doc_id}, include=["metadatas"])
    ids = result["ids"]
    if not ids:
        return 0

    parent_ids_to_delete: List[str] = list({
        m.get("parent_id", "")
        for m in (result.get("metadatas") or [])
        if m.get("parent_id")
    })

    collection.delete(ids=ids)
    await _delete_parents_from_redis(parent_ids_to_delete)

    remaining = collection.get(include=["documents"])
    remaining_docs: List[str] = remaining.get("documents") or []
    _session_corpus_tokens[session_id] = []
    if remaining_docs:
        _rebuild_bm25(session_id, remaining_docs)
    else:
        _session_bm25.pop(session_id, None)

    logger.info("ingestion.deleted", session_id=session_id, doc_id=doc_id,
                chunks_removed=len(ids), parents_removed=len(parent_ids_to_delete))
    return len(ids)

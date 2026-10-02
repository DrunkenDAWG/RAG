"""
app/api/v1/endpoints/documents.py
───────────────────────────────────
Document management endpoints:
  POST   /documents/upload   – ingest one or more files
  GET    /documents           – list all ingested documents
  DELETE /documents/{doc_id} – remove a document and its chunks
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.api.deps import AuthDep
from app.core.logging import get_logger
from app.services.ingestion import delete_document, get_collection, ingest_document

logger = get_logger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB


# ── Schemas ───────────────────────────────────────────────────────────────────

class IngestResult(BaseModel):
    filename: str
    document_id: str
    chunk_count: int
    status: str


class DocumentMeta(BaseModel):
    document_id: str
    filename: str
    chunk_count: int


class DeleteResult(BaseModel):
    document_id: str
    chunks_removed: int


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/upload",
    response_model=List[IngestResult],
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest one or more documents",
)
async def upload_documents(
    _: AuthDep,
    files: List[UploadFile] = File(..., description="PDF, DOCX, or plain-text files"),
) -> List[IngestResult]:
    results: List[IngestResult] = []
    for upload in files:
        data = await upload.read()

        if len(data) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File '{upload.filename}' exceeds the 50 MB limit.",
            )

        try:
            summary = await ingest_document(
                filename=upload.filename or "unknown",
                data=data,
                metadata={"content_type": upload.content_type or "application/octet-stream"},
            )
        except Exception as exc:
            logger.error("ingestion.failed", filename=upload.filename, error=str(exc))
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Failed to ingest '{upload.filename}': {exc}",
            )

        results.append(
            IngestResult(
                filename=upload.filename or "unknown",
                document_id=summary["document_id"],
                chunk_count=summary["chunk_count"],
                status=summary["status"],
            )
        )
    return results


@router.get(
    "",
    response_model=List[DocumentMeta],
    summary="List all ingested documents",
)
async def list_documents(_: AuthDep) -> List[DocumentMeta]:
    collection = get_collection()
    # Fetch all metadata (no embedding needed)
    result = collection.get(include=["metadatas"])
    if not result["metadatas"]:
        return []

    # Aggregate chunks per document_id
    doc_map: dict = {}
    for meta in result["metadatas"]:
        doc_id = meta.get("document_id", "")
        filename = meta.get("filename", "")
        if doc_id not in doc_map:
            doc_map[doc_id] = {"filename": filename, "chunk_count": 0}
        doc_map[doc_id]["chunk_count"] += 1

    return [
        DocumentMeta(document_id=doc_id, filename=v["filename"], chunk_count=v["chunk_count"])
        for doc_id, v in doc_map.items()
    ]


@router.delete(
    "/{document_id}",
    response_model=DeleteResult,
    summary="Delete a document and all its chunks",
)
async def remove_document(_: AuthDep, document_id: str) -> DeleteResult:
    removed = await delete_document(document_id)
    if removed == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )
    return DeleteResult(document_id=document_id, chunks_removed=removed)

"""Document catalog endpoints: index, ingest, list, delete."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

from rag_backend.dependencies import RagServiceDep
from rag_backend.schemas import (
    DocumentCatalogResponse,
    DocumentIndexRequest,
    FileIngestRequest,
    IngestResponse,
)

router = APIRouter(prefix="/documents", tags=["documents"])

# Per-file outcomes that should not degrade the batch to partial_success.
_ACCEPTABLE_INGEST_STATUSES = {"success", "duplicate"}


@router.post("/index")
async def index_documents(
    request: DocumentIndexRequest, rag_service: RagServiceDep
) -> dict[str, Any]:
    """Index in-memory documents for semantic search."""
    try:
        return rag_service.index_documents(request.documents)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.post("/ingest", response_model=IngestResponse)
async def ingest_files(request: FileIngestRequest, rag_service: RagServiceDep) -> dict[str, Any]:
    """Ingest local files by path into the catalog and vector index."""
    results = [
        rag_service.ingest_file(path, force_reindex=request.force_reindex) for path in request.paths
    ]
    all_ok = all(result.get("status") in _ACCEPTABLE_INGEST_STATUSES for result in results)
    return {"status": "success" if all_ok else "partial_success", "results": results}


@router.get("", response_model=DocumentCatalogResponse)
async def list_documents(rag_service: RagServiceDep) -> dict[str, Any]:
    """List indexed source documents."""
    return {"status": "success", "documents": rag_service.list_documents()}


@router.delete("/{document_id}")
async def delete_document(document_id: str, rag_service: RagServiceDep) -> dict[str, Any]:
    """Delete a source document and its indexed chunks."""
    result = rag_service.delete_document(document_id)
    if result.get("status") == "error":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("error"),
        )
    if result.get("status") == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return result

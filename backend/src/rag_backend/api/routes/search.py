"""Retrieval endpoints: similarity search and the full RAG query pipeline."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

from rag_backend.dependencies import RagServiceDep
from rag_backend.schemas import (
    DocumentQueryRequest,
    DocumentSearchRequest,
    QueryResponse,
    SearchResponse,
)

router = APIRouter(tags=["search"])


@router.post("/documents/search", response_model=SearchResponse)
async def search_documents(
    request: DocumentSearchRequest, rag_service: RagServiceDep
) -> dict[str, Any]:
    """Search for documents using hybrid dense + lexical retrieval."""
    try:
        results = rag_service.search_documents(
            query=request.query, k=request.k, min_score=request.min_score
        )
        return {"status": "success", "results": results}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.post("/query", response_model=QueryResponse)
async def query_documents(
    request: DocumentQueryRequest, rag_service: RagServiceDep
) -> dict[str, Any]:
    """Execute the RAG pipeline: retrieve documents and generate an answer."""
    try:
        result = rag_service.query_documents(
            user_query=request.query,
            k=request.k,
            min_score=request.min_score,
            answer_mode=request.answer_mode,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e

    if result.get("status") == "error":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("error"),
        )
    return result

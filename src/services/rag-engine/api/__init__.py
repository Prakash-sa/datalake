"""
API Layer - HTTP routes and controllers
"""

from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from typing import List

from application.rag_service import DocumentRAGService
from interfaces import (
    DocumentIndexRequest,
    DocumentSearchRequest,
    DocumentQueryRequest,
    HealthResponse,
    StatsResponse,
    SearchResponse,
    QueryResponse,
)

router = APIRouter()
rag_service = None


def initialize_rag_service(service: DocumentRAGService):
    """Initialize RAG service for API handlers."""
    global rag_service
    rag_service = service


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for monitoring and orchestration."""
    if not rag_service:
        # Service still initializing
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail="RAG service initializing")
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@router.get("/stats", response_model=StatsResponse)
async def get_stats():
    """Get engine statistics and metrics."""
    if not rag_service:
        raise HTTPException(status_code=500, detail="RAG service not initialized")

    stats = rag_service.get_stats()
    return StatsResponse(**stats)


@router.post("/documents/index")
async def index_documents(request: DocumentIndexRequest):
    """Index documents for semantic search."""
    if not rag_service:
        raise HTTPException(status_code=500, detail="RAG service not initialized")

    try:
        result = rag_service.index_documents(request.documents)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/documents/search", response_model=SearchResponse)
async def search_documents(request: DocumentSearchRequest):
    """Search for documents using semantic similarity."""
    if not rag_service:
        raise HTTPException(status_code=500, detail="RAG service not initialized")

    try:
        results = rag_service.search_documents(
            query=request.query, k=request.k, min_score=request.min_score
        )
        return {"status": "success", "results": results}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query", response_model=QueryResponse)
async def query_documents(request: DocumentQueryRequest):
    """Execute RAG pipeline: search documents and generate response."""
    if not rag_service:
        raise HTTPException(status_code=500, detail="RAG service not initialized")

    try:
        result = rag_service.query_documents(user_query=request.query, k=request.k)

        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("error"))

        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

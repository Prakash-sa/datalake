"""
API Layer - HTTP routes and controllers
"""

from datetime import datetime
from uuid import uuid4
from fastapi import APIRouter, HTTPException

from application.rag_service import DocumentRAGService
from interfaces import (
    DocumentIndexRequest,
    DocumentSearchRequest,
    DocumentQueryRequest,
    FileIngestRequest,
    ModelPullRequest,
    SettingsUpdateRequest,
    EvalRequest,
    HealthResponse,
    StatsResponse,
    SearchResponse,
    DocumentCatalogResponse,
    IngestResponse,
    ModelListResponse,
    SettingsResponse,
    QueryResponse,
    ReadinessResponse,
    EvalResponse,
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


@router.get("/readiness", response_model=ReadinessResponse)
async def get_readiness():
    """Report production operating capabilities."""
    if not rag_service:
        raise HTTPException(status_code=500, detail="RAG service not initialized")

    return rag_service.get_readiness()


@router.get("/models", response_model=ModelListResponse)
async def list_models():
    """List installed and required Ollama models."""
    if not rag_service:
        raise HTTPException(status_code=500, detail="RAG service not initialized")

    return rag_service.list_ollama_models()


@router.post("/models/pull")
async def pull_model(request: ModelPullRequest):
    """Pull a local Ollama model."""
    if not rag_service:
        raise HTTPException(status_code=500, detail="RAG service not initialized")

    result = rag_service.pull_ollama_model(request.name)
    if result.get("status") == "error":
        raise HTTPException(status_code=502, detail=result.get("error"))
    return result


@router.get("/settings", response_model=SettingsResponse)
async def get_settings():
    """Return local runtime settings."""
    if not rag_service:
        raise HTTPException(status_code=500, detail="RAG service not initialized")

    return {"status": "success", "settings": rag_service.get_settings()}


@router.post("/settings", response_model=SettingsResponse)
async def update_settings(request: SettingsUpdateRequest):
    """Persist local runtime settings."""
    if not rag_service:
        raise HTTPException(status_code=500, detail="RAG service not initialized")

    result = rag_service.update_settings(request.dict(exclude_none=True))
    return {"status": result["status"], "settings": result["settings"]}


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


@router.post("/documents/ingest", response_model=IngestResponse)
async def ingest_files(request: FileIngestRequest):
    """Ingest local files by path into the catalog and vector index."""
    if not rag_service:
        raise HTTPException(status_code=500, detail="RAG service not initialized")

    results = [
        rag_service.ingest_file(path, force_reindex=request.force_reindex)
        for path in request.paths
    ]
    status = "success" if all(result.get("status") in {"success", "duplicate"} for result in results) else "partial_success"
    return {"status": status, "results": results}


@router.get("/documents", response_model=DocumentCatalogResponse)
async def list_documents():
    """List indexed source documents."""
    if not rag_service:
        raise HTTPException(status_code=500, detail="RAG service not initialized")

    return {"status": "success", "documents": rag_service.list_documents()}


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str):
    """Delete a source document and its indexed chunks."""
    if not rag_service:
        raise HTTPException(status_code=500, detail="RAG service not initialized")

    result = rag_service.delete_document(document_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("error"))
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Document not found")
    return result


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
        result = rag_service.query_documents(
            user_query=request.query,
            k=request.k,
            min_score=request.min_score,
        )

        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("error"))

        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/eval", response_model=EvalResponse)
async def run_eval(request: EvalRequest):
    """Run deterministic retrieval and answer checks for release gating."""
    if not rag_service:
        raise HTTPException(status_code=500, detail="RAG service not initialized")

    eval_results = []
    passed_cases = 0

    for case in request.cases:
        result = rag_service.query_documents(
            user_query=case.query,
            k=request.k,
            min_score=case.min_relevance,
        )
        documents = result.get("retrieved_documents", [])
        answer = result.get("answer", "").lower()
        expected_terms = case.answer_contains or []
        missing_terms = [
            term for term in expected_terms if term.lower() not in answer
        ]
        max_relevance = max(
            [doc.get("relevance_score", 0.0) for doc in documents],
            default=0.0,
        )

        answer_contains_passed = not missing_terms
        min_documents_passed = len(documents) >= case.min_documents
        min_relevance_passed = max_relevance >= case.min_relevance
        passed = (
            answer_contains_passed
            and min_documents_passed
            and min_relevance_passed
            and result.get("status") != "error"
        )

        if passed:
            passed_cases += 1

        eval_results.append(
            {
                "id": case.id,
                "passed": passed,
                "answer_contains_passed": answer_contains_passed,
                "min_documents_passed": min_documents_passed,
                "min_relevance_passed": min_relevance_passed,
                "document_count": len(documents),
                "max_relevance": max_relevance,
                "missing_terms": missing_terms,
                "processing_time_seconds": result.get("processing_time_seconds", 0.0),
            }
        )

    response = {
        "status": "success",
        "passed": passed_cases == len(request.cases),
        "total_cases": len(request.cases),
        "passed_cases": passed_cases,
        "results": eval_results,
    }
    rag_service.catalog.record_eval_run(
        run_id=f"eval_{uuid4().hex}",
        status="passed" if response["passed"] else "failed",
        request=request.dict(),
        result=response,
    )
    return response

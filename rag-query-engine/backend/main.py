"""
FastAPI Backend for Document RAG Engine
Production-ready REST API with comprehensive error handling, validation, and monitoring.

Provides endpoints for semantic search and LLM-powered document analysis on enterprise documents.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from typing import Optional, List
import logging
import os
import json
from datetime import datetime

from rag_engine import DocumentRAGEngine

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app with production settings
app = FastAPI(
    title="Document RAG Engine",
    description="Production-ready REST API for semantic search and LLM-powered analysis on enterprise documents",
    version="2.0.0",
    docs_url="/docs" if os.getenv("ENV", "production") == "development" else None,
    redoc_url="/redoc" if os.getenv("ENV", "production") == "development" else None,
)

# CORS configuration for production
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    max_age=600,  # Cache preflight requests for 10 minutes
)

# Initialize RAG engine with error handling
rag_engine = None
try:
    rag_engine = DocumentRAGEngine(
        chroma_path=os.getenv("CHROMA_PATH", "./chroma_db"),
        ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
        embedding_model=os.getenv("EMBEDDING_MODEL", "nomic-embed-text"),
        llm_model=os.getenv("LLM_MODEL", "mistral"),
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.3")),
    )
    logger.info("✅ Document RAG Engine initialized successfully")
except Exception as e:
    logger.error(f"❌ Failed to initialize RAG Engine: {e}", exc_info=True)
    rag_engine = None


# Pydantic models with validation
class DocumentQueryRequest(BaseModel):
    """Request model for document queries with validation."""
    query: str = Field(..., min_length=1, max_length=1000, description="Search query")
    k: int = Field(5, ge=1, le=100, description="Number of results to return")
    min_score: Optional[float] = Field(0.0, ge=0.0, le=1.0, description="Minimum similarity score")
    
    @validator('query')
    def query_not_empty(cls, v):
        if not v.strip():
            raise ValueError('Query cannot be empty or whitespace only')
        return v.strip()


class DocumentResponse(BaseModel):
    """Response model for document RAG results."""
    status: str
    query: str
    answer: Optional[str] = None
    retrieved_documents: Optional[List] = None
    document_count: int = 0
    processing_time_seconds: Optional[float] = None
    error: Optional[str] = None
    timestamp: str


class DocumentIndexRequest(BaseModel):
    """Request model for indexing documents with validation."""
    documents: List[dict] = Field(..., min_items=1, max_items=1000, description="List of {id, content, metadata}")
    
    @validator('documents')
    def validate_documents(cls, v):
        for doc in v:
            if not isinstance(doc, dict):
                raise ValueError('Each document must be a dictionary')
            if 'id' not in doc or 'content' not in doc:
                raise ValueError('Each document must have "id" and "content" fields')
        return v


class DocumentSearchRequest(BaseModel):
    """Request model for semantic search without LLM."""
    query: str = Field(..., min_length=1, max_length=1000)
    k: int = Field(5, ge=1, le=100)
    min_score: Optional[float] = Field(0.0, ge=0.0, le=1.0)


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    rag_engine: str
    timestamp: str
    version: str


# Health check endpoint
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint for monitoring and orchestration.
    Returns: status, engine state, version, and timestamp.
    """
    return {
        "status": "healthy" if rag_engine else "degraded",
        "rag_engine": "initialized" if rag_engine else "not_initialized",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0"
    }


@app.get("/stats")
async def get_stats():
    """Get engine statistics for monitoring."""
    if not rag_engine:
        raise HTTPException(status_code=503, detail="RAG Engine not initialized")
    
    return rag_engine.get_stats()


# Query endpoint with production-grade error handling
@app.post("/query", response_model=DocumentResponse)
async def query_documents(request: DocumentQueryRequest):
    """
    Query documents using RAG (Retrieval Augmented Generation).
    
    This endpoint:
    - Retrieves relevant documents using semantic search
    - Generates an LLM-powered response based on retrieved context
    - Includes comprehensive error handling and monitoring
    
    Example request:
    ```json
    {
        "query": "What is Apache Airflow?",
        "k": 5,
        "min_score": 0.0
    }
    ```
    """
    if not rag_engine:
        logger.error("RAG Engine not initialized")
        raise HTTPException(status_code=503, detail="RAG Engine not initialized. Please check server logs.")
    
    try:
        logger.info(f"🔍 Processing document query: {request.query[:100]}...")
        result = rag_engine.query_documents(request.query, k=request.k)

        
        # Include processing time in response
        if "processing_time_seconds" in result:
            result["processing_time_seconds"] = result["processing_time_seconds"]
        
        return DocumentResponse(
            status=result["status"],
            query=result.get("query"),
            answer=result.get("answer"),
            retrieved_documents=result.get("retrieved_documents"),
            document_count=result.get("document_count", 0),
            processing_time_seconds=result.get("processing_time_seconds"),
            error=result.get("error"),
            timestamp=result.get("timestamp")
        )
    except ValueError as e:
        logger.warning(f"⚠️  Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Query processing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error processing query")


@app.post("/documents/index")
async def index_documents(request: DocumentIndexRequest):
    """
    Index documents into the vector store for semantic search and RAG.
    
    This endpoint:
    - Validates documents have required fields (id, content)
    - Generates embeddings for each document
    - Stores in vector database for retrieval
    - Returns detailed success/failure statistics
    
    Example request:
    ```json
    {
        "documents": [
            {
                "id": "doc1",
                "content": "Apache Airflow is a workflow orchestration platform...",
                "metadata": {"source": "documentation", "date": "2024-01-01"}
            },
            {
                "id": "doc2",
                "content": "Kubernetes is a container orchestration system...",
                "metadata": {"source": "wiki"}
            }
        ]
    }
    ```
    
    Returns: Indexing statistics with success/failure counts and error details.
    """
    if not rag_engine:
        raise HTTPException(status_code=503, detail="RAG Engine not initialized")
    
    try:
        logger.info(f"📄 Indexing {len(request.documents)} documents...")
        result = rag_engine.index_documents(request.documents)
        
        return {
            "status": result["status"],
            "documents_indexed": result.get("documents_indexed", 0),
            "documents_failed": result.get("documents_failed", 0),
            "errors": result.get("errors"),
            "timestamp": result.get("timestamp")
        }
    except Exception as e:
        logger.error(f"❌ Document indexing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error indexing documents")


@app.post("/documents/search")
async def search_documents(
    query: str = Query(..., min_length=1, max_length=1000),
    k: int = Query(5, ge=1, le=100),
    min_score: float = Query(0.0, ge=0.0, le=1.0)
):
    """
    Semantic search on indexed documents without LLM generation.
    
    This endpoint:
    - Searches documents using semantic similarity
    - Returns ranked documents by relevance score
    - Fast lookup without LLM inference
    - Useful for exploratory search and validation
    
    Query parameters:
        - query: Search query (required, 1-1000 chars)
        - k: Number of results to return (default: 5, max: 100)
        - min_score: Minimum similarity score filter (0.0-1.0, default: 0.0)
    
    Returns: List of relevant documents with similarity scores.
    """
    if not rag_engine:
        raise HTTPException(status_code=503, detail="RAG Engine not initialized")
    
    try:
        logger.info(f"🔍 Searching documents: {query[:100]}...")
        results = rag_engine.search_documents(query, k=k, min_score=min_score)
        
        return {
            "status": "success",
            "query": query,
            "count": len(results),
            "documents": results,
            "timestamp": datetime.now().isoformat()
        }
    except ValueError as e:
        logger.warning(f"⚠️  Search validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during search")


@app.get("/")
async def root():
    """API documentation and status endpoint."""
    return {
        "name": "Document RAG Engine",
        "version": "2.0.0",
        "status": "healthy" if rag_engine else "degraded",
        "description": "Production-ready REST API for semantic search and LLM-powered analysis on enterprise documents",
        "endpoints": {
            "health": {"GET": "/health", "description": "Health check for monitoring"},
            "stats": {"GET": "/stats", "description": "Engine statistics and metrics"},
            "query": {"POST": "/query", "description": "RAG query with LLM analysis"},
            "search": {"POST": "/documents/search", "description": "Semantic search only"},
            "index": {"POST": "/documents/index", "description": "Index documents to vector store"},
            "docs": {"GET": "/docs", "description": "Interactive API documentation (dev only)"}
        }
    }


# Error handlers
@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    """Handle validation errors."""
    logger.warning(f"Validation error: {exc}")
    return JSONResponse(
        status_code=400,
        content={"status": "error", "error": str(exc), "timestamp": datetime.now().isoformat()}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle unexpected errors."""
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"status": "error", "error": "Internal server error", "timestamp": datetime.now().isoformat()}
    )


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    env = os.getenv("ENV", "production")
    
    logger.info(f"🚀 Starting Document RAG Engine on {host}:{port} (env: {env})")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=os.getenv("LOG_LEVEL", "info"),
        access_log=env == "development"
    )

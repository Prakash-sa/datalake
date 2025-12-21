"""
FastAPI Backend for Document RAG Engine
Provides REST API endpoints for semantic search and LLM-powered document analysis.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import logging
import os
import json

from rag_engine import DocumentRAGEngine

# Initialize FastAPI app
app = FastAPI(
    title="Document RAG Engine",
    description="REST API for semantic search and LLM-powered analysis on enterprise documents",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize RAG engine
try:
    rag_engine = DocumentRAGEngine(
        chroma_path=os.getenv("CHROMA_PATH", "./chroma_db"),
        ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434")
    )
    logger.info("✅ Document RAG Engine initialized")
except Exception as e:
    logger.error(f"❌ Failed to initialize RAG Engine: {e}")
    rag_engine = None


# Pydantic models
class DocumentQueryRequest(BaseModel):
    """Request model for document queries."""
    query: str
    k: int = 5  # Number of documents to retrieve


class DocumentResponse(BaseModel):
    """Response model for document RAG results."""
    status: str
    query: str
    answer: Optional[str] = None
    retrieved_documents: Optional[List] = None
    document_count: int = 0
    error: Optional[str] = None
    timestamp: str


class DocumentIndexRequest(BaseModel):
    """Request model for indexing documents."""
    documents: List[dict]  # List of {id, content, metadata}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "rag_engine": "initialized" if rag_engine else "not_initialized"
    }


@app.post("/query", response_model=DocumentResponse)
async def query_documents(request: DocumentQueryRequest):
    """
    Query documents using RAG (Retrieval Augmented Generation).
    Retrieves relevant documents and generates an LLM-powered response.
    
    Example:
    {
        "query": "What is Apache Airflow and how does it work?",
        "k": 5
    }
    """
    if not rag_engine:
        raise HTTPException(status_code=503, detail="RAG Engine not initialized")
    
    if not request.query or request.query.strip() == "":
        raise HTTPException(status_code=400, detail="Query is required")
    
    try:
        logger.info(f"🔍 Processing document query: {request.query[:100]}...")
        result = rag_engine.query_documents(request.query, k=request.k)
        
        return DocumentResponse(
            status=result["status"],
            query=result.get("query"),
            answer=result.get("answer"),
            retrieved_documents=result.get("retrieved_documents"),
            document_count=result.get("document_count", 0),
            error=result.get("error"),
            timestamp=result.get("timestamp")
        )
    except Exception as e:
        logger.error(f"❌ Query processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/documents/index")
async def index_documents(request: DocumentIndexRequest):
    """
    Index documents into the vector store for semantic search.
    
    Example:
    {
        "documents": [
            {
                "id": "doc1",
                "content": "Document text content...",
                "metadata": {"source": "pdf", "date": "2024-01-01"}
            }
        ]
    }
    """
    if not rag_engine:
        raise HTTPException(status_code=503, detail="RAG Engine not initialized")
    
    if not request.documents:
        raise HTTPException(status_code=400, detail="Documents list is required")
    
    try:
        logger.info(f"📄 Indexing {len(request.documents)} documents...")
        result = rag_engine.index_documents(request.documents)
        
        return {
            "status": result["status"],
            "documents_indexed": result.get("documents_indexed", 0),
            "error": result.get("error"),
            "timestamp": result.get("timestamp")
        }
    except Exception as e:
        logger.error(f"❌ Document indexing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/documents/search")
async def search_documents(query: str, k: int = 5):
    """
    Semantic search on indexed documents without LLM generation.
    Returns relevant documents ranked by similarity score.
    
    Query parameters:
        - query: Search query string
        - k: Number of results to return (default: 5)
    """
    if not rag_engine:
        raise HTTPException(status_code=503, detail="RAG Engine not initialized")
    
    if not query or query.strip() == "":
        raise HTTPException(status_code=400, detail="Query is required")
    
    try:
        logger.info(f"🔍 Searching documents: {query[:100]}...")
        results = rag_engine.search_documents(query, k=k)
        
        return {
            "status": "success",
            "query": query,
            "count": len(results),
            "documents": results
        }
    except Exception as e:
        logger.error(f"❌ Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    """API documentation endpoint."""
    return {
        "name": "Document RAG Engine",
        "version": "1.0.0",
        "description": "Semantic search and LLM-powered analysis on enterprise documents",
        "endpoints": {
            "health": "GET /health",
            "query": "POST /query (natural language query with LLM analysis)",
            "search": "POST /documents/search (semantic search without LLM)",
            "index": "POST /documents/index (add documents to vector store)"
        },
        "docs": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

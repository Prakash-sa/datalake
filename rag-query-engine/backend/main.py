"""
FastAPI Backend for RAG Query Engine
Provides REST API endpoints for natural language querying of the data lake.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import logging
import os

from rag_engine import DataLakeRAGEngine

# Initialize FastAPI app
app = FastAPI(
    title="Data Lake RAG Query Engine",
    description="Natural language interface for querying Apache Iceberg tables",
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
    rag_engine = DataLakeRAGEngine(
        trino_host=os.getenv("TRINO_HOST", "localhost"),
        trino_port=int(os.getenv("TRINO_PORT", "8080"))
    )
    logger.info("✅ RAG Engine initialized")
except Exception as e:
    logger.error(f"❌ Failed to initialize RAG Engine: {e}")
    rag_engine = None


# Pydantic models
class QueryRequest(BaseModel):
    """Request model for natural language queries."""
    query: str
    max_retries: int = 2


class QueryResponse(BaseModel):
    """Response model for query results."""
    user_query: str
    sql_query: str
    results: dict
    attempts: int
    timestamp: str


class MetadataIndexRequest(BaseModel):
    """Request model for metadata indexing."""
    force_reindex: bool = False


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "rag_engine": "initialized" if rag_engine else "not_initialized"
    }


@app.post("/query", response_model=QueryResponse)
async def query_data_lake(request: QueryRequest):
    """
    Natural language query endpoint.
    
    Accepts natural language queries and returns:
    - Generated SQL
    - Query results
    - Number of self-correction attempts
    
    Example:
    {
        "query": "Show me total sales by region",
        "max_retries": 2
    }
    """
    if not rag_engine:
        raise HTTPException(status_code=503, detail="RAG Engine not initialized")
    
    try:
        logger.info(f"📝 Processing query: {request.query}")
        result = rag_engine.query_data_lake(request.query, max_retries=request.max_retries)
        
        return QueryResponse(**result)
    except Exception as e:
        logger.error(f"❌ Query processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/metadata/index")
async def index_metadata(request: MetadataIndexRequest, background_tasks: BackgroundTasks):
    """
    Trigger metadata indexing for semantic search.
    Returns immediately and indexes asynchronously.
    
    Example:
    {
        "force_reindex": false
    }
    """
    if not rag_engine:
        raise HTTPException(status_code=503, detail="RAG Engine not initialized")
    
    try:
        background_tasks.add_task(rag_engine.index_metadata)
        return {
            "status": "indexing_started",
            "message": "Metadata indexing started in background"
        }
    except Exception as e:
        logger.error(f"❌ Metadata indexing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metadata/tables")
async def get_indexed_tables():
    """Retrieve list of indexed tables from metadata cache."""
    if not rag_engine:
        raise HTTPException(status_code=503, detail="RAG Engine not initialized")
    
    tables = {}
    for table_name, columns in rag_engine.metadata_cache.items():
        if table_name not in tables:
            tables[table_name] = []
        tables[table_name].append(columns)
    
    return {
        "count": len(tables),
        "tables": tables
    }


@app.post("/query/validate")
async def validate_sql(request: dict):
    """
    Validate generated SQL without executing it.
    
    Example:
    {
        "sql": "SELECT * FROM iceberg.raw.sales"
    }
    """
    sql = request.get("sql")
    if not sql:
        raise HTTPException(status_code=400, detail="SQL query required")
    
    # Basic validation (syntax check via Trino)
    if not rag_engine:
        raise HTTPException(status_code=503, detail="RAG Engine not initialized")
    
    try:
        # Prepend EXPLAIN to validate without execution
        cursor = rag_engine.conn.cursor()
        cursor.execute(f"EXPLAIN {sql}")
        cursor.close()
        
        return {
            "valid": True,
            "message": "SQL is valid"
        }
    except Exception as e:
        return {
            "valid": False,
            "error": str(e)
        }


@app.get("/")
async def root():
    """API documentation endpoint."""
    return {
        "name": "Data Lake RAG Query Engine",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "query": "POST /query",
            "metadata_index": "POST /metadata/index",
            "indexed_tables": "GET /metadata/tables",
            "validate_sql": "POST /query/validate"
        },
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

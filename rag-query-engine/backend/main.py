"""
FastAPI Backend for Data Lake Query Engine
Provides REST API endpoints for executing SQL queries on Apache Iceberg tables.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import logging
import os

from rag_engine import DataLakeQueryEngine

# Initialize FastAPI app
app = FastAPI(
    title="Data Lake Query Engine",
    description="REST API for executing SQL queries on Apache Iceberg tables",
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

# Initialize query engine
try:
    query_engine = DataLakeQueryEngine(
        trino_host=os.getenv("TRINO_HOST", "localhost"),
        trino_port=int(os.getenv("TRINO_PORT", "8080"))
    )
    logger.info("✅ Query Engine initialized")
except Exception as e:
    logger.error(f"❌ Failed to initialize Query Engine: {e}")
    query_engine = None


# Pydantic models
class QueryRequest(BaseModel):
    """Request model for SQL queries."""
    sql: str


class QueryResponse(BaseModel):
    """Response model for query results."""
    status: str
    rows: Optional[List] = None
    columns: Optional[List] = None
    row_count: int
    error: Optional[str] = None
    timestamp: str


class TableInfo(BaseModel):
    """Request model for getting table info."""
    pass


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "query_engine": "initialized" if query_engine else "not_initialized"
    }


@app.post("/query", response_model=QueryResponse)
async def execute_query(request: QueryRequest):
    """
    Execute SQL query on the data lake.
    
    Example:
    {
        "sql": "SELECT * FROM iceberg.raw.sales LIMIT 10"
    }
    """
    if not query_engine:
        raise HTTPException(status_code=503, detail="Query Engine not initialized")
    
    if not request.sql or request.sql.strip() == "":
        raise HTTPException(status_code=400, detail="SQL query is required")
    
    try:
        logger.info(f"🔍 Executing query: {request.sql[:100]}...")
        result = query_engine.execute_query(request.sql)
        
        return QueryResponse(
            status=result["status"],
            rows=result.get("rows"),
            columns=result.get("columns"),
            row_count=result.get("row_count", 0),
            error=result.get("error"),
            timestamp=result.get("timestamp")
        )
    except Exception as e:
        logger.error(f"❌ Query execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tables")
async def get_tables():
    """Retrieve list of available tables and their schemas."""
    if not query_engine:
        raise HTTPException(status_code=503, detail="Query Engine not initialized")
    
    try:
        tables = query_engine.get_tables_info()
        return {
            "count": len(tables),
            "tables": tables
        }
    except Exception as e:
        logger.error(f"❌ Failed to retrieve tables: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    """API documentation endpoint."""
    return {
        "name": "Data Lake Query Engine",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "query": "POST /query",
            "tables": "GET /tables"
        },
        "docs": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

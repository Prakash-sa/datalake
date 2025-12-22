"""
Response Models - API output with Pydantic
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    timestamp: str = datetime.now().isoformat()


class StatsResponse(BaseModel):
    """Engine statistics response."""

    documents_indexed: int
    queries_processed: int
    errors: int
    total_documents: int
    timestamp: str


class DocumentResultItem(BaseModel):
    """Single document in search result."""

    id: str
    content: str
    relevance_score: float
    metadata: Dict[str, Any] = {}


class SearchResponse(BaseModel):
    """Search response."""

    status: str
    results: List[DocumentResultItem]
    timestamp: str = datetime.now().isoformat()


class QueryResponse(BaseModel):
    """RAG query response."""

    status: str
    query: str
    answer: str
    retrieved_documents: List[DocumentResultItem]
    document_count: int
    processing_time_seconds: float
    timestamp: str = datetime.now().isoformat()

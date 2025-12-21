"""
Request Models - API input validation with Pydantic
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator


class DocumentIndexRequest(BaseModel):
    """Request model for indexing documents."""

    documents: List[Dict[str, Any]] = Field(
        ..., min_items=1, max_items=1000, description="List of documents to index"
    )

    @validator("documents")
    def validate_documents(cls, documents):
        """Validate each document has required fields."""
        for doc in documents:
            if "id" not in doc or "content" not in doc:
                raise ValueError("Each document must have 'id' and 'content'")
        return documents


class DocumentSearchRequest(BaseModel):
    """Request model for searching documents."""

    query: str = Field(..., min_length=1, max_length=1000, description="Search query")
    k: int = Field(5, ge=1, le=100, description="Number of results")
    min_score: Optional[float] = Field(
        0.0, ge=0.0, le=1.0, description="Minimum relevance score"
    )


class DocumentQueryRequest(BaseModel):
    """Request model for RAG queries."""

    query: str = Field(
        ..., min_length=1, max_length=1000, description="Natural language query"
    )
    k: int = Field(5, ge=1, le=100, description="Number of documents to retrieve")
    min_score: Optional[float] = Field(
        0.0, ge=0.0, le=1.0, description="Minimum relevance score"
    )

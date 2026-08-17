"""
Domain Models - Core entities and value objects
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Document:
    """Domain model for a document"""

    id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.id:
            raise ValueError("Document ID cannot be empty")
        if not self.content:
            raise ValueError("Document content cannot be empty")


@dataclass
class SearchResult:
    """Domain model for search result"""

    document_id: str
    content: str
    relevance_score: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not 0.0 <= self.relevance_score <= 1.0:
            raise ValueError("Relevance score must be between 0.0 and 1.0")


@dataclass
class QueryResult:
    """Domain model for query result"""

    query: str
    search_results: List[SearchResult]
    llm_analysis: Optional[str] = None
    processing_time_seconds: float = 0.0
    status: str = "success"
    error: Optional[str] = None


@dataclass
class EngineStats:
    """Domain model for engine statistics"""

    documents_indexed: int = 0
    queries_processed: int = 0
    errors: int = 0
    total_documents: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

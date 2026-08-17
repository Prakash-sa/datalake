"""
Response Models - API output with Pydantic
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class StatsResponse(BaseModel):
    """Engine statistics response."""

    documents_indexed: int
    queries_processed: int
    errors: int
    total_documents: int
    catalog_documents: int
    timestamp: str


class DocumentResultItem(BaseModel):
    """Single document in search result."""

    id: str
    content: str
    relevance_score: float
    metadata: dict[str, Any] = {}


class SearchResponse(BaseModel):
    """Search response."""

    status: str
    results: list[DocumentResultItem]
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class DocumentCatalogItem(BaseModel):
    """Indexed source document catalog item."""

    id: str
    source_path: str
    title: str
    source_hash: str
    content_type: str
    parser_version: str
    chunker_version: str
    embedding_model: str
    llm_model: str
    indexed_at: str
    updated_at: str
    metadata: dict[str, Any] = {}
    chunk_count: int = 0


class DocumentCatalogResponse(BaseModel):
    """Catalog listing response."""

    status: str
    documents: list[DocumentCatalogItem]
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class IngestResponse(BaseModel):
    """File ingestion response."""

    status: str
    results: list[dict[str, Any]]
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class ModelListResponse(BaseModel):
    """Ollama model listing response."""

    status: str
    ollama_url: str
    models: list[dict[str, Any]]
    required_models: list[str]
    missing_models: list[str]
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class SettingsResponse(BaseModel):
    """Runtime settings response."""

    status: str
    settings: dict[str, Any]
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class QueryResponse(BaseModel):
    """RAG query response."""

    status: str
    query: str
    answer: str
    retrieved_documents: list[DocumentResultItem]
    document_count: int
    processing_time_seconds: float
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class ReadinessResponse(BaseModel):
    """Production readiness capabilities response."""

    status: str
    capabilities: dict[str, Any]
    stats: dict[str, Any]
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class EvalCaseResult(BaseModel):
    """Single eval result."""

    id: str
    passed: bool
    answer_contains_passed: bool
    min_documents_passed: bool
    min_relevance_passed: bool
    document_count: int
    max_relevance: float
    missing_terms: list[str]
    processing_time_seconds: float


class EvalResponse(BaseModel):
    """Batch eval response."""

    status: str
    passed: bool
    total_cases: int
    passed_cases: int
    results: list[EvalCaseResult]
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

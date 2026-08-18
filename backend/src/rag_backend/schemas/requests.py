"""Request schemas - API input validation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

MAX_QUERY_LENGTH = 1000


class DocumentIndexRequest(BaseModel):
    """Request model for indexing documents."""

    documents: list[dict[str, Any]] = Field(
        ..., min_length=1, max_length=1000, description="List of documents to index"
    )

    @field_validator("documents")
    @classmethod
    def validate_documents(cls, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Every document must carry an id and content."""
        for doc in documents:
            if "id" not in doc or "content" not in doc:
                raise ValueError("Each document must have 'id' and 'content'")
        return documents


class DocumentSearchRequest(BaseModel):
    """Request model for searching documents."""

    query: str = Field(..., min_length=1, max_length=MAX_QUERY_LENGTH, description="Search query")
    k: int = Field(5, ge=1, le=100, description="Number of results")
    min_score: float | None = Field(0.0, ge=0.0, le=1.0, description="Minimum relevance score")


class DocumentQueryRequest(BaseModel):
    """Request model for RAG queries."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=MAX_QUERY_LENGTH,
        description="Natural language query",
    )
    k: int = Field(5, ge=1, le=100, description="Number of documents to retrieve")
    min_score: float | None = Field(0.0, ge=0.0, le=1.0, description="Minimum relevance score")


class FileIngestRequest(BaseModel):
    """Request model for ingesting local files."""

    paths: list[str] = Field(..., min_length=1, max_length=100)
    force_reindex: bool = Field(False, description="Re-parse and re-index duplicate files")


class ModelPullRequest(BaseModel):
    """Request model for pulling an Ollama model."""

    name: str = Field(..., min_length=1, max_length=200)


class SettingsUpdateRequest(BaseModel):
    """Runtime settings persisted locally."""

    ollama_url: str | None = Field(None, min_length=1, max_length=500)
    embedding_model: str | None = Field(None, min_length=1, max_length=200)
    llm_model: str | None = Field(None, min_length=1, max_length=200)
    temperature: float | None = Field(None, ge=0.0, le=1.0)


class EvalCase(BaseModel):
    """Single deterministic eval case for retrieval and answer grounding."""

    id: str = Field(..., min_length=1, max_length=120)
    query: str = Field(..., min_length=1, max_length=MAX_QUERY_LENGTH)
    answer_contains: list[str] | None = Field(
        default=None, description="Terms expected in the generated answer"
    )
    min_documents: int = Field(1, ge=0, le=100)
    min_relevance: float = Field(0.0, ge=0.0, le=1.0)
    relevant_chunk_ids: list[str] | None = Field(
        default=None,
        description="Ground-truth chunk ids, enabling retrieval metrics for this case",
    )


class EvalRequest(BaseModel):
    """Batch eval request."""

    cases: list[EvalCase] = Field(..., min_length=1, max_length=50)
    k: int = Field(5, ge=1, le=100)


class JobEnqueueRequest(BaseModel):
    """Queue ingestion jobs for local files."""

    paths: list[str] = Field(..., min_length=1, max_length=100)
    force_reindex: bool = Field(
        False, description="Re-parse and re-index files already in the catalog"
    )


class DataExportRequest(BaseModel):
    """Write an archive of local data."""

    destination: str = Field(..., min_length=1, max_length=4096)


class DataImportRequest(BaseModel):
    """Read an archive of local data."""

    source: str = Field(..., min_length=1, max_length=4096)

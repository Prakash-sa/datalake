"""Shared test fixtures.

The API fixtures build the app with a stub RAG service so route wiring,
validation, and status codes can be tested without Ollama or Chroma running.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from rag_backend.app import create_app
from rag_backend.settings import Settings


@pytest.fixture
def settings(tmp_path) -> Settings:
    """Settings pointed at throwaway per-test storage."""
    return Settings(
        ENV="testing",
        DEBUG="true",
        CHROMA_PATH=str(tmp_path / "chroma"),
        APP_DB_PATH=str(tmp_path / "app.db"),
        ALLOWED_ORIGINS="http://localhost:3000",
    )


class StubRagService:
    """Minimal stand-in exposing the surface the routes depend on."""

    def __init__(self) -> None:
        self.catalog = None
        self.deleted: list[str] = []

    def get_stats(self) -> dict[str, Any]:
        return {
            "documents_indexed": 1,
            "queries_processed": 2,
            "errors": 0,
            "total_documents": 3,
            "catalog_documents": 1,
            "timestamp": "2026-01-01T00:00:00",
        }

    def get_readiness(self) -> dict[str, Any]:
        return {"status": "ready", "capabilities": {}, "stats": self.get_stats()}

    def get_diagnostics(self) -> dict[str, Any]:
        return {"status": "success", "runtime": {}}

    def list_documents(self) -> list[dict[str, Any]]:
        return []

    def delete_document(self, document_id: str) -> dict[str, Any]:
        self.deleted.append(document_id)
        return {"status": "not_found", "document_id": document_id, "chunks_deleted": 0}

    def search_documents(
        self, query: str, k: int = 5, min_score: float | None = None
    ) -> list[dict[str, Any]]:
        return [
            {
                "id": "chunk-1",
                "content": "local rag content",
                "relevance_score": 0.9,
                "metadata": {},
            }
        ]


@pytest.fixture
def stub_rag_service() -> StubRagService:
    return StubRagService()


@pytest.fixture
def client(settings: Settings, stub_rag_service: StubRagService):
    """TestClient whose app has the stub service injected post-startup."""
    app = create_app(settings)
    with TestClient(app) as test_client:
        app.state.rag_service = stub_rag_service
        yield test_client


@pytest.fixture
def unready_client(settings: Settings):
    """TestClient whose RAG service never initialized."""
    app = create_app(settings)
    with TestClient(app) as test_client:
        app.state.rag_service = None
        app.state.eval_service = None
        yield test_client

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
        self.shutdown_called = False

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

    def shutdown(self) -> None:
        self.shutdown_called = True


class StubJobService:
    """In-memory stand-in for the ingestion queue."""

    def __init__(self) -> None:
        self.jobs: dict[str, dict[str, Any]] = {}
        self._n = 0
        self.shutdown_called = False

    def start(self) -> None:
        """No worker thread in tests."""

    def shutdown(self, timeout: float = 5.0) -> None:
        """Called by lifespan teardown; recorded so it can be asserted."""
        self.shutdown_called = True

    def _make(self, source_path: str, force_reindex: bool) -> dict[str, Any]:
        self._n += 1
        job_id = f"job_{self._n}"
        job = {
            "id": job_id,
            "source_path": source_path,
            "document_id": None,
            "status": "queued",
            "error_code": None,
            "error": None,
            "attempts": 0,
            "chunks_total": 0,
            "chunks_done": 0,
            "force_reindex": force_reindex,
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
            "finished_at": None,
        }
        self.jobs[job_id] = job
        return job

    def enqueue(self, source_path: str, force_reindex: bool = False) -> dict[str, Any]:
        return self._make(source_path, force_reindex)

    def list_jobs(self, statuses=None, limit=100) -> list[dict[str, Any]]:
        jobs = list(self.jobs.values())
        if statuses:
            jobs = [j for j in jobs if j["status"] in statuses]
        return jobs[:limit]

    def get_job(self, job_id: str):
        return self.jobs.get(job_id)

    def cancel(self, job_id: str):
        job = self.jobs.get(job_id)
        if job:
            job["status"] = "cancelled"
        return job

    def retry(self, job_id: str):
        job = self.jobs.get(job_id)
        if job and job["status"] == "failed":
            job["status"] = "queued"
        return job


@pytest.fixture
def stub_rag_service() -> StubRagService:
    return StubRagService()


class StubDataService:
    """In-memory stand-in for export/import/backup."""

    def backup(self, destination_dir: str | None = None) -> dict[str, Any]:
        return {"status": "success", "path": "/tmp/catalog.db", "size_bytes": 1}

    def list_backups(self) -> list[dict[str, Any]]:
        return []

    def export(self, destination: str) -> dict[str, Any]:
        return {"status": "success", "path": destination, "document_count": 0}

    def inspect(self, source: str) -> dict[str, Any]:
        return {"status": "success", "manifest": {"format_version": 1}}

    def import_archive(self, source: str) -> dict[str, Any]:
        return {"status": "success", "document_count": 0, "reindex_required": True}


@pytest.fixture
def stub_job_service() -> StubJobService:
    return StubJobService()


@pytest.fixture
def stub_data_service() -> StubDataService:
    return StubDataService()


@pytest.fixture
def client(
    settings: Settings,
    stub_rag_service: StubRagService,
    stub_job_service: StubJobService,
    stub_data_service: StubDataService,
):
    """TestClient whose app has the stub services injected post-startup."""
    app = create_app(settings)
    with TestClient(app) as test_client:
        app.state.rag_service = stub_rag_service
        app.state.job_service = stub_job_service
        app.state.data_service = stub_data_service
        yield test_client


@pytest.fixture
def unready_client(settings: Settings):
    """TestClient whose RAG service never initialized."""
    app = create_app(settings)
    with TestClient(app) as test_client:
        app.state.rag_service = None
        app.state.eval_service = None
        app.state.job_service = None
        app.state.data_service = None
        yield test_client

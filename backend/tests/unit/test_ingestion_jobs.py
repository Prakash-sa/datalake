"""Ingestion queue: persistence, progress, cancellation, and retry.

Runs against a real SQLite catalog and a real local Chroma index; only the
embedding call is stubbed, since that is the part that reaches Ollama.
"""

from __future__ import annotations

import pytest

from rag_backend.application.ingestion_jobs import IngestionJobService
from rag_backend.application.rag_service import DocumentRAGService
from rag_backend.domain.jobs import JobStatus


class StubEmbeddings:
    def __init__(self, fail: bool = False):
        self.fail = fail

    def embed_query(self, content: str) -> list[float]:
        if self.fail:
            raise RuntimeError("Failed to connect to Ollama.")
        return [float(len(content) % 5)] * 8


@pytest.fixture
def rag(tmp_path) -> DocumentRAGService:
    service = DocumentRAGService(
        chroma_path=str(tmp_path / "chroma"), app_db_path=str(tmp_path / "app.db")
    )
    service.embeddings = StubEmbeddings()
    return service


@pytest.fixture
def jobs(rag) -> IngestionJobService:
    # start() is never called, so no worker thread runs; process_job is driven
    # directly and the state machine is exercised deterministically.
    return IngestionJobService(rag)


@pytest.fixture
def doc(tmp_path):
    path = tmp_path / "notes.md"
    path.write_text("# Notes\n\nProduction readiness requires citations.", encoding="utf-8")
    return path


def test_enqueue_persists_a_queued_job(jobs, doc):
    job = jobs.enqueue(str(doc))

    assert job["status"] == JobStatus.QUEUED
    assert job["source_path"].endswith("notes.md")
    assert job["attempts"] == 0
    assert jobs.get_job(job["id"]) is not None


def test_processing_a_job_reaches_complete(jobs, doc):
    job = jobs.enqueue(str(doc))

    result = jobs.process_job(job["id"])

    assert result["status"] == JobStatus.COMPLETE
    assert result["document_id"]
    assert result["chunks_total"] >= 1
    assert result["chunks_done"] >= 1
    assert result["finished_at"] is not None
    assert result["attempts"] == 1


def test_completed_job_indexes_its_chunks(jobs, rag, doc):
    job = jobs.enqueue(str(doc))
    jobs.process_job(job["id"])

    assert rag.vector_store.count() >= 1
    assert len(rag.catalog.list_documents()) == 1


def test_missing_file_fails_with_an_actionable_code(jobs, tmp_path):
    job = jobs.enqueue(str(tmp_path / "absent.md"))

    result = jobs.process_job(job["id"])

    assert result["status"] == JobStatus.FAILED
    assert result["error_code"] == "unsupported_format"
    assert result["error"]


def test_embedding_failure_marks_the_job_failed(jobs, rag, doc):
    rag.embeddings = StubEmbeddings(fail=True)
    job = jobs.enqueue(str(doc))

    result = jobs.process_job(job["id"])

    assert result["status"] == JobStatus.FAILED
    assert result["error_code"] == "embedding_failed"


def test_failed_job_can_be_retried(jobs, rag, doc):
    rag.embeddings = StubEmbeddings(fail=True)
    job = jobs.enqueue(str(doc))
    jobs.process_job(job["id"])

    rag.embeddings = StubEmbeddings()
    requeued = jobs.retry(job["id"])
    assert requeued["status"] == JobStatus.QUEUED
    assert requeued["error"] is None

    result = jobs.process_job(job["id"])
    assert result["status"] == JobStatus.COMPLETE
    # The retry is a second attempt on the same job record.
    assert result["attempts"] == 2


def test_cancelling_a_queued_job_stops_it_running(jobs, rag, doc):
    job = jobs.enqueue(str(doc))

    cancelled = jobs.cancel(job["id"])
    assert cancelled["status"] == JobStatus.CANCELLED

    result = jobs.process_job(job["id"])
    assert result["status"] == JobStatus.CANCELLED
    # Nothing was indexed, so a cancelled import leaves no partial state.
    assert rag.vector_store.count() == 0


def test_cancelled_jobs_are_not_resumable(jobs, doc):
    job = jobs.enqueue(str(doc))
    jobs.cancel(job["id"])

    result = jobs.retry(job["id"])

    assert result["status"] == JobStatus.CANCELLED


def test_cancelling_an_unknown_job_returns_none(jobs):
    assert jobs.cancel("job_missing") is None


def test_completed_jobs_are_not_reprocessed(jobs, doc):
    job = jobs.enqueue(str(doc))
    jobs.process_job(job["id"])

    again = jobs.process_job(job["id"])

    assert again["status"] == JobStatus.COMPLETE
    assert again["attempts"] == 1


def test_duplicate_import_completes_without_reindexing(jobs, rag, doc):
    first = jobs.enqueue(str(doc))
    jobs.process_job(first["id"])
    indexed = rag.vector_store.count()

    second = jobs.enqueue(str(doc))
    result = jobs.process_job(second["id"])

    assert result["status"] == JobStatus.COMPLETE
    assert result["error_code"] == "duplicate"
    assert rag.vector_store.count() == indexed


def test_force_reindex_bypasses_the_duplicate_check(jobs, doc):
    first = jobs.enqueue(str(doc))
    jobs.process_job(first["id"])

    second = jobs.enqueue(str(doc), force_reindex=True)
    result = jobs.process_job(second["id"])

    assert result["status"] == JobStatus.COMPLETE
    assert result["error_code"] is None


def test_jobs_are_listed_newest_first_and_filterable(jobs, doc, tmp_path):
    other = tmp_path / "second.txt"
    other.write_text("another document", encoding="utf-8")

    first = jobs.enqueue(str(doc))
    jobs.enqueue(str(other))
    jobs.process_job(first["id"])

    assert len(jobs.list_jobs()) == 2
    complete = jobs.list_jobs(statuses=[JobStatus.COMPLETE])
    assert [j["id"] for j in complete] == [first["id"]]


def test_job_state_survives_a_new_service_instance(jobs, rag, doc):
    # Progress must survive a restart, so state lives in SQLite, not memory.
    job = jobs.enqueue(str(doc))
    jobs.process_job(job["id"])

    reloaded = IngestionJobService(rag).get_job(job["id"])

    assert reloaded["status"] == JobStatus.COMPLETE


def _wait_for(predicate, timeout: float = 10.0) -> bool:
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def test_started_worker_drains_the_queue(jobs, doc):
    # The worker is what the running application relies on, so it needs at least
    # one test that actually starts a thread.
    job = jobs.enqueue(str(doc))
    jobs.start()
    try:
        drained = _wait_for(lambda: jobs.get_job(job["id"])["status"] == JobStatus.COMPLETE)
    finally:
        jobs.shutdown()

    assert drained, f"job stuck in {jobs.get_job(job['id'])['status']}"


def test_shutdown_stops_the_worker(jobs):
    jobs.start()
    jobs.shutdown()

    assert jobs._worker is not None
    assert not jobs._worker.is_alive()


def test_start_is_idempotent(jobs):
    jobs.start()
    first = jobs._worker
    jobs.start()
    try:
        assert jobs._worker is first
    finally:
        jobs.shutdown()

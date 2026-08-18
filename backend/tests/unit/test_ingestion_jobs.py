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
    dimensions = 8

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


def test_rebuild_requeues_every_catalogued_document(jobs, doc):
    first = jobs.enqueue(str(doc))
    jobs.process_job(first["id"])

    result = jobs.rebuild_all()

    assert result["queued"] == 1
    assert result["missing_sources"] == []
    # Reindexing must bypass the duplicate check or nothing would be re-embedded.
    assert result["jobs"][0]["force_reindex"] is True


def test_rebuild_reports_documents_whose_source_file_is_gone(jobs, doc):
    job = jobs.enqueue(str(doc))
    jobs.process_job(job["id"])
    doc.unlink()

    result = jobs.rebuild_all()

    assert result["queued"] == 0
    assert len(result["missing_sources"]) == 1


def test_rebuild_on_an_empty_catalog_queues_nothing(jobs):
    result = jobs.rebuild_all()

    assert result["queued"] == 0
    assert result["jobs"] == []


def test_indexing_records_the_index_fingerprint(jobs, rag, doc):
    assert rag.stored_fingerprint() is None

    job = jobs.enqueue(str(doc))
    jobs.process_job(job["id"])

    stored = rag.stored_fingerprint()
    assert stored is not None
    assert stored["embedding_model"] == rag.embedding_model


def test_changing_the_embedding_model_reports_a_rebuild(jobs, rag, doc):
    job = jobs.enqueue(str(doc))
    jobs.process_job(job["id"])

    rag.embedding_model = "a-different-model"

    assert rag.check_index_compatibility()["rebuild_required"] is True


OLD_OLLAMA_FINGERPRINT = {
    "embedding_provider": "ollama",
    "embedding_model": "qwen3-embedding:0.6b",
    "embedding_digest": "sha256:old",
    "embedding_dimensions": 1024,
    "chunker_version": "recursive-char-v1",
    "parser_version": "local-parser-v1",
    "index_schema_version": 1,
}


def _simulate_old_index(rag) -> None:
    """Make the catalog look like an index built by a different model."""
    rag.catalog.set_setting("index_fingerprint", OLD_OLLAMA_FINGERPRINT)


def test_import_is_refused_when_the_index_was_built_by_another_model(jobs, rag, doc):
    # Chroma fixes a collection's vector width, so writing 384-dim vectors into
    # a 1024-dim collection fails deep in the driver. Refuse earlier, with a
    # remedy the user can act on.
    jobs.process_job(jobs.enqueue(str(doc))["id"])
    _simulate_old_index(rag)

    result = jobs.process_job(jobs.enqueue(str(doc), force_reindex=True)["id"])

    assert result["status"] == JobStatus.FAILED
    assert result["error_code"] == "index_model_mismatch"
    assert "Rebuild" in result["error"]


def test_rebuild_recreates_the_collection_and_restores_search(jobs, rag, doc):
    jobs.process_job(jobs.enqueue(str(doc))["id"])
    _simulate_old_index(rag)
    assert rag.check_index_compatibility()["rebuild_required"] is True

    outcome = jobs.rebuild_all()
    for job in outcome["jobs"]:
        jobs.process_job(job["id"])

    assert outcome["queued"] == 1
    assert rag.check_index_compatibility()["rebuild_required"] is False
    assert rag.vector_store.count() >= 1


def test_an_empty_index_adopts_the_new_configuration_silently(jobs, rag, doc):
    # Nothing is at risk in an empty index, so requiring an explicit rebuild
    # would be friction for no benefit.
    _simulate_old_index(rag)

    result = jobs.process_job(jobs.enqueue(str(doc))["id"])

    assert result["status"] == JobStatus.COMPLETE
    assert rag.check_index_compatibility()["rebuild_required"] is False


def test_reset_index_clears_vectors_and_restamps_the_fingerprint(jobs, rag, doc):
    jobs.process_job(jobs.enqueue(str(doc))["id"])
    assert rag.vector_store.count() >= 1

    rag.reset_index()

    assert rag.vector_store.count() == 0
    assert rag.stored_fingerprint()["embedding_provider"] == rag.embedding_provider_name


def test_mismatch_is_caught_even_with_no_recorded_fingerprint(jobs, rag, doc):
    # An index written before fingerprints existed has none to compare against,
    # which is the ordinary upgrade case. The stored vectors still have a fixed
    # width, so that is measured directly.
    rag.vector_store.upsert(["legacy"], ["old"], [{"id": "legacy"}], [[0.1] * 1024])
    rag.catalog.set_setting("index_fingerprint", None)
    assert rag.stored_fingerprint() is None

    compatibility = rag.check_index_compatibility()

    assert compatibility["rebuild_required"] is True
    assert compatibility["stored_dimensions"] == 1024


def test_import_is_refused_when_only_the_stored_vectors_reveal_the_mismatch(jobs, rag, doc):
    rag.vector_store.upsert(["legacy"], ["old"], [{"id": "legacy"}], [[0.1] * 1024])
    rag.catalog.set_setting("index_fingerprint", None)

    result = jobs.process_job(jobs.enqueue(str(doc))["id"])

    assert result["status"] == JobStatus.FAILED
    assert result["error_code"] == "index_model_mismatch"


def test_rebuild_recovers_an_index_that_has_no_fingerprint(jobs, rag, doc):
    jobs.process_job(jobs.enqueue(str(doc))["id"])
    rag.vector_store.reset()
    rag.vector_store.upsert(["legacy"], ["old"], [{"id": "legacy"}], [[0.1] * 1024])
    rag.catalog.set_setting("index_fingerprint", None)

    outcome = jobs.rebuild_all()
    for job in outcome["jobs"]:
        jobs.process_job(job["id"])

    assert rag.vector_store.dimension() == StubEmbeddings.dimensions
    assert rag.check_index_compatibility()["rebuild_required"] is False


def test_dimension_is_none_for_an_empty_collection(rag):
    assert rag.vector_store.dimension() is None


def test_matching_dimensions_do_not_trigger_a_rebuild(jobs, rag, doc):
    jobs.process_job(jobs.enqueue(str(doc))["id"])
    rag.catalog.set_setting("index_fingerprint", None)

    # No fingerprint, but the stored width matches the provider, so there is
    # nothing to rebuild.
    assert rag.check_index_compatibility()["rebuild_required"] is False


def test_empty_but_width_constrained_collection_recovers_automatically(jobs, rag, doc):
    # Chroma keeps a collection's width after every row is deleted, so an empty
    # index can still reject a new model's vectors. Nothing is at stake, so this
    # must resolve itself rather than demanding a rebuild.
    rag.vector_store.upsert(["seed"], ["x"], [{"id": "seed"}], [[0.1] * 1024])
    rag.vector_store.delete(["seed"])
    assert rag.vector_store.count() == 0

    result = jobs.process_job(jobs.enqueue(str(doc))["id"])

    assert result["status"] == JobStatus.COMPLETE
    assert rag.vector_store.count() >= 1


def test_a_populated_mismatched_index_is_never_silently_discarded(jobs, rag, doc):
    # Auto-recovery must not extend to an index holding real data.
    rag.vector_store.upsert(["legacy"], ["old"], [{"id": "legacy"}], [[0.1] * 1024])

    result = jobs.process_job(jobs.enqueue(str(doc))["id"])

    assert result["status"] == JobStatus.FAILED
    assert result["error_code"] == "index_model_mismatch"
    assert rag.vector_store.count() == 1


def test_the_mismatch_error_names_both_widths(rag):
    from rag_backend.errors import IndexModelMismatchError

    rag.vector_store.upsert(["legacy"], ["old"], [{"id": "legacy"}], [[0.1] * 1024])

    with pytest.raises(IndexModelMismatchError) as excinfo:
        rag.vector_store.upsert(["new"], ["y"], [{"id": "new"}], [[0.2] * 8])

    assert excinfo.value.details == {"expected_dimensions": 1024, "received_dimensions": 8}
    assert excinfo.value.actionable is True

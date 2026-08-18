"""Persistent ingestion job queue.

Drives each import through the state machine in :mod:`rag_backend.domain.jobs`,
persisting every transition so progress survives a restart and the UI can render
per-document status, actionable errors, retry, and cancellation.

A single worker thread processes the queue. Ingestion is I/O bound on Ollama and
Chroma, and Chroma expects a single writer, so added concurrency would buy
nothing and risk corrupting the index.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any
from uuid import uuid4

from rag_backend.application.ingestion_service import build_ingested_document
from rag_backend.application.rag_service import DocumentRAGService
from rag_backend.domain.jobs import JobStatus, is_terminal
from rag_backend.errors import ErrorCode, RagError

logger = logging.getLogger(__name__)


class IngestionJobService:
    """Queues, runs, cancels, and retries document ingestion jobs."""

    def __init__(self, rag_service: DocumentRAGService) -> None:
        self._rag = rag_service
        self._catalog = rag_service.catalog
        self._cancelled: set[str] = set()
        self._lock = threading.Lock()
        self._worker: threading.Thread | None = None
        self._wake = threading.Event()
        self._shutdown = threading.Event()

    # -- Queue management -----------------------------------------------------

    def enqueue(self, source_path: str, force_reindex: bool = False) -> dict[str, Any]:
        """Persist a queued job and wake the worker if one is running.

        Enqueuing deliberately does not start a worker. The application owns the
        worker lifecycle (see ``lifespan``), which keeps the queue drivable
        synchronously and avoids spawning a thread per caller.
        """
        job = self._catalog.create_job(
            job_id=f"job_{uuid4().hex}",
            source_path=str(Path(source_path).expanduser()),
            force_reindex=force_reindex,
        )
        self._wake.set()
        return job

    def list_jobs(
        self, statuses: list[str] | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """List jobs newest first."""
        return self._catalog.list_jobs(statuses=statuses, limit=limit)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        """Fetch one job."""
        return self._catalog.get_job(job_id)

    def cancel(self, job_id: str) -> dict[str, Any] | None:
        """Cancel a queued or running job.

        A running job is flagged; the worker checks between stages and stops at
        the next boundary rather than leaving a half-committed index.
        """
        job = self._catalog.get_job(job_id)
        if job is None:
            return None
        if is_terminal(JobStatus(job["status"])):
            return job

        with self._lock:
            self._cancelled.add(job_id)

        return self._catalog.update_job(
            job_id,
            status=JobStatus.CANCELLED,
            error_code=str(ErrorCode.CANCELLED),
            error="Cancelled",
            finished_at=_now(),
        )

    def retry(self, job_id: str) -> dict[str, Any] | None:
        """Return a failed job to the queue.

        Only failures are resumable; a cancelled job stays cancelled, since the
        user deliberately stopped it.
        """
        job = self._catalog.get_job(job_id)
        if job is None or JobStatus(job["status"]) is not JobStatus.FAILED:
            return job

        with self._lock:
            self._cancelled.discard(job_id)

        updated = self._catalog.update_job(
            job_id,
            status=JobStatus.QUEUED,
            error_code=None,
            error=None,
            chunks_done=0,
            finished_at=None,
        )
        self._wake.set()
        return updated

    def rebuild_all(self) -> dict[str, Any]:
        """Re-queue every catalogued document for reindexing.

        Used after an embedding-model change, when existing vectors can no
        longer be compared against new queries. Documents whose source file has
        since moved are reported rather than queued, because reindexing needs
        the original bytes.
        """
        queued: list[dict[str, Any]] = []
        missing: list[str] = []

        for document in self._catalog.list_documents():
            source = Path(document["source_path"]).expanduser()
            if not source.is_file():
                missing.append(document["source_path"])
                continue
            queued.append(self.enqueue(str(source), force_reindex=True))

        return {
            "status": "accepted",
            "queued": len(queued),
            "jobs": queued,
            "missing_sources": missing,
        }

    # -- Worker ---------------------------------------------------------------

    def start(self) -> None:
        """Ensure a background worker thread is alive."""
        with self._lock:
            if self._worker is not None and self._worker.is_alive():
                self._wake.set()
                return
            self._shutdown.clear()
            self._worker = threading.Thread(
                target=self._run_worker, name="ingestion-worker", daemon=True
            )
            self._worker.start()
        self._wake.set()

    def shutdown(self, timeout: float = 5.0) -> None:
        """Stop the worker after the job in flight reaches a stage boundary."""
        self._shutdown.set()
        self._wake.set()
        worker = self._worker
        if worker is not None and worker.is_alive():
            worker.join(timeout=timeout)

    def _run_worker(self) -> None:
        while not self._shutdown.is_set():
            queued = self._catalog.list_jobs(statuses=[JobStatus.QUEUED], limit=1)
            if not queued:
                # Nothing to do; sleep until enqueue() or shutdown() wakes us.
                self._wake.clear()
                self._wake.wait(timeout=1.0)
                continue
            self.process_job(queued[0]["id"])

    # -- Execution ------------------------------------------------------------

    def _is_cancelled(self, job_id: str) -> bool:
        with self._lock:
            return job_id in self._cancelled

    def _advance(self, job_id: str, status: JobStatus, **fields: Any) -> None:
        self._catalog.update_job(job_id, status=status, **fields)

    def process_job(self, job_id: str) -> dict[str, Any] | None:
        """Run one job through the pipeline.

        Called by the worker, and directly by tests so the state machine can be
        exercised without threading.
        """
        job = self._catalog.get_job(job_id)
        if job is None or is_terminal(JobStatus(job["status"])):
            return job

        self._catalog.update_job(job_id, attempts=job["attempts"] + 1)

        try:
            # Parse
            if self._stop(job_id):
                return self._catalog.get_job(job_id)
            self._advance(job_id, JobStatus.PARSING)
            path = Path(job["source_path"]).expanduser().resolve()
            ingested = build_ingested_document(path, self._rag.embedding_model, self._rag.llm_model)

            # Chunk
            if self._stop(job_id):
                return self._catalog.get_job(job_id)
            document = ingested["document"]
            chunks = ingested["chunks"]
            self._advance(
                job_id,
                JobStatus.CHUNKING,
                document_id=document["id"],
                chunks_total=len(chunks),
            )

            existing = self._catalog.get_document_by_hash(document["source_hash"])
            if existing and not job["force_reindex"]:
                # Already indexed; completing is more honest than re-embedding.
                return self._advance_complete(job_id, len(chunks), duplicate=True)

            # Embed
            if self._stop(job_id):
                return self._catalog.get_job(job_id)
            self._advance(job_id, JobStatus.EMBEDDING)
            index_result = self._rag.index_documents(
                [
                    {
                        "id": chunk["id"],
                        "content": chunk["content"],
                        "metadata": chunk["metadata"],
                    }
                    for chunk in chunks
                ]
            )
            if index_result.get("status") == "error":
                return self._fail(
                    job_id,
                    ErrorCode.EMBEDDING_FAILED,
                    index_result.get("error", "Embedding failed"),
                )
            indexed = index_result.get("documents_indexed", 0)
            if indexed == 0 and chunks:
                return self._fail(
                    job_id,
                    ErrorCode.EMBEDDING_FAILED,
                    "No chunks could be embedded",
                )

            # Commit
            if self._stop(job_id):
                return self._catalog.get_job(job_id)
            self._advance(job_id, JobStatus.COMMITTING, chunks_done=indexed)
            self._catalog.upsert_document(document, chunks)
            return self._advance_complete(job_id, indexed)

        except RagError as e:
            return self._fail(job_id, e.code, e.message)
        except ValueError as e:
            # build_ingested_document rejects unsupported or unreadable files.
            return self._fail(job_id, ErrorCode.UNSUPPORTED_FORMAT, str(e))
        except Exception as e:
            logger.error("Ingestion job %s failed: %s", job_id, e, exc_info=True)
            return self._fail(job_id, ErrorCode.INTERNAL_ERROR, str(e))

    def _stop(self, job_id: str) -> bool:
        """Whether the job was cancelled since the last stage boundary."""
        return self._is_cancelled(job_id)

    def _advance_complete(
        self, job_id: str, chunks_done: int, duplicate: bool = False
    ) -> dict[str, Any] | None:
        with self._lock:
            self._cancelled.discard(job_id)
        return self._catalog.update_job(
            job_id,
            status=JobStatus.COMPLETE,
            chunks_done=chunks_done,
            error_code="duplicate" if duplicate else None,
            finished_at=_now(),
        )

    def _fail(self, job_id: str, code: ErrorCode | str, message: str) -> dict[str, Any] | None:
        return self._catalog.update_job(
            job_id,
            status=JobStatus.FAILED,
            error_code=str(code),
            error=message,
            finished_at=_now(),
        )


def _now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()

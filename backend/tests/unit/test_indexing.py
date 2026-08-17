"""Indexing behaviour when the embedding backend misbehaves.

Chroma is local and file-backed, so a real service can be built against a
temporary directory. Only the embedding call is stubbed, since that is the part
that reaches out to Ollama.
"""

from __future__ import annotations

import pytest

from rag_backend.application.rag_service import DocumentRAGService


class FlakyEmbeddings:
    """Embeds successfully except for content listed in ``fail_on``."""

    def __init__(self, fail_on: set[str] | None = None, dim: int = 8) -> None:
        self.fail_on = fail_on or set()
        self.dim = dim
        self.calls: list[str] = []

    def embed_query(self, content: str) -> list[float]:
        self.calls.append(content)
        if content in self.fail_on:
            raise RuntimeError("Failed to connect to Ollama.")
        return [float(len(content) % 7)] * self.dim


@pytest.fixture
def service(tmp_path) -> DocumentRAGService:
    svc = DocumentRAGService(
        chroma_path=str(tmp_path / "chroma"),
        app_db_path=str(tmp_path / "app.db"),
    )
    svc.embeddings = FlakyEmbeddings()
    return svc


def _docs(*ids: str) -> list[dict]:
    return [{"id": i, "content": f"content for {i}", "metadata": {}} for i in ids]


def test_indexes_documents_successfully(service):
    result = service.index_documents(_docs("a", "b", "c"))

    assert result["status"] == "success"
    assert result["documents_indexed"] == 3
    assert service.vector_store.count() == 3


def test_every_embedding_failing_does_not_crash_the_batch(service):
    # Reproduces the Ollama-unavailable case: previously the id/content lists
    # were appended before embedding, so Chroma received 56 ids and 0 embeddings.
    service.embeddings = FlakyEmbeddings(fail_on={f"content for {i}" for i in ("a", "b", "c")})

    result = service.index_documents(_docs("a", "b", "c"))

    assert result["status"] == "partial_success"
    assert result["documents_indexed"] == 0
    assert len(result["errors"]) == 3
    assert service.vector_store.count() == 0


def test_partial_embedding_failure_keeps_content_aligned(service):
    # The dangerous case: a mid-batch failure must not shift embeddings against
    # their documents.
    service.embeddings = FlakyEmbeddings(fail_on={"content for b"})

    result = service.index_documents(_docs("a", "b", "c"))

    assert result["status"] == "partial_success"
    assert result["documents_indexed"] == 2
    assert service.vector_store.count() == 2

    stored = service.vector_store._collection.get(include=["documents"])
    by_id = dict(zip(stored["ids"], stored["documents"], strict=True))
    assert by_id == {"a": "content for a", "c": "content for c"}


def test_documents_missing_required_fields_are_skipped(service):
    result = service.index_documents(
        [
            {"id": "a", "content": "content for a"},
            {"id": "", "content": "orphaned"},
            {"id": "c", "content": ""},
        ]
    )

    assert result["status"] == "partial_success"
    assert result["documents_indexed"] == 1
    assert service.vector_store.count() == 1


def test_empty_document_list_is_a_noop(service):
    assert service.index_documents([]) == {
        "status": "success",
        "documents_indexed": 0,
    }

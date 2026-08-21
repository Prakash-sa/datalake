"""Streaming generation: event ordering, cancellation, and error mapping."""

from __future__ import annotations

import threading

import pytest

from rag_backend.application.rag_service import DocumentRAGService
from rag_backend.errors import ErrorCode, ModelUnavailableError


class StubEmbeddings:
    def embed_query(self, content: str) -> list[float]:
        return [float(len(content) % 5)] * 8


class StubGeneration:
    """Stands in for the configured generation provider."""

    name = "test"
    model_name = "test-model"

    def __init__(self, tokens: list[str] | None = None, error: Exception | None = None):
        self.tokens = tokens or ["Answer ", "[S1]", "."]
        self.error = error
        self.seen_cancel: threading.Event | None = None
        self.seen_max_tokens: int | None = None

    def stream_generate(self, prompt, temperature=0.1, cancel=None, **kwargs):
        self.seen_cancel = cancel
        self.seen_max_tokens = kwargs.get("max_tokens")
        if self.error:
            raise self.error
        for token in self.tokens:
            if cancel is not None and cancel.is_set():
                return
            yield token

    def generate(self, prompt, temperature=0.1, **kwargs):
        return "".join(self.stream_generate(prompt, temperature=temperature))

    def health(self):
        return {"status": "ready", "provider": self.name, "model": self.model_name}


@pytest.fixture
def service(tmp_path) -> DocumentRAGService:
    svc = DocumentRAGService(
        chroma_path=str(tmp_path / "chroma"), app_db_path=str(tmp_path / "app.db")
    )
    svc.embeddings = StubEmbeddings()
    svc.generation = StubGeneration()
    return svc


def _index(service: DocumentRAGService) -> None:
    service.index_documents([{"id": "chunk-1", "content": "local rag content", "metadata": {}}])


def _collect(service: DocumentRAGService, **kwargs) -> list[dict]:
    return list(service.stream_query_documents("what is local rag", **kwargs))


def test_events_arrive_in_order_sources_then_tokens_then_done(service):
    _index(service)

    events = _collect(service)

    assert events[0]["event"] == "sources"
    assert [e["event"] for e in events[1:-1]] == ["token", "token", "token"]
    assert events[-1]["event"] == "done"


def test_done_event_carries_the_joined_answer_and_citations(service):
    _index(service)

    done = _collect(service)[-1]

    assert done["answer"] == "Answer [S1]."
    assert done["citations"]["valid"] is True
    assert done["citations"]["cited_chunk_ids"] == ["chunk-1"]
    assert done["status"] == "success"


def test_sources_are_emitted_before_any_token(service):
    # The UI renders citations while the answer streams, so this ordering is
    # part of the contract.
    _index(service)

    events = _collect(service)
    first_token = next(i for i, e in enumerate(events) if e["event"] == "token")

    assert events[0]["event"] == "sources"
    assert first_token > 0


def test_empty_index_yields_a_no_results_done_event(service):
    events = _collect(service)

    assert len(events) == 1
    assert events[0]["event"] == "done"
    assert events[0]["status"] == "no_results"
    assert events[0]["code"] == ErrorCode.NO_RELEVANT_EVIDENCE


def test_invalid_query_yields_a_structured_validation_error(service):
    events = list(service.stream_query_documents(""))

    assert events[0]["event"] == "error"
    assert events[0]["code"] == ErrorCode.VALIDATION_FAILED


def test_model_unavailable_is_reported_as_a_structured_error(service):
    _index(service)
    service.generation = StubGeneration(error=ModelUnavailableError("model is not available"))

    events = _collect(service)

    error = events[-1]
    assert error["event"] == "error"
    assert error["code"] == ErrorCode.MODEL_UNAVAILABLE
    # The plan requires actionable failures be distinguishable.
    assert error["actionable"] is True


def test_cancellation_stops_generation_and_reports_cancelled(service):
    _index(service)
    cancel = threading.Event()
    cancel.set()

    events = _collect(service, cancel=cancel)

    assert events[-1]["event"] == "error"
    assert events[-1]["code"] == ErrorCode.CANCELLED


def test_cancel_event_is_passed_through_to_the_client(service):
    _index(service)
    cancel = threading.Event()

    _collect(service, cancel=cancel)

    assert service.generation.seen_cancel is cancel


def test_truncated_document_count_is_reported(service):
    _index(service)
    service.context_token_budget = 1

    sources = _collect(service)[0]

    assert sources["event"] == "sources"
    assert sources["truncated_document_count"] == 0


def test_answer_mode_controls_generation_cap(service):
    _index(service)

    _collect(service, answer_mode="fast")

    assert service.generation.seen_max_tokens == 160

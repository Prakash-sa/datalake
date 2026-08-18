"""Ollama client generation: parsing, error classification, and cancellation."""

from __future__ import annotations

import json
import threading
from contextlib import contextmanager

import pytest

from rag_backend.errors import (
    ErrorCode,
    GenerationTimeoutError,
    ModelUnavailableError,
    RagError,
    classify_ollama_exception,
)
from rag_backend.infrastructure import ollama_client
from rag_backend.infrastructure.ollama_client import OllamaClient


@pytest.fixture
def client() -> OllamaClient:
    return OllamaClient("http://127.0.0.1:11434/", ["embed", "llm"])


@contextmanager
def _fake_urlopen(monkeypatch, lines: list[bytes] | None = None, exc: Exception | None = None):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def __iter__(self):
            return iter(lines or [])

        def read(self):
            return b"".join(lines or [])

    def fake(request, timeout=None):
        if exc:
            raise exc
        return FakeResponse()

    monkeypatch.setattr(ollama_client.urllib.request, "urlopen", fake)
    yield


def test_base_url_trailing_slash_is_normalized(client):
    assert client.base_url == "http://127.0.0.1:11434"


def test_generate_returns_the_response_field(monkeypatch, client):
    with _fake_urlopen(monkeypatch, [json.dumps({"response": "hello"}).encode()]):
        assert client.generate("prompt", model="llm") == "hello"


def test_generate_raises_model_unavailable_on_an_error_payload(monkeypatch, client):
    with (
        _fake_urlopen(monkeypatch, [json.dumps({"error": "model not found"}).encode()]),
        pytest.raises(ModelUnavailableError) as excinfo,
    ):
        client.generate("prompt", model="llm")

    assert excinfo.value.code is ErrorCode.MODEL_UNAVAILABLE


def test_generate_maps_a_timeout_to_a_structured_error(monkeypatch, client):
    with (
        _fake_urlopen(monkeypatch, exc=TimeoutError("timed out")),
        pytest.raises(GenerationTimeoutError),
    ):
        client.generate("prompt", model="llm")


def test_stream_generate_yields_tokens_in_order(monkeypatch, client):
    lines = [
        json.dumps({"response": "a", "done": False}).encode(),
        json.dumps({"response": "b", "done": False}).encode(),
        json.dumps({"response": "c", "done": True}).encode(),
    ]
    with _fake_urlopen(monkeypatch, lines):
        assert list(client.stream_generate("p", model="llm")) == ["a", "b", "c"]


def test_stream_generate_stops_at_the_done_marker(monkeypatch, client):
    lines = [
        json.dumps({"response": "a", "done": True}).encode(),
        json.dumps({"response": "ignored", "done": False}).encode(),
    ]
    with _fake_urlopen(monkeypatch, lines):
        assert list(client.stream_generate("p", model="llm")) == ["a"]


def test_stream_generate_skips_malformed_lines(monkeypatch, client):
    # A partial answer is better than failing the whole generation.
    lines = [
        b"not json",
        b"",
        json.dumps({"response": "ok", "done": True}).encode(),
    ]
    with _fake_urlopen(monkeypatch, lines):
        assert list(client.stream_generate("p", model="llm")) == ["ok"]


def test_stream_generate_honours_cancellation(monkeypatch, client):
    lines = [json.dumps({"response": str(i), "done": False}).encode() for i in range(10)]
    cancel = threading.Event()
    cancel.set()

    with _fake_urlopen(monkeypatch, lines):
        assert list(client.stream_generate("p", model="llm", cancel=cancel)) == []


def test_stream_generate_raises_on_an_error_chunk(monkeypatch, client):
    lines = [json.dumps({"error": "no such model"}).encode()]
    with _fake_urlopen(monkeypatch, lines), pytest.raises(RagError) as excinfo:
        list(client.stream_generate("p", model="llm"))

    assert excinfo.value.code is ErrorCode.MODEL_UNAVAILABLE


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Failed to connect to Ollama.", ErrorCode.MODEL_UNAVAILABLE),
        ("connection refused", ErrorCode.MODEL_UNAVAILABLE),
        ("model not found, try pulling it first", ErrorCode.MODEL_UNAVAILABLE),
        ("request timed out", ErrorCode.GENERATION_TIMEOUT),
        ("something else broke", ErrorCode.GENERATION_FAILED),
    ],
)
def test_exception_classification(message, expected):
    assert classify_ollama_exception(Exception(message)) is expected


def test_timeout_type_classifies_even_without_a_message():
    assert classify_ollama_exception(TimeoutError()) is ErrorCode.GENERATION_TIMEOUT

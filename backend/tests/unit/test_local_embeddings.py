"""Local ONNX embeddings: the provider that removes the Ollama prerequisite."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from rag_backend.errors import EmbeddingError, ErrorCode
from rag_backend.infrastructure.embeddings import (
    OllamaEmbeddingProvider,
    build_embedding_provider,
)
from rag_backend.infrastructure.local_embeddings import (
    DIMENSIONS,
    MODEL_NAME,
    LocalEmbeddings,
)

MODEL_DIR = Path(__file__).resolve().parents[2] / "src" / "rag_backend" / "models" / MODEL_NAME

# The model is a build artifact fetched by scripts/fetch_embedding_model.py, so
# it may be absent in a fresh checkout.
requires_model = pytest.mark.skipif(
    not (MODEL_DIR / "model.onnx").is_file(),
    reason="run scripts/fetch_embedding_model.py to enable local embedding tests",
)


@pytest.fixture(scope="module")
def embedder() -> LocalEmbeddings:
    return LocalEmbeddings(str(MODEL_DIR))


class TestAvailability:
    def test_reports_unavailable_when_the_model_is_missing(self, tmp_path):
        assert LocalEmbeddings(str(tmp_path)).is_available is False

    def test_embedding_without_a_model_raises_an_actionable_error(self, tmp_path):
        with pytest.raises(EmbeddingError) as excinfo:
            LocalEmbeddings(str(tmp_path)).embed_query("hello")

        assert excinfo.value.code is ErrorCode.MODEL_UNAVAILABLE
        assert excinfo.value.actionable is True

    def test_health_reports_no_external_software_requirement(self, tmp_path):
        health = LocalEmbeddings(str(tmp_path)).health()

        assert health["requires_external_software"] is False
        assert health["dimensions"] == DIMENSIONS


@requires_model
class TestEmbedding:
    def test_produces_vectors_of_the_declared_dimension(self, embedder):
        assert len(embedder.embed_query("hello world")) == DIMENSIONS

    def test_vectors_are_unit_length(self, embedder):
        # The Chroma collection uses cosine space, which assumes normalisation.
        vector = embedder.embed_query("local first retrieval")
        norm = math.sqrt(sum(value * value for value in vector))

        assert norm == pytest.approx(1.0, abs=1e-5)

    def test_embedding_is_deterministic(self, embedder):
        # Non-determinism would silently invalidate an existing index.
        assert embedder.embed_query("stable text") == embedder.embed_query("stable text")

    def test_related_text_scores_higher_than_unrelated(self, embedder):
        query = embedder.embed_query("how are search rankings combined?")
        related = embedder.embed_query("reciprocal rank fusion merges two rankings")
        unrelated = embedder.embed_query("bake the cake for forty minutes")

        assert sum(a * b for a, b in zip(query, related, strict=True)) > sum(
            a * b for a, b in zip(query, unrelated, strict=True)
        )

    def test_batch_matches_individual_embedding(self, embedder):
        texts = ["first document", "second document"]

        batch = embedder.embed_documents(texts)

        assert len(batch) == 2
        for vector, text in zip(batch, texts, strict=True):
            assert vector == pytest.approx(embedder.embed_query(text), abs=1e-5)

    def test_padding_does_not_change_a_vector(self, embedder):
        # Mean pooling must ignore padding, or similarity would depend on what
        # else happened to be in the batch.
        alone = embedder.embed_query("short")
        batched = embedder.embed_documents(["short", "a considerably longer passage " * 20])[0]

        assert batched == pytest.approx(alone, abs=1e-5)

    def test_empty_batch_returns_nothing(self, embedder):
        assert embedder.embed_documents([]) == []

    def test_oversized_input_is_truncated_rather_than_failing(self, embedder):
        assert len(embedder.embed_query("word " * 5000)) == DIMENSIONS


class TestProviderSelection:
    def test_local_is_selected_when_the_model_is_present(self, tmp_path):
        if not (MODEL_DIR / "model.onnx").is_file():
            pytest.skip("model not fetched")

        provider = build_embedding_provider(
            "local",
            ollama_model="x",
            ollama_url="http://127.0.0.1:11434",
            local_model_dir=str(MODEL_DIR),
        )

        assert isinstance(provider, LocalEmbeddings)

    def test_falls_back_to_ollama_when_the_local_model_is_missing(self, tmp_path):
        # A bundle missing its model should degrade, not fail to start.
        provider = build_embedding_provider(
            "local",
            ollama_model="nomic-embed-text",
            ollama_url="http://127.0.0.1:11434",
            local_model_dir=str(tmp_path),
        )

        assert isinstance(provider, OllamaEmbeddingProvider)

    def test_ollama_is_selected_when_requested(self, tmp_path):
        provider = build_embedding_provider(
            "ollama",
            ollama_model="nomic-embed-text",
            ollama_url="http://127.0.0.1:11434",
            local_model_dir=str(MODEL_DIR),
        )

        assert isinstance(provider, OllamaEmbeddingProvider)
        assert provider.health()["requires_external_software"] is True

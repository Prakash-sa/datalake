"""Embedding provider selection.

Two providers share one interface:

``local``   ONNX Runtime in-process. No external software; the default.
``ollama``  Delegates to an Ollama daemon, for larger or different models.

They produce different vectors and different dimensions, so switching providers
invalidates the index. That is enforced through the index fingerprint rather
than left to the user to remember.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

from rag_backend.infrastructure.local_embeddings import LocalEmbeddings

logger = logging.getLogger(__name__)

LOCAL = "local"
OLLAMA = "ollama"


@runtime_checkable
class EmbeddingProvider(Protocol):
    """What the RAG service needs from an embedder."""

    model_name: str
    dimensions: int

    def embed_query(self, text: str) -> list[float]: ...

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def health(self) -> dict[str, Any]: ...


class OllamaEmbeddingProvider:
    """Adapter over langchain's Ollama embeddings.

    Wrapped so the rest of the application depends on the provider interface
    rather than on langchain, and so health reporting is uniform.
    """

    def __init__(self, model: str, base_url: str, client: Any = None) -> None:
        from langchain_ollama import OllamaEmbeddings

        self.model_name = model
        self.base_url = base_url
        # Dimensions depend on the remote model and are not known until an
        # embedding is produced; zero means "unknown", which the fingerprint
        # treats as not-a-mismatch.
        self.dimensions = 0
        self._client = client
        self._embeddings = OllamaEmbeddings(model=model, base_url=base_url)

    def embed_query(self, text: str) -> list[float]:
        vector = self._embeddings.embed_query(text)
        if not self.dimensions:
            self.dimensions = len(vector)
        return vector

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def health(self) -> dict[str, Any]:
        status = "unknown"
        if self._client is not None:
            reported = self._client.check_health()
            missing = reported.get("missing_models", [])
            status = (
                "error"
                if reported.get("status") == "error"
                else ("degraded" if self.model_name in missing else "ready")
            )
        return {
            "status": status,
            "provider": OLLAMA,
            "model": self.model_name,
            "dimensions": self.dimensions or None,
            "requires_external_software": True,
        }


def build_embedding_provider(
    provider: str,
    *,
    ollama_model: str,
    ollama_url: str,
    local_model_dir: str,
    ollama_client: Any = None,
) -> EmbeddingProvider:
    """Construct the configured provider.

    An unusable local model falls back to Ollama rather than failing startup,
    so a bundle missing its model is degraded instead of dead.
    """
    if provider == OLLAMA:
        return OllamaEmbeddingProvider(ollama_model, ollama_url, client=ollama_client)

    local = LocalEmbeddings(local_model_dir)
    if local.is_available:
        return local

    logger.warning("Local embedding model missing from %s; falling back to Ollama", local_model_dir)
    return OllamaEmbeddingProvider(ollama_model, ollama_url, client=ollama_client)

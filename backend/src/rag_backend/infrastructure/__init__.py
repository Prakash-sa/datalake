"""Infrastructure layer - adapters for external services and local storage."""

from rag_backend.infrastructure.catalog_store import CatalogStore
from rag_backend.infrastructure.embeddings import (
    EmbeddingProvider,
    build_embedding_provider,
)
from rag_backend.infrastructure.local_embeddings import LocalEmbeddings
from rag_backend.infrastructure.ollama_client import OllamaClient
from rag_backend.infrastructure.vector_store import ChromaVectorStore, normalize_metadata

__all__ = [
    "CatalogStore",
    "ChromaVectorStore",
    "EmbeddingProvider",
    "LocalEmbeddings",
    "OllamaClient",
    "build_embedding_provider",
    "normalize_metadata",
]

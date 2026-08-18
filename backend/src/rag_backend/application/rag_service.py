"""RAG service - orchestrates ingestion, retrieval, and answer generation.

This is a facade over the infrastructure adapters. It owns the shared runtime
state (models, vector store, catalog, counters) and delegates the mechanics of
talking to Chroma and Ollama to :mod:`rag_backend.infrastructure`.
"""

from __future__ import annotations

import hashlib
import logging
import platform
import shutil
import sys
import threading
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from langchain_ollama import OllamaLLM

from rag_backend.application.citations import validate_citations
from rag_backend.application.ingestion_service import (
    CHUNKER_VERSION,
    PARSER_VERSION,
    build_ingested_document,
)
from rag_backend.application.prompts import (
    DEFAULT_CONTEXT_TOKEN_BUDGET,
    GROUNDED_ANSWER_TEMPLATE,
    PROMPT_VERSION,
    build_context,
    select_context_documents,
)
from rag_backend.application.retrieval import (
    RETRIEVAL_VERSION,
    candidate_pool_size,
    fuse_results,
)
from rag_backend.domain.fingerprint import build_fingerprint, compare
from rag_backend.errors import (
    CancelledError,
    ErrorCode,
    IndexModelMismatchError,
    RagError,
    RetrievalError,
    ValidationError,
    classify_ollama_exception,
)
from rag_backend.infrastructure.catalog_store import CatalogStore
from rag_backend.infrastructure.embeddings import build_embedding_provider
from rag_backend.infrastructure.ollama_client import OllamaClient
from rag_backend.infrastructure.vector_store import ChromaVectorStore, normalize_metadata

logger = logging.getLogger(__name__)

DEFAULT_MODEL_PROFILES = {
    "light": {"llm_model": "qwen3:1.7b", "embedding_model": "qwen3-embedding:0.6b"},
    "balanced": {"llm_model": "qwen3:4b", "embedding_model": "qwen3-embedding:0.6b"},
}


class DocumentRAGService:
    """Application service for indexing, searching, and querying documents."""

    MAX_QUERY_LENGTH = 1000
    MIN_SIMILARITY_SCORE = 0.0
    DEFAULT_MODEL_PROFILES = DEFAULT_MODEL_PROFILES
    PROMPT_VERSION = PROMPT_VERSION
    RETRIEVAL_VERSION = RETRIEVAL_VERSION

    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        embedding_model: str = "nomic-embed-text",
        llm_model: str = "mistral",
        temperature: float = 0.3,
        chroma_path: str = "./chroma_db",
        app_db_path: str = "./app.db",
        context_token_budget: int = DEFAULT_CONTEXT_TOKEN_BUDGET,
        embedding_provider: str = "local",
        local_embedding_model_dir: str | None = None,
    ) -> None:
        if not 0.0 <= temperature <= 1.0:
            raise ValueError("Temperature must be between 0.0 and 1.0")

        self.ollama_url = ollama_url
        self.embedding_model = embedding_model
        self.llm_model = llm_model
        self.temperature = temperature
        self.chroma_path = chroma_path
        self.app_db_path = app_db_path
        self.context_token_budget = context_token_budget

        self.catalog = CatalogStore(app_db_path)
        self.embedding_provider_name = embedding_provider
        # Only the generation model is required from Ollama when embeddings run
        # locally, so a missing embedding model must not be reported as missing.
        required = [llm_model] if embedding_provider == "local" else [embedding_model, llm_model]
        self.ollama = OllamaClient(ollama_url, required)
        self.stats = {"documents_indexed": 0, "queries_processed": 0, "errors": 0}

        try:
            self.embeddings = build_embedding_provider(
                embedding_provider,
                ollama_model=embedding_model,
                ollama_url=ollama_url,
                local_model_dir=local_embedding_model_dir
                or str(Path(__file__).resolve().parents[1] / "models" / "all-MiniLM-L6-v2"),
                ollama_client=self.ollama,
            )
            self.llm = OllamaLLM(model=llm_model, base_url=ollama_url, temperature=temperature)
            self.vector_store = ChromaVectorStore(chroma_path)
        except Exception as e:
            logger.error("Failed to initialize RAG components: %s", e, exc_info=True)
            self.stats["errors"] += 1
            raise ConnectionError(f"Failed to initialize RAG components: {e}") from e

        # Report the provider actually in use; naming the configured Ollama
        # model when embeddings run locally is misleading during diagnosis.
        logger.info(
            "RAG service ready (embeddings=%s/%s, generation=%s)",
            self.embedding_provider_name,
            getattr(self.embeddings, "model_name", embedding_model),
            llm_model,
        )

    # -- Models ---------------------------------------------------------------

    def list_ollama_models(self) -> dict[str, Any]:
        """List installed and required Ollama models."""
        return self.ollama.list_models()

    def pull_ollama_model(self, name: str) -> dict[str, Any]:
        """Pull a local Ollama model."""
        return self.ollama.pull_model(name)

    # -- Settings -------------------------------------------------------------

    def get_settings(self) -> dict[str, Any]:
        """Return persisted runtime settings layered over the active defaults."""
        stored = self.catalog.get_setting("runtime", {})
        return {
            "ollama_url": stored.get("ollama_url", self.ollama_url),
            "embedding_model": stored.get("embedding_model", self.embedding_model),
            "llm_model": stored.get("llm_model", self.llm_model),
            "temperature": stored.get("temperature", self.temperature),
            "model_profiles": DEFAULT_MODEL_PROFILES,
        }

    def update_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        """Persist runtime settings. Model changes apply on next backend restart."""
        current = self.get_settings()
        for key in ("ollama_url", "embedding_model", "llm_model", "temperature"):
            if settings.get(key) is not None:
                current[key] = settings[key]
        self.catalog.set_setting("runtime", current)
        return {"status": "success", "settings": current, "restart_required": True}

    # -- Indexing -------------------------------------------------------------

    def index_documents(self, documents: list[dict[str, Any]]) -> dict[str, Any]:
        """Embed and upsert documents into the vector store."""
        if not documents:
            return {"status": "success", "documents_indexed": 0}

        compatibility = self.check_index_compatibility()
        if compatibility["rebuild_required"]:
            if self.vector_store.count() == 0:
                # An empty index has nothing worth preserving, so adopt the new
                # configuration rather than making the user ask for a rebuild.
                self.reset_index()
            else:
                changed = ", ".join(compatibility["changed"])
                logger.warning("Index incompatible with current config (%s)", changed)
                self.stats["errors"] += 1
                return {
                    "status": "error",
                    "code": str(ErrorCode.INDEX_MODEL_MISMATCH),
                    "error": (
                        f"The existing index was built with a different embedding "
                        f"configuration ({changed}). Rebuild the index to continue."
                    ),
                }

        try:
            logger.info("Indexing %d documents", len(documents))
            errors: list[str] = []
            ids: list[str] = []
            contents: list[str] = []
            metadatas: list[dict[str, Any]] = []
            embeddings: list[list[float]] = []

            for idx, doc in enumerate(documents):
                try:
                    doc_id = doc.get("id", "")
                    content = doc.get("content", "")
                    if not doc_id or not content:
                        errors.append(f"Document {idx}: missing 'id' or 'content'")
                        continue

                    # Embed before appending anything. These four lists are
                    # positionally paired, so a failure mid-append would offset
                    # embeddings against content and silently mis-index the
                    # remaining documents.
                    embedding = self.embeddings.embed_query(content)
                    metadata = normalize_metadata(doc.get("metadata", {}))
                    metadata["id"] = doc_id

                    ids.append(doc_id)
                    contents.append(content)
                    metadatas.append(metadata)
                    embeddings.append(embedding)
                except Exception as e:
                    errors.append(f"Document {idx}: {e}")
                    logger.warning("Failed to index document %d: %s", idx, e)

            # Compare what is about to be written against what the collection
            # already holds. This is exact and needs no provider to declare its
            # width, which covers a provider whose dimensions are unknown until
            # it has embedded once.
            if embeddings:
                stored_width = self.vector_store.dimension()
                new_width = len(embeddings[0])
                if stored_width is not None and stored_width != new_width:
                    if self.vector_store.count() == 0:
                        # The collection is empty but still carries the width it
                        # was created with, so nothing is lost by recreating it.
                        # Requiring a manual rebuild here would be friction with
                        # no data at stake.
                        logger.info(
                            "Recreating an empty %d-dim collection for %d-dim vectors",
                            stored_width,
                            new_width,
                        )
                        self.reset_index()
                    else:
                        logger.warning(
                            "Index holds %d-dim vectors but the model produces %d",
                            stored_width,
                            new_width,
                        )
                        self.stats["errors"] += 1
                        return {
                            "status": "error",
                            "code": str(ErrorCode.INDEX_MODEL_MISMATCH),
                            "error": (
                                f"The existing index holds {stored_width}-dimension "
                                f"vectors but the current embedding model produces "
                                f"{new_width}. Rebuild the index to continue."
                            ),
                        }

            try:
                self.vector_store.upsert(ids, contents, metadatas, embeddings)
            except IndexModelMismatchError as mismatch:
                if self.vector_store.count() > 0:
                    self.stats["errors"] += 1
                    return {"status": "error", **mismatch.to_dict()}
                # An empty collection still carries the width it was created
                # with. Nothing is at stake, so adopt the new one and retry once
                # rather than making the user request a rebuild.
                logger.info("Recreating an empty collection with a new vector width")
                self.reset_index()
                self.vector_store.upsert(ids, contents, metadatas, embeddings)

            self.stats["documents_indexed"] += len(ids)
            if ids:
                # Stamp the index so a later model change is detectable.
                self.record_fingerprint()

            return {
                "status": "partial_success" if errors else "success",
                "documents_indexed": len(ids),
                "errors": errors or None,
            }
        except Exception as e:
            logger.error("Document indexing failed: %s", e, exc_info=True)
            self.stats["errors"] += 1
            return {"status": "error", "error": str(e)}

    def ingest_file(self, file_path: str, force_reindex: bool = False) -> dict[str, Any]:
        """Parse, chunk, persist, and index a local file."""
        try:
            path = Path(file_path).expanduser().resolve()
            ingested = build_ingested_document(path, self.embedding_model, self.llm_model)
            document = ingested["document"]
            chunks = ingested["chunks"]

            existing = self.catalog.get_document_by_hash(document["source_hash"])
            if existing and not force_reindex:
                return {
                    "status": "duplicate",
                    "document": existing,
                    "chunks_indexed": existing.get("chunk_count", 0),
                }

            index_result = self.index_documents(
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
                return index_result

            self.catalog.upsert_document(document, chunks)
            return {
                "status": "success",
                "document": document,
                "chunks_indexed": len(chunks),
                "index_result": index_result,
            }
        except Exception as e:
            logger.error("File ingestion failed: %s", e, exc_info=True)
            self.stats["errors"] += 1
            return {"status": "error", "error": str(e)}

    def list_documents(self) -> list[dict[str, Any]]:
        """List indexed source documents from the local catalog."""
        return self.catalog.list_documents()

    def delete_document(self, document_id: str) -> dict[str, Any]:
        """Delete catalog rows and vector chunks for a source document."""
        try:
            chunk_ids = self.catalog.get_chunk_ids(document_id)
            self.vector_store.delete(chunk_ids)
            deleted = self.catalog.delete_document(document_id)
            return {
                "status": "success" if deleted else "not_found",
                "document_id": document_id,
                "chunks_deleted": len(chunk_ids),
            }
        except Exception as e:
            logger.error("Document delete failed: %s", e, exc_info=True)
            self.stats["errors"] += 1
            return {"status": "error", "error": str(e)}

    # -- Retrieval ------------------------------------------------------------

    def search_documents(
        self, query: str, k: int = 5, min_score: float | None = None
    ) -> list[dict[str, Any]]:
        """Search using dense vectors fused with SQLite FTS via RRF."""
        try:
            if not query or len(query) > self.MAX_QUERY_LENGTH:
                raise ValueError(f"Query must be 1-{self.MAX_QUERY_LENGTH} characters")
            if not 1 <= k <= 100:
                raise ValueError("k must be between 1 and 100")

            if min_score is None:
                min_score = self.MIN_SIMILARITY_SCORE
            if not 0.0 <= min_score <= 1.0:
                raise ValueError("min_score must be between 0.0 and 1.0")

            collection_count = self.vector_store.count()
            if collection_count == 0:
                logger.debug("No documents in the vector store")
                return []

            candidates = candidate_pool_size(k, collection_count)
            matches = self.vector_store.query(
                self.embeddings.embed_query(query), n_results=candidates
            )

            dense_ranked = [
                {
                    "id": match["id"],
                    "content": match["content"],
                    "metadata": match["metadata"],
                    "relevance_score": round(float(match["similarity"]), 3),
                    "retrieval_source": "dense",
                }
                for match in matches
                if match["similarity"] >= min_score
            ]

            lexical_ranked = [
                {
                    "id": item["id"],
                    "content": item["content"],
                    "metadata": item["metadata"],
                    "relevance_score": 0.0,
                    "retrieval_source": "fts",
                }
                for item in self.catalog.search_fts(query, limit=candidates)
            ]

            return fuse_results(dense_ranked, lexical_ranked)[:k]
        except ValueError as e:
            logger.warning("Search validation error: %s", e)
            raise
        except Exception as e:
            logger.error("Document search failed: %s", e, exc_info=True)
            return []

    def query_documents(
        self, user_query: str, k: int = 5, min_score: float | None = None
    ) -> dict[str, Any]:
        """Execute the RAG pipeline: retrieve context, then generate an answer."""
        try:
            if not user_query or len(user_query) > self.MAX_QUERY_LENGTH:
                raise ValueError(f"Query must be 1-{self.MAX_QUERY_LENGTH} characters")

            start_time = datetime.now()
            relevant_docs = self.search_documents(user_query, k=k, min_score=min_score)

            if not relevant_docs:
                elapsed = (datetime.now() - start_time).total_seconds()
                self._record_query_trace(
                    user_query, [], "no_results", {"total_seconds": round(elapsed, 3)}
                )
                return {
                    "status": "no_results",
                    "query": user_query,
                    "answer": "No relevant documents found in the knowledge base.",
                    "retrieved_documents": [],
                    "document_count": 0,
                    "processing_time_seconds": round(elapsed, 2),
                }

            # Only the documents that fit the budget are sent to the model, so
            # citations must be validated against this list, not the full result.
            context_docs = select_context_documents(
                relevant_docs, token_budget=self.context_token_budget
            )
            context = build_context(context_docs)

            degraded_code: str | None = None
            try:
                answer = self.llm.invoke(
                    GROUNDED_ANSWER_TEMPLATE.format(context=context, query=user_query)
                )
            except Exception as llm_error:
                # Degrade to context-only so retrieval stays usable without a
                # loaded generation model.
                degraded_code = str(classify_ollama_exception(llm_error))
                logger.warning("Generation unavailable (%s): %s", degraded_code, llm_error)
                answer = f"Based on {len(context_docs)} relevant document(s):\n\n{context}"

            answer = answer.strip() if answer else "No answer generated"
            citations = validate_citations(answer, context_docs)
            if not citations["valid"]:
                # The model cited a source it was never given. Surface it rather
                # than rendering a citation that resolves to nothing.
                logger.warning(
                    "Answer cited %d source(s) outside the supplied range",
                    len(citations["invalid_indices"]),
                )

            elapsed = (datetime.now() - start_time).total_seconds()
            self.stats["queries_processed"] += 1
            self._record_query_trace(
                user_query,
                context_docs,
                "degraded" if degraded_code else "success",
                {"total_seconds": round(elapsed, 3)},
                error_code=degraded_code,
                citation_count=citations["citation_count"],
            )

            return {
                "status": "degraded" if degraded_code else "success",
                "query": user_query,
                "answer": answer,
                "retrieved_documents": context_docs,
                "document_count": len(context_docs),
                "processing_time_seconds": round(elapsed, 2),
                "citations": citations,
                # Documents retrieved but dropped by the context budget.
                "truncated_document_count": len(relevant_docs) - len(context_docs),
                **({"code": degraded_code} if degraded_code else {}),
            }
        except ValueError as e:
            logger.warning("Query validation error: %s", e)
            self.stats["errors"] += 1
            self._record_query_trace(user_query, [], "error", {}, error_code="validation")
            raise
        except Exception as e:
            logger.error("Document query failed: %s", e, exc_info=True)
            self.stats["errors"] += 1
            self._record_query_trace(user_query, [], "error", {}, error_code="query_failed")
            return {"status": "error", "query": user_query, "error": str(e)}

    def stream_query_documents(
        self,
        user_query: str,
        k: int = 5,
        min_score: float | None = None,
        cancel: threading.Event | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Run the RAG pipeline, yielding events as generation progresses.

        Event shapes, in order:
          {"event": "sources", "documents": [...], "truncated_document_count": n}
          {"event": "token",  "text": "..."}                      (repeated)
          {"event": "done",   "answer": "...", "citations": {...}}
          {"event": "error",  "code": "...", "error": "..."}      (terminal)

        Sources are emitted before the first token so the UI can render
        citations while the answer streams in.
        """
        start_time = datetime.now()

        try:
            if not user_query or len(user_query) > self.MAX_QUERY_LENGTH:
                raise ValidationError(f"Query must be 1-{self.MAX_QUERY_LENGTH} characters")
            relevant_docs = self.search_documents(user_query, k=k, min_score=min_score)
        except ValidationError as e:
            self.stats["errors"] += 1
            self._record_query_trace(user_query, [], "error", {}, error_code=str(e.code))
            yield {"event": "error", **e.to_dict()}
            return
        except Exception as e:
            logger.error("Retrieval failed: %s", e, exc_info=True)
            self.stats["errors"] += 1
            error = RetrievalError(str(e))
            self._record_query_trace(user_query, [], "error", {}, error_code=str(error.code))
            yield {"event": "error", **error.to_dict()}
            return

        if not relevant_docs:
            elapsed = (datetime.now() - start_time).total_seconds()
            self._record_query_trace(
                user_query, [], "no_results", {"total_seconds": round(elapsed, 3)}
            )
            yield {
                "event": "done",
                "status": "no_results",
                "code": str(ErrorCode.NO_RELEVANT_EVIDENCE),
                "answer": "No relevant documents found in the knowledge base.",
                "retrieved_documents": [],
                "citations": validate_citations("", []),
                "processing_time_seconds": round(elapsed, 2),
            }
            return

        context_docs = select_context_documents(
            relevant_docs, token_budget=self.context_token_budget
        )
        yield {
            "event": "sources",
            "documents": context_docs,
            "truncated_document_count": len(relevant_docs) - len(context_docs),
        }

        prompt = GROUNDED_ANSWER_TEMPLATE.format(
            context=build_context(context_docs), query=user_query
        )

        parts: list[str] = []
        try:
            for token in self.ollama.stream_generate(
                prompt,
                model=self.llm_model,
                temperature=self.temperature,
                cancel=cancel,
            ):
                parts.append(token)
                yield {"event": "token", "text": token}
        except RagError as e:
            self.stats["errors"] += 1
            self._record_query_trace(user_query, context_docs, "error", {}, error_code=str(e.code))
            yield {"event": "error", **e.to_dict()}
            return

        elapsed = (datetime.now() - start_time).total_seconds()

        if cancel is not None and cancel.is_set():
            self._record_query_trace(
                user_query,
                context_docs,
                "cancelled",
                {"total_seconds": round(elapsed, 3)},
                error_code=str(ErrorCode.CANCELLED),
            )
            yield {
                "event": "error",
                **CancelledError("Generation cancelled").to_dict(),
            }
            return

        answer = "".join(parts).strip()
        citations = validate_citations(answer, context_docs)
        self.stats["queries_processed"] += 1
        self._record_query_trace(
            user_query,
            context_docs,
            "success",
            {"total_seconds": round(elapsed, 3)},
            citation_count=citations["citation_count"],
        )

        yield {
            "event": "done",
            "status": "success",
            "answer": answer,
            "retrieved_documents": context_docs,
            "document_count": len(context_docs),
            "citations": citations,
            "truncated_document_count": len(relevant_docs) - len(context_docs),
            "processing_time_seconds": round(elapsed, 2),
        }

    def _record_query_trace(
        self,
        query: str,
        documents: list[dict[str, Any]],
        status: str,
        latency: dict[str, Any],
        error_code: str | None = None,
        citation_count: int = 0,
    ) -> None:
        """Persist a privacy-safe trace: query is hashed, content never stored."""
        try:
            now = datetime.now(UTC)
            self.catalog.record_query_trace(
                {
                    "id": f"query_{now.strftime('%Y%m%d%H%M%S%f')}",
                    "query_hash": hashlib.sha256(query.encode("utf-8")).hexdigest(),
                    "prompt_version": PROMPT_VERSION,
                    "retrieval_version": RETRIEVAL_VERSION,
                    "embedding_model": self.embedding_model,
                    "llm_model": self.llm_model,
                    "chunk_ids": [doc.get("id") for doc in documents],
                    "scores": [doc.get("relevance_score") for doc in documents],
                    "latency": {**latency, "citation_count": citation_count},
                    "status": status,
                    "error_code": error_code,
                }
            )
        except Exception as e:
            logger.debug("Query trace persistence failed: %s", e)

    # -- Index fingerprint ----------------------------------------------------

    def current_fingerprint(self) -> dict[str, Any]:
        """Describe the configuration this process would index with."""
        local = self.embedding_provider_name == "local"
        return build_fingerprint(
            embedding_provider=self.embedding_provider_name,
            embedding_model=getattr(self.embeddings, "model_name", self.embedding_model),
            embedding_dimensions=getattr(self.embeddings, "dimensions", None) or None,
            # A local model has no Ollama digest; its identity is the model name
            # and dimensions, which are already compared.
            embedding_digest=None if local else self.ollama.model_digest(self.embedding_model),
            chunker_version=CHUNKER_VERSION,
            parser_version=PARSER_VERSION,
        )

    def stored_fingerprint(self) -> dict[str, Any] | None:
        """The fingerprint recorded when the index was last written."""
        stored = self.catalog.get_setting("index_fingerprint", None)
        return stored or None

    def record_fingerprint(self) -> dict[str, Any]:
        """Persist the current configuration as the index's fingerprint."""
        fingerprint = self.current_fingerprint()
        self.catalog.set_setting("index_fingerprint", fingerprint)
        return fingerprint

    def reset_index(self) -> dict[str, Any]:
        """Recreate the vector collection and stamp it with the current config.

        Used when the embedding model changes: the old vectors cannot be
        compared against new queries, and the collection cannot accept vectors
        of a different width.
        """
        self.vector_store.reset()
        fingerprint = self.record_fingerprint()
        logger.info("Vector index reset for %s", fingerprint["embedding_model"])
        return fingerprint

    def check_index_compatibility(self) -> dict[str, Any]:
        """Report whether existing vectors match the running configuration.

        The recorded fingerprint is not sufficient on its own: an index written
        before fingerprints existed has none, yet its vectors still have a fixed
        width. The stored vectors are therefore measured directly, which is
        ground truth and covers the upgrade case the fingerprint cannot.
        """
        current = self.current_fingerprint()
        stored = self.stored_fingerprint()
        result = compare(stored, current)

        actual = self.vector_store.dimension()
        expected = current.get("embedding_dimensions")
        if actual is not None and expected and actual != expected:
            changed = sorted({*result["changed"], "embedding_dimensions"})
            result = {
                **result,
                "status": "mismatch",
                "rebuild_required": True,
                "changed": changed,
            }

        return {
            **result,
            "current": current,
            "stored": stored,
            "stored_dimensions": actual,
        }

    # -- Observability --------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Engine counters plus current index sizes."""
        return {
            **self.stats,
            "total_documents": self.vector_store.count(),
            "catalog_documents": len(self.catalog.list_documents()),
            "timestamp": datetime.now().isoformat(),
        }

    def get_diagnostics(self) -> dict[str, Any]:
        """Local diagnostics for support, excluding document text and prompts."""
        data_dir = Path(self.app_db_path).parent
        usage = shutil.disk_usage(data_dir)
        return {
            "status": "success",
            "runtime": {
                "python_version": sys.version.split()[0],
                "platform": platform.platform(),
            },
            "paths": {
                "app_data_dir": str(data_dir),
                "app_db_path": self.app_db_path,
                "chroma_path": self.chroma_path,
            },
            "disk": {
                "total_bytes": usage.total,
                "used_bytes": usage.used,
                "free_bytes": usage.free,
            },
            "models": {
                "ollama_url": self.ollama_url,
                "embedding_model": self.embedding_model,
                "llm_model": self.llm_model,
            },
            "storage": self.vector_store.check_storage(),
            "stats": self.get_stats(),
        }

    def get_readiness(self) -> dict[str, Any]:
        """Report production operating capabilities."""
        stats = self.get_stats()
        memory = self.vector_store.check_storage()
        ollama = self.ollama.check_health()
        ready = memory["status"] == "ready" and ollama["status"] == "ready"

        return {
            "status": "ready" if ready else "degraded",
            "capabilities": {
                "loop_engineering": {
                    "status": "enabled",
                    "signals": [
                        "queries_processed",
                        "errors",
                        "processing_time_seconds",
                        "retrieved_documents",
                    ],
                },
                "memory": {
                    **memory,
                    "documents": stats["total_documents"],
                    "catalog_documents": stats["catalog_documents"],
                    "catalog_path": self.app_db_path,
                },
                "ollama": ollama,
                "embeddings": self.embeddings.health(),
                "index": self.check_index_compatibility(),
                "eval": {
                    "status": "enabled",
                    "endpoint": "/eval",
                    "checks": ["answer_contains", "min_documents", "min_relevance"],
                },
                "open_source": {
                    "status": "prepared",
                    "assets": ["LICENSE", "CONTRIBUTING.md", "SECURITY.md"],
                },
            },
            "stats": stats,
        }

"""
RAG Service - Application use cases and orchestration
"""

import logging
import os
import json
import urllib.error
import urllib.request
from typing import Any, List, Dict
from datetime import datetime
from pathlib import Path

import chromadb
from langchain_ollama import OllamaEmbeddings, OllamaLLM
from langchain_core.prompts import ChatPromptTemplate

from domain.models import SearchResult
from application.ingestion_service import build_ingested_document
from infrastructure.catalog_store import CatalogStore

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class DocumentRAGService:
    """
    Application service for RAG operations.
    Handles use cases: index, search, and query documents.
    """

    MAX_DOCUMENTS = 10000
    MIN_SIMILARITY_SCORE = 0.0
    MAX_QUERY_LENGTH = 1000
    DEFAULT_TIMEOUT = 30
    DEFAULT_MODEL_PROFILES = {
        "light": {
            "llm_model": "qwen3:1.7b",
            "embedding_model": "qwen3-embedding:0.6b",
        },
        "balanced": {
            "llm_model": "qwen3:4b",
            "embedding_model": "qwen3-embedding:0.6b",
        },
    }

    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        embedding_model: str = "nomic-embed-text",
        llm_model: str = "mistral",
        temperature: float = 0.3,
        chroma_path: str = "./chroma_db",
        app_db_path: str = "./app.db",
    ):
        """Initialize RAG service with Chroma vector database."""
        if not 0.0 <= temperature <= 1.0:
            raise ValueError("Temperature must be between 0.0 and 1.0")

        self.ollama_url = ollama_url
        self.embedding_model = embedding_model
        self.llm_model = llm_model
        self.temperature = temperature
        self.chroma_path = chroma_path
        self.app_db_path = app_db_path
        self.embeddings = None
        self.llm = None
        self.chroma_client = None
        self.chroma_collection = None
        self.catalog = CatalogStore(app_db_path)
        self.documents_store: Dict[str, Dict] = {}
        self.stats = {"documents_indexed": 0, "queries_processed": 0, "errors": 0}
        self._initialize_components()

    @staticmethod
    def _normalize_metadata(metadata: Dict) -> Dict:
        """Keep only Chroma-compatible primitive metadata values."""
        normalized = {}
        for key, value in (metadata or {}).items():
            if value is None:
                continue
            if isinstance(value, (str, int, float, bool)):
                normalized[str(key)] = value
            else:
                normalized[str(key)] = str(value)
        return normalized

    def _initialize_components(self) -> None:
        """Initialize RAG components including Chroma vector DB."""
        try:
            self.embeddings = OllamaEmbeddings(
                model=self.embedding_model, base_url=self.ollama_url
            )
            logger.info(f"✅ Embedding model ({self.embedding_model}) initialized")

            self.llm = OllamaLLM(
                model=self.llm_model,
                base_url=self.ollama_url,
                temperature=self.temperature,
            )
            logger.info(f"✅ LLM ({self.llm_model}) initialized")

            # Initialize Chroma client
            Path(self.chroma_path).mkdir(parents=True, exist_ok=True)
            self.chroma_client = chromadb.PersistentClient(path=self.chroma_path)
            logger.info(f"✅ Chroma client initialized at {self.chroma_path}")

            # Get or create documents collection
            self.chroma_collection = self.chroma_client.get_or_create_collection(
                name="documents", metadata={"hnsw:space": "cosine"}
            )
            logger.info("✅ Chroma 'documents' collection ready")

        except Exception as e:
            logger.error(f"❌ Failed to initialize RAG components: {e}", exc_info=True)
            self.stats["errors"] += 1
            raise ConnectionError(f"Failed to initialize RAG components: {e}") from e

    def _check_chroma_storage(self) -> Dict[str, Any]:
        """Verify the vector storage path exists and is writable."""
        try:
            chroma_dir = Path(self.chroma_path)
            chroma_dir.mkdir(parents=True, exist_ok=True)
            probe = chroma_dir / ".readiness_check"
            probe.write_text(datetime.now().isoformat(), encoding="utf-8")
            probe.unlink(missing_ok=True)
            return {
                "status": "ready",
                "provider": "chroma",
                "persistent_path": str(chroma_dir),
                "writable": True,
            }
        except Exception as e:
            logger.warning(f"Chroma storage readiness failed: {e}")
            return {
                "status": "error",
                "provider": "chroma",
                "persistent_path": self.chroma_path,
                "writable": False,
                "error": str(e),
            }

    def _check_ollama(self) -> Dict[str, Any]:
        """Check Ollama availability and required model presence."""
        tags_url = f"{self.ollama_url.rstrip('/')}/api/tags"
        required_models = [self.embedding_model, self.llm_model]

        try:
            request = urllib.request.Request(tags_url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(request, timeout=3) as response:
                payload = json.loads(response.read().decode("utf-8"))

            models = payload.get("models", [])
            installed = {
                model.get("name") or model.get("model")
                for model in models
                if model.get("name") or model.get("model")
            }
            installed_aliases = installed | {model.split(":", 1)[0] for model in installed}
            missing = [model for model in required_models if model not in installed_aliases]

            return {
                "status": "ready" if not missing else "degraded",
                "url": self.ollama_url,
                "required_models": required_models,
                "installed_models": sorted(installed),
                "missing_models": missing,
            }
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            logger.warning(f"Ollama readiness failed: {e}")
            return {
                "status": "error",
                "url": self.ollama_url,
                "required_models": required_models,
                "installed_models": [],
                "missing_models": required_models,
                "error": str(e),
            }

    def list_ollama_models(self) -> dict:
        """List installed Ollama models and missing required models."""
        readiness = self._check_ollama()
        installed_models = readiness.get("installed_models", [])
        return {
            "status": readiness.get("status", "error"),
            "ollama_url": self.ollama_url,
            "models": [{"name": model} for model in installed_models],
            "required_models": readiness.get("required_models", []),
            "missing_models": readiness.get("missing_models", []),
            "error": readiness.get("error"),
        }

    def pull_ollama_model(self, name: str) -> dict:
        """Pull an Ollama model with a non-streaming request."""
        try:
            payload = json.dumps({"name": name, "stream": False}).encode("utf-8")
            request = urllib.request.Request(
                f"{self.ollama_url.rstrip('/')}/api/pull",
                data=payload,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=60 * 60) as response:
                result = json.loads(response.read().decode("utf-8") or "{}")
            return {"status": "success", "model": name, "result": result}
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            return {"status": "error", "model": name, "error": str(e)}

    def get_settings(self) -> dict:
        """Return persisted runtime settings with active defaults."""
        stored = self.catalog.get_setting("runtime", {})
        return {
            "ollama_url": stored.get("ollama_url", self.ollama_url),
            "embedding_model": stored.get("embedding_model", self.embedding_model),
            "llm_model": stored.get("llm_model", self.llm_model),
            "temperature": stored.get("temperature", self.temperature),
            "model_profiles": self.DEFAULT_MODEL_PROFILES,
        }

    def update_settings(self, settings: Dict[str, Any]) -> dict:
        """Persist runtime settings. Model changes apply on next backend restart."""
        current = self.get_settings()
        for key in ("ollama_url", "embedding_model", "llm_model", "temperature"):
            if settings.get(key) is not None:
                current[key] = settings[key]
        self.catalog.set_setting("runtime", current)
        return {
            "status": "success",
            "settings": current,
            "restart_required": True,
        }

    def index_documents(self, documents: List[dict]) -> dict:
        """Index documents into the vector store."""
        if not documents:
            return {"status": "success", "documents_indexed": 0}

        try:
            logger.info(f"📄 Indexing {len(documents)} documents...")
            indexed_count = 0
            errors = []

            ids = []
            contents = []
            metadatas = []
            embeddings = []

            for idx, doc in enumerate(documents):
                try:
                    doc_id = doc.get("id", "")
                    content = doc.get("content", "")

                    if not doc_id or not content:
                        errors.append(f"Document {idx}: missing 'id' or 'content'")
                        continue

                    embedding = self.embeddings.embed_query(content)
                    metadata = self._normalize_metadata(doc.get("metadata", {}))
                    metadata["id"] = doc_id

                    self.documents_store[doc_id] = {
                        "content": content,
                        "embedding": embedding,
                        "metadata": metadata,
                    }

                    ids.append(doc_id)
                    contents.append(content)
                    metadatas.append(metadata)
                    embeddings.append(embedding)
                    indexed_count += 1

                except Exception as e:
                    errors.append(f"Document {idx}: {str(e)}")
                    logger.warning(f"Failed to index document {idx}: {e}")

            if ids:
                self.chroma_collection.upsert(
                    ids=ids,
                    documents=contents,
                    metadatas=metadatas,
                    embeddings=embeddings,
                )

            self.stats["documents_indexed"] += indexed_count
            return {
                "status": "partial_success" if errors else "success",
                "documents_indexed": indexed_count,
                "errors": errors if errors else None,
            }
        except Exception as e:
            logger.error(f"❌ Document indexing failed: {e}", exc_info=True)
            self.stats["errors"] += 1
            return {"status": "error", "error": str(e)}

    def ingest_file(self, file_path: str, force_reindex: bool = False) -> dict:
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

            index_payload = [
                {
                    "id": chunk["id"],
                    "content": chunk["content"],
                    "metadata": chunk["metadata"],
                }
                for chunk in chunks
            ]
            index_result = self.index_documents(index_payload)
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
            logger.error(f"❌ File ingestion failed: {e}", exc_info=True)
            self.stats["errors"] += 1
            return {"status": "error", "error": str(e)}

    def list_documents(self) -> List[dict]:
        """List indexed source documents from the local catalog."""
        return self.catalog.list_documents()

    def delete_document(self, document_id: str) -> dict:
        """Delete catalog rows and vector chunks for a source document."""
        try:
            chunk_ids = self.catalog.get_chunk_ids(document_id)
            if chunk_ids and self.chroma_collection:
                self.chroma_collection.delete(ids=chunk_ids)
            deleted = self.catalog.delete_document(document_id)
            return {
                "status": "success" if deleted else "not_found",
                "document_id": document_id,
                "chunks_deleted": len(chunk_ids),
            }
        except Exception as e:
            logger.error(f"❌ Document delete failed: {e}", exc_info=True)
            self.stats["errors"] += 1
            return {"status": "error", "error": str(e)}

    def search_documents(
        self, query: str, k: int = 5, min_score: float = None
    ) -> List[dict]:
        """Search for relevant documents in Chroma vector database."""
        try:
            if not query or len(query) > self.MAX_QUERY_LENGTH:
                raise ValueError(f"Query must be 1-{self.MAX_QUERY_LENGTH} characters")
            if not 1 <= k <= 100:
                raise ValueError("k must be between 1 and 100")

            if min_score is None:
                min_score = self.MIN_SIMILARITY_SCORE
            if not 0.0 <= min_score <= 1.0:
                raise ValueError("min_score must be between 0.0 and 1.0")

            logger.info(f"🔍 Searching Chroma for: {query}")

            if not self.chroma_collection:
                logger.warning("❌ Chroma collection not initialized")
                return []

            # Check collection count
            collection_count = self.chroma_collection.count()
            logger.info(f"📊 Chroma collection has {collection_count} documents")

            if collection_count == 0:
                logger.debug("No documents in Chroma collection")
                return []

            query_embedding = self.embeddings.embed_query(query)
            results = self.chroma_collection.query(
                query_embeddings=[query_embedding],
                n_results=k,
                include=["documents", "metadatas", "distances"],
            )

            documents = []
            for doc_text, metadata, distance in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                similarity = 1 - distance  # Convert distance to similarity
                if similarity >= min_score:
                    documents.append(
                        {
                            "id": metadata.get("id", "doc"),
                            "content": doc_text,
                            "metadata": metadata,
                            "relevance_score": round(float(similarity), 3),
                        }
                    )

            return documents
        except ValueError as e:
            logger.warning(f"⚠️  Search validation error: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Document search failed: {e}", exc_info=True)
            return []

    def query_documents(
        self,
        user_query: str,
        k: int = 5,
        timeout: int = 30,
        min_score: float = None,
    ) -> dict:
        """Execute RAG pipeline: search documents, retrieve context, generate response."""
        try:
            if not user_query or len(user_query) > self.MAX_QUERY_LENGTH:
                raise ValueError(f"Query must be 1-{self.MAX_QUERY_LENGTH} characters")

            logger.info(f"📝 Processing query: {user_query[:100]}...")
            start_time = datetime.now()

            # Search for relevant documents
            relevant_docs = self.search_documents(user_query, k=k, min_score=min_score)

            if not relevant_docs:
                processing_time = (datetime.now() - start_time).total_seconds()
                return {
                    "status": "no_results",
                    "query": user_query,
                    "answer": "No relevant documents found in the knowledge base.",
                    "retrieved_documents": [],
                    "document_count": 0,
                    "processing_time_seconds": round(processing_time, 2),
                }

            # Prepare context
            context_parts = [
                f"[Document {i+1} - Relevance: {doc['relevance_score']:.1%}]\n{doc['content']}"
                for i, doc in enumerate(relevant_docs)
            ]
            context = "\n\n".join(context_parts)

            # Try to generate response using LLM, but gracefully degrade to context-only mode
            response_text = None
            try:
                prompt = ChatPromptTemplate.from_template(
                    """Based on the following documents, answer the user's question accurately.
If information is not in the documents, say so clearly.

Documents:
{context}

User Question: {query}

Answer:"""
                )
                response_text = self.llm.invoke(
                    prompt.format(context=context, query=user_query)
                )
            except Exception as llm_error:
                logger.warning(f"⚠️  LLM generation not available: {llm_error}")
                # Gracefully degrade: use document context as answer
                response_text = (
                    f"Based on {len(relevant_docs)} relevant document(s):\n\n{context}"
                )

            processing_time = (datetime.now() - start_time).total_seconds()
            self.stats["queries_processed"] += 1

            return {
                "status": "success",
                "query": user_query,
                "answer": (
                    response_text.strip() if response_text else "No answer generated"
                ),
                "retrieved_documents": relevant_docs,
                "document_count": len(relevant_docs),
                "processing_time_seconds": round(processing_time, 2),
            }
        except ValueError as e:
            logger.warning(f"⚠️  Query validation error: {e}")
            self.stats["errors"] += 1
            raise
        except Exception as e:
            logger.error(f"❌ Document query failed: {e}", exc_info=True)
            self.stats["errors"] += 1
            return {
                "status": "error",
                "query": user_query,
                "error": str(e),
            }

    def get_stats(self) -> dict:
        """Get engine statistics."""
        total_documents = 0
        if self.chroma_collection:
            total_documents = self.chroma_collection.count()

        return {
            **self.stats,
            "total_documents": total_documents,
            "catalog_documents": len(self.catalog.list_documents()),
            "timestamp": datetime.now().isoformat(),
        }

    def get_readiness(self) -> dict:
        """Report production operating capabilities."""
        stats = self.get_stats()
        memory = self._check_chroma_storage()
        ollama = self._check_ollama()
        status = "ready" if memory["status"] == "ready" and ollama["status"] == "ready" else "degraded"

        return {
            "status": status,
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

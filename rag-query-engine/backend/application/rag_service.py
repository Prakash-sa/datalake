"""
RAG Service - Application use cases and orchestration
"""

import os
import logging
from typing import List, Dict
from datetime import datetime
from pathlib import Path

import chromadb
from langchain_ollama import OllamaEmbeddings, OllamaLLM
from langchain_core.prompts import ChatPromptTemplate

from domain.models import SearchResult

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

    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        embedding_model: str = "nomic-embed-text",
        llm_model: str = "mistral",
        temperature: float = 0.3,
        chroma_path: str = "./chroma_db",
    ):
        """Initialize RAG service with Chroma vector database."""
        if not 0.0 <= temperature <= 1.0:
            raise ValueError("Temperature must be between 0.0 and 1.0")

        self.ollama_url = ollama_url
        self.embedding_model = embedding_model
        self.llm_model = llm_model
        self.temperature = temperature
        self.chroma_path = chroma_path
        self.embeddings = None
        self.llm = None
        self.chroma_client = None
        self.chroma_collection = None
        self.documents_store: Dict[str, Dict] = {}
        self.stats = {"documents_indexed": 0, "queries_processed": 0, "errors": 0}
        self._initialize_components()

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

    def index_documents(self, documents: List[dict]) -> dict:
        """Index documents into the vector store."""
        if not documents:
            return {"status": "success", "documents_indexed": 0}

        try:
            logger.info(f"📄 Indexing {len(documents)} documents...")
            indexed_count = 0
            errors = []

            for idx, doc in enumerate(documents):
                try:
                    doc_id = doc.get("id", "")
                    content = doc.get("content", "")

                    if not doc_id or not content:
                        errors.append(f"Document {idx}: missing 'id' or 'content'")
                        continue

                    embedding = self.embeddings.embed_query(content)
                    self.documents_store[doc_id] = {
                        "content": content,
                        "embedding": embedding,
                        "metadata": doc.get("metadata", {}),
                    }
                    indexed_count += 1

                except Exception as e:
                    errors.append(f"Document {idx}: {str(e)}")
                    logger.warning(f"Failed to index document {idx}: {e}")

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

            # Query Chroma
            results = self.chroma_collection.query(
                query_texts=[query],
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
                            "content": doc_text[:500],
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

    def query_documents(self, user_query: str, k: int = 5, timeout: int = 30) -> dict:
        """Execute RAG pipeline: search documents, retrieve context, generate response."""
        try:
            if not user_query or len(user_query) > self.MAX_QUERY_LENGTH:
                raise ValueError(f"Query must be 1-{self.MAX_QUERY_LENGTH} characters")

            logger.info(f"📝 Processing query: {user_query[:100]}...")
            start_time = datetime.now()

            # Search for relevant documents
            relevant_docs = self.search_documents(user_query, k=k)

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
        return {
            **self.stats,
            "total_documents": len(self.documents_store),
            "timestamp": datetime.now().isoformat(),
        }

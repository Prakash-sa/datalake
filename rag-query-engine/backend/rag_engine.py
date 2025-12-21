"""
Document RAG Engine
Semantic search and LLM-powered analysis on structured and unstructured enterprise documents.
"""

import os
import json
from typing import List
from datetime import datetime
import logging

from langchain_ollama import OllamaEmbeddings, OllamaLLM
from langchain_core.prompts import ChatPromptTemplate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DocumentRAGEngine:
    """
    RAG Engine for semantic search and LLM analysis on enterprise documents.
    Supports structured and unstructured data (PDFs, documents, databases, etc.)
    Uses in-memory vector store for demo purposes.
    """

    def __init__(self, chroma_path: str = "./chroma_db", ollama_url: str = "http://localhost:11434"):
        """
        Initialize the document RAG engine.
        
        Args:
            chroma_path: Path to Chroma vector database (for future use)
            ollama_url: URL to Ollama LLM service
        """
        self.chroma_path = chroma_path
        self.ollama_url = ollama_url
        self.embeddings = None
        self.llm = None
        self.documents_store = {}  # In-memory document store: {id: {"content": ..., "embedding": ..., "metadata": ...}}
        self._initialize_components()

    def _initialize_components(self):
        """Initialize RAG components: embeddings, LLM."""
        try:
            # Initialize embeddings model
            self.embeddings = OllamaEmbeddings(
                model="nomic-embed-text",
                base_url=self.ollama_url
            )
            logger.info("✅ Embedding model initialized")
            
            # Initialize LLM
            self.llm = OllamaLLM(model="mistral", base_url=self.ollama_url, temperature=0.3)
            logger.info("✅ LLM initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize RAG components: {e}")
            raise

    def index_documents(self, documents: List[dict]) -> dict:
        """
        Index documents into the vector store.
        
        Args:
            documents: List of document dictionaries with 'id', 'content', 'metadata'
            
        Returns:
            Indexing statistics
        """
        try:
            logger.info(f"📄 Indexing {len(documents)} documents...")
            
            for doc in documents:
                doc_id = doc.get('id', '')
                content = doc.get('content', '')
                metadata = doc.get('metadata', {})
                
                # Generate embedding for document
                embedding = self.embeddings.embed_query(content)
                
                # Store in memory
                self.documents_store[doc_id] = {
                    "content": content,
                    "embedding": embedding,
                    "metadata": metadata
                }
            
            logger.info(f"✅ Indexed {len(documents)} documents")
            
            return {
                "status": "success",
                "documents_indexed": len(documents),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"❌ Document indexing failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    def search_documents(self, query: str, k: int = 5) -> List[dict]:
        """
        Search for relevant documents using semantic similarity.
        
        Args:
            query: Search query
            k: Number of results to return
            
        Returns:
            List of relevant documents with scores
        """
        try:
            logger.info(f"🔍 Searching for: {query}")
            
            if not self.documents_store:
                logger.info("No documents in store")
                return []
            
            # Generate query embedding
            query_embedding = self.embeddings.embed_query(query)
            
            # Calculate similarity scores using cosine similarity
            similarities = []
            for doc_id, doc_data in self.documents_store.items():
                doc_embedding = doc_data["embedding"]
                # Simple cosine similarity
                dot_product = sum(a * b for a, b in zip(query_embedding, doc_embedding))
                norm_q = sum(x ** 2 for x in query_embedding) ** 0.5
                norm_d = sum(x ** 2 for x in doc_embedding) ** 0.5
                similarity = dot_product / (norm_q * norm_d) if norm_q > 0 and norm_d > 0 else 0
                similarities.append((doc_id, similarity))
            
            # Sort by similarity and get top k
            top_results = sorted(similarities, key=lambda x: x[1], reverse=True)[:k]
            
            documents = []
            for doc_id, score in top_results:
                doc_data = self.documents_store[doc_id]
                documents.append({
                    "id": doc_id,
                    "content": doc_data["content"],
                    "metadata": doc_data["metadata"],
                    "relevance_score": float(score)
                })
            
            logger.info(f"✅ Found {len(documents)} relevant documents")
            return documents
        except Exception as e:
            logger.error(f"❌ Document search failed: {e}")
            return []

    def query_documents(self, user_query: str, k: int = 5) -> dict:
        """
        End-to-end RAG pipeline: search documents → retrieve context → generate response.
        
        Args:
            user_query: Natural language query about documents
            k: Number of documents to retrieve
            
        Returns:
            RAG response with retrieved documents and LLM answer
        """
        try:
            logger.info(f"📝 Processing document query: {user_query}")
            
            # Step 1: Search for relevant documents
            relevant_docs = self.search_documents(user_query, k=k)
            
            if not relevant_docs:
                return {
                    "status": "no_results",
                    "query": user_query,
                    "message": "No relevant documents found",
                    "timestamp": datetime.now().isoformat()
                }
            
            # Step 2: Prepare context from retrieved documents
            context = "\n\n".join([
                f"Document {i+1} (Relevance: {doc['relevance_score']:.2f}):\n{doc['content'][:500]}"
                for i, doc in enumerate(relevant_docs)
            ])
            
            logger.info(f"📚 Retrieved context from {len(relevant_docs)} documents")
            
            # Step 3: Generate response using LLM
            prompt = ChatPromptTemplate.from_template("""
Based on the following documents, answer the user's question. 
Be specific and cite the relevant documents.

Documents:
{context}

User Question: {query}

Answer:
""")
            
            response_text = self.llm.invoke(prompt.format(context=context, query=user_query))
            logger.info(f"✅ Generated response")
            
            return {
                "status": "success",
                "query": user_query,
                "answer": response_text.strip(),
                "retrieved_documents": relevant_docs,
                "document_count": len(relevant_docs),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"❌ Document query failed: {e}")
            return {
                "status": "error",
                "query": user_query,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }


# Example usage
if __name__ == "__main__":
    # Initialize RAG engine
    engine = DocumentRAGEngine(
        chroma_path="./chroma_db",
        ollama_url="http://localhost:11434"
    )
    
    # Example documents to index
    sample_documents = [
        {
            "id": "doc1",
            "content": "Apache Iceberg is a table format designed for huge analytic tables. It supports arbitrary schemas and partitioning.",
            "metadata": {"source": "docs", "type": "documentation"}
        },
        {
            "id": "doc2",
            "content": "Trino is a distributed SQL query engine for big data analytics. It can query data where it lives.",
            "metadata": {"source": "docs", "type": "documentation"}
        },
        {
            "id": "doc3",
            "content": "Apache Airflow is a platform to programmatically author, schedule and monitor workflows.",
            "metadata": {"source": "docs", "type": "documentation"}
        }
    ]
    
    # Index documents
    print("\n=== Indexing Documents ===")
    index_result = engine.index_documents(sample_documents)
    print(json.dumps(index_result, indent=2))
    
    # Query documents
    test_queries = [
        "What is Iceberg and what is it designed for?",
        "Tell me about Trino",
        "How does Airflow work?"
    ]
    
    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        result = engine.query_documents(query, k=3)
        print(f"Answer: {result.get('answer', 'No answer')}")
        print(f"Documents used: {result.get('document_count', 0)}")
        print(f"{'='*60}")

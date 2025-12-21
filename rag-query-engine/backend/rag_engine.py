"""
Document RAG Engine
Semantic search and LLM-powered analysis on structured and unstructured enterprise documents.
"""

import os
from typing import List
from datetime import datetime
import logging
import json

from langchain_ollama import OllamaEmbeddings, OllamaLLM
from langchain_chroma import Chroma
from langchain.prompts import ChatPromptTemplate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DocumentRAGEngine:
    """
    RAG Engine for semantic search and LLM analysis on enterprise documents.
    Supports structured and unstructured data (PDFs, documents, databases, etc.)
    """

    def __init__(self, chroma_path: str = "./chroma_db", ollama_url: str = "http://localhost:11434"):
        """
        Initialize the document RAG engine.
        
        Args:
            chroma_path: Path to Chroma vector database
            ollama_url: URL to Ollama LLM service
        """
        self.chroma_path = chroma_path
        self.ollama_url = ollama_url
        self.embeddings = None
        self.llm = None
        self.vector_store = None
        self._initialize_components()

    def _initialize_components(self):
        """Initialize RAG components: embeddings, LLM, vector store."""
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
            
            # Initialize vector store
            self.vector_store = Chroma(
                collection_name="documents",
                persist_directory=self.chroma_path,
                embedding_function=self.embeddings
            )
            logger.info("✅ Vector store initialized")
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
            
            doc_texts = []
            doc_ids = []
            doc_metadatas = []
            
            for doc in documents:
                doc_texts.append(doc.get('content', ''))
                doc_ids.append(doc.get('id', ''))
                doc_metadatas.append(doc.get('metadata', {}))
            
            # Add to vector store
            if doc_texts:
                self.vector_store.add_texts(
                    texts=doc_texts,
                    ids=doc_ids,
                    metadatas=doc_metadatas
                )
                logger.info(f"✅ Indexed {len(doc_texts)} documents")
            
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
            
            results = self.vector_store.similarity_search_with_scores(query, k=k)
            
            documents = []
            for doc, score in results:
                documents.append({
                    "content": doc.page_content,
                    "metadata": doc.metadata,
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
        logger.info(f"🔍 Generated SQL:\n{sql_query}")
        
        # Step 3: Execute with self-correction loop
        for attempt in range(max_retries + 1):
            result = self.execute_query(sql_query)
            
            if result["status"] == "success":
                logger.info(f"✅ Query executed successfully ({result['row_count']} rows)")
                return {
                    "user_query": user_query,
                    "sql_query": sql_query,
                    "results": result,
                    "attempts": attempt + 1,
                    "timestamp": datetime.now().isoformat()
                }
            elif attempt < max_retries:
                logger.warning(f"⚠️ Attempt {attempt + 1} failed, self-correcting...")
                sql_query = self.validate_and_correct_query(user_query, sql_query, result.get("error"))
        
        # Return last attempt result
        return {
            "user_query": user_query,
            "sql_query": sql_query,
            "results": result,
            "attempts": max_retries + 1,
            "timestamp": datetime.now().isoformat()
        }


# Example usage
if __name__ == "__main__":
    # Initialize query engine
    engine = DataLakeQueryEngine(trino_host="localhost", trino_port=8080)
    
    # Example SQL queries
    test_queries = [
        "SELECT COUNT(*) as total_count FROM iceberg.raw.sales",
        "SELECT * FROM iceberg.raw.customers LIMIT 5",
        "SELECT product_id, SUM(amount) as total FROM iceberg.raw.sales GROUP BY product_id"
    ]
    
    for query in test_queries:
        result = engine.execute_query(query)
        print(f"\n{'='*60}")
        print(f"SQL: {query}")
        print(f"Status: {result['status']}")
        if result['status'] == 'success':
            print(f"Rows: {result['row_count']}")
            print(f"Columns: {result['columns']}")
        else:
            print(f"Error: {result['error']}")
        print(f"{'='*60}")
        print(f"{'='*60}")

# 🏗️ Enterprise RAG System - Architecture Diagrams

## 1. High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                                │
│  ┌─────────────────┐  ┌──────────────┐  ┌─────────────────────────┐│
│  │ Web Browser     │  │ Mobile App   │  │ Command Line / Scripts  ││
│  │ http://3000     │  │ (Future)     │  │ (REST API clients)      ││
│  └────────┬────────┘  └──────┬───────┘  └────────────┬─────────────┘│
└───────────┼──────────────────┼──────────────────────┼──────────────────┘
            │                  │                      │
            └──────────────────┴──────────────────────┘
                               │
                     ┌─────────▼─────────┐
                     │  API GATEWAY      │
                     │  (FastAPI Router) │
                     └─────────┬─────────┘
                               │
┌──────────────────────────────┴──────────────────────────────────────┐
│                      APPLICATION LAYER                             │
│                                                                     │
│  ┌──────────────────────────┐      ┌─────────────────────────────┐│
│  │ RAG Service              │      │ Frontend Service            ││
│  │ (Search & Q&A Logic)     │      │ (Next.js)                   ││
│  │                          │      │                             ││
│  │ - Document Search        │      │ - Search Interface          ││
│  │ - Embedding Generation   │      │ - Q&A Interface             ││
│  │ - LLM Query Processing   │      │ - Results Display           ││
│  │ - Source Attribution     │      │ - Real-time Streaming       ││
│  └────────┬─────────────────┘      └─────────────┬───────────────┘│
└───────────┼────────────────────────────────────┬─────────────────────┘
            │                                    │
            └────────────────┬───────────────────┘
                             │
┌────────────────────────────┼────────────────────────────────────────┐
│                      DATA LAYER                                    │
│                                                                     │
│  ┌─────────────────────────────┐  ┌──────────────────────────────┐│
│  │ VECTOR DATABASE (Chroma)    │  │ LLM INFERENCE (Ollama)       ││
│  │                             │  │                              ││
│  │ - Documents Index           │  │ - orca-mini (LLM)            ││
│  │ - Embeddings (768-dim)      │  │ - nomic-embed-text (embed)   ││
│  │ - Metadata Store            │  │ - In-memory Model Weights    ││
│  │ - Similarity Search         │  │ - Context-aware Generation   ││
│  │ - Persistent Storage        │  │ - Batch Processing Ready     ││
│  │ (Port 8000)                 │  │ (Port 11434)                 ││
│  └────────┬────────────────────┘  └──────────┬───────────────────┘│
│           │                                  │                     │
│  ┌────────┴──────────┐                       │                     │
│  │ STORAGE (MinIO)   │                       │                     │
│  │                   │                       │                     │
│  │ - Documents       │◄──────────────────────┘                     │
│  │ - Staging Area    │                                             │
│  │ - S3 Compatible   │                                             │
│  │ (Port 9000/9001)  │                                             │
│  └───────────────────┘                                             │
└──────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATION LAYER                            │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ Apache Airflow (Port 9093)                                   │ │
│  │                                                              │ │
│  │  Scheduler → Worker Pool → Task Execution                   │ │
│  │                                                              │ │
│  │  DAG: document_rag_ingestion_pipeline                        │ │
│  │  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌────────┐    │ │
│  │  │ Fetch    │→ │ Process   │→ │ Embed    │→ │ Upsert │    │ │
│  │  │ Documents│  │ Documents │  │ Docs     │  │ Chroma │    │ │
│  │  └──────────┘  └───────────┘  └──────────┘  └───┬────┘    │ │
│  │                                                  │          │ │
│  │  ┌──────────┐  ┌──────────────────────────────┘           │ │
│  │  │ Validate │← │ Notify                                    │ │
│  │  │ Vector DB│  │ Completion                                │ │
│  │  └──────────┘  └───────────────────────────────────────────┘ │
│  │                                                              │ │
│  │ Data Flow: XCom (PostgreSQL-backed)                          │ │
│  │ Execution: Celery + Redis                                   │ │
│  └──────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│                  INFRASTRUCTURE LAYER                             │
│                                                                    │
│  ┌──────────────────┐  ┌──────────────┐  ┌─────────────────────┐ │
│  │ PostgreSQL       │  │ Redis        │  │ Docker Network      │ │
│  │ (Port 5432)      │  │ (Port 6379)  │  │                     │ │
│  │                  │  │              │  │ - airflow-network   │ │
│  │ - Airflow State  │  │ - Task Queue │  │ - rag-network       │ │
│  │ - XCom Data      │  │ - Caching    │  │ - Service Discovery │ │
│  │ - Metadata       │  │ - Session    │  │ - Internal DNS      │ │
│  └──────────────────┘  └──────────────┘  └─────────────────────┘ │
└────────────────────────────────────────────────────────────────────┘
```

---

## 2. Data Flow - Complete Request Lifecycle

### A. Document Upload & Indexing

```
USER UPLOADS DOCUMENT
│
├─ MinIO Console (http://localhost:9001)
│  └─ Select file → Upload to "documents" bucket
│
▼
DOCUMENT STORED IN MINIO
│
├─ File location: s3://documents/filename.txt
│
▼
AIRFLOW DAG TRIGGERED (daily or manual)
│
├─ Scheduler detects new documents
│
▼
TASK 1: fetch_documents_from_minio
│
├─ Connect to MinIO
├─ List all documents in bucket
├─ Read file content (limit 5000 chars)
├─ Return List[Dict] documents
│
├─ XCom Push:
│  └─ Key: "documents"
│     Value: [{"id": "doc1", "content": "...", "metadata": {...}}, ...]
│
▼
TASK 2: process_documents
│
├─ XCom Pull: fetch previous task output
├─ Chunk documents (1000 tokens, 200 overlap)
├─ Generate chunk metadata
├─ Return List[Dict] processed_docs
│
├─ XCom Push:
│  └─ Key: "processed_docs"
│     Value: [{"id": "doc1_chunk_0", "content": "..."}, ...]
│
▼
TASK 3: create_embeddings
│
├─ XCom Pull: processed documents
├─ For each chunk:
│  ├─ Send to Ollama: text → nomic-embed-text
│  ├─ Receive vector: 768-dimensional
│  └─ Store: {id, content, vector, metadata}
├─ Return List[Dict] embedded_docs
│
├─ XCom Push:
│  └─ Key: "embedded_docs"
│     Value: [{"id": "doc1_chunk_0", "vector": [0.1, 0.2, ...], ...}, ...]
│
▼
TASK 4: upsert_to_chroma
│
├─ XCom Pull: embedded documents
├─ Connect to Chroma persistent client
├─ Get or create collection "documents"
│  ├─ Dimension: 768
│  ├─ Metric: cosine similarity
│  └─ Index: HNSW
├─ For each embedding:
│  ├─ ID: "doc1_chunk_0"
│  ├─ Embedding: [0.1, 0.2, ...] (768 floats)
│  ├─ Document: "text content..."
│  └─ Metadata: {source, filename, chunk_index, ...}
├─ Batch upsert to Chroma
├─ Return {status, count, timestamp}
│
├─ XCom Push:
│  └─ Key: "upsert_result"
│     Value: {status: "success", embeddings_count: 50, ...}
│
▼
TASK 5: validate_vector_db
│
├─ XCom Pull: upsert result
├─ Connect to Chroma
├─ Query collection count
├─ Verify count matches expected
├─ Sample search to verify indexing
├─ Return {status, validation_details}
│
├─ XCom Push:
│  └─ Key: "validation_result"
│     Value: {status: "success", total_embeddings: 1250, ...}
│
▼
TASK 6: notify_completion
│
├─ XCom Pull: validation result
├─ Log pipeline summary
├─ (Optional) Send notification
├─ Return completion summary
│
▼
DOCUMENTS NOW SEARCHABLE
│
├─ Collection: "documents" in Chroma
├─ Status: Ready for queries
```

### B. User Query & Search Flow

```
USER SUBMITS SEARCH QUERY
│
├─ UI: http://localhost:3000
│  └─ Enter: "kubernetes deployment"
│
▼
FRONTEND SENDS REQUEST
│
├─ API URL: http://localhost:8000/documents/search
├─ Method: POST
├─ Body: {
│    "query": "kubernetes deployment",
│    "top_k": 5
│  }
│
▼
FASTAPI RECEIVES REQUEST
│
├─ Endpoint: POST /documents/search
├─ RAG Service processes:
│  │
│  ├─ Step 1: Generate Query Embedding
│  │  ├─ Send query to Ollama
│  │  ├─ Model: nomic-embed-text
│  │  ├─ Output: 768-dimensional vector
│  │  └─ Time: ~50-100ms
│  │
│  ├─ Step 2: Search Chroma
│  │  ├─ Query vector: [0.1, 0.2, ..., 768 dims]
│  │  ├─ Distance metric: cosine similarity
│  │  ├─ Results: top 5 matches
│  │  ├─ Scores: [0.92, 0.87, 0.81, 0.75, 0.68]
│  │  └─ Time: ~100-200ms
│  │
│  ├─ Step 3: Format Results
│  │  ├─ For each match:
│  │  │  ├─ Document ID
│  │  │  ├─ Text content
│  │  │  ├─ Similarity score
│  │  │  └─ Metadata (source, filename, chunk#)
│  │  └─ Time: ~30ms
│  │
│  └─ Step 4: Return JSON
│     └─ Time: <1ms
│
▼
API RESPONSE (200 OK)
│
├─ Status: 200
├─ Body: {
│    "query": "kubernetes deployment",
│    "results": [
│      {
│        "id": "k8s_guide_chunk_2",
│        "content": "To deploy: 1. Create namespace...",
│        "similarity_score": 0.924,
│        "metadata": {...}
│      },
│      ... 4 more results
│    ],
│    "execution_time_ms": 245,
│    "total_documents_searched": 847
│  }
│
▼
FRONTEND DISPLAYS RESULTS
│
├─ Format: Ranked list with scores
├─ Display: Document preview + source
├─ Link: Click to view full document
├─ Time: <100ms rendering
│
▼
TOTAL LATENCY: 200-500ms
```

### C. LLM Question-Answering Flow

```
USER CLICKS "ASK AI"
│
├─ UI sends question + context
│  └─ API: POST /documents/ask
│     Body: {
│       "question": "Explain k8s deployment",
│       "top_k": 3
│     }
│
▼
FASTAPI PROCESSES REQUEST
│
├─ Step 1: Retrieve Context
│  ├─ Search for similar documents
│  ├─ Top-3 results
│  ├─ Extract content + sources
│  └─ Context: ~500-1000 tokens
│
├─ Step 2: Build Prompt
│  └─ Format:
│     """
│     Context from documents:
│     - [Source 1] k8s pattern...
│     - [Source 2] best practices...
│     - [Source 3] common mistakes...
│     
│     Question: Explain k8s deployment
│     
│     Answer:
│     """
│
├─ Step 3: Call Ollama LLM
│  ├─ Model: orca-mini
│  ├─ Temperature: 0.7
│  ├─ Max tokens: 500
│  ├─ System prompt: "You are helpful..."
│  └─ Time: 2-5 seconds
│
├─ Step 4: Stream Response
│  ├─ Token-by-token streaming
│  ├─ Frontend shows in real-time
│  └─ User sees: "Generating... deploying..."
│
├─ Step 5: Format Output
│  └─ {
│       "question": "...",
│       "answer": "Based on documents...",
│       "sources": [
│         {"id": "chunk_1", "score": 0.91},
│         {"id": "chunk_2", "score": 0.88}
│       ],
│       "model": "orca-mini",
│       "generation_time_ms": 2150
│     }
│
▼
API RESPONSE (200 OK)
│
├─ Streaming response
├─ User sees answer building in real-time
│
▼
TOTAL LATENCY: 2-6 seconds
│
└─ Breakdown:
   ├─ Search: 200ms
   ├─ LLM inference: 2-5s
   ├─ Formatting: 50ms
   └─ Network: 100-300ms
```

---

## 3. Component Interaction Diagram

```
                  ┌─────────────────┐
                  │   User/Browser  │
                  │  http://3000    │
                  └────────┬────────┘
                           │ HTTP/JSON
                           ▼
                    ┌────────────────────┐
                    │  Next.js Frontend  │
                    │  Search & Q&A UI   │
                    └────────┬───────────┘
                             │ HTTP/REST
              ┌──────────────┴──────────────┐
              │                             │
              ▼                             ▼
    ┌──────────────────────┐    ┌────────────────────────┐
    │   FastAPI Backend    │    │  API Documentation    │
    │  /documents/search   │    │  http://8000/docs     │
    │  /documents/ask      │    │                        │
    │  /health             │    └────────────────────────┘
    └────────┬─────────────┘
             │
    ┌────────┼────────────────────────┐
    │        │                        │
    ▼        ▼                        ▼
┌─────────────┐     ┌──────────────┐    ┌────────────────┐
│ RAG Engine  │     │   Ollama     │    │ Error Handler  │
│ (Python)    │     │  (LLM + Embed)   │ (Graceful      │
│             │     │               │  │  Degradation)  │
│ - Search    │     │ Models:       │    │                │
│ - Embedding │     │ - orca-mini  │    └────────────────┘
│ - Context   │     │ - nomic-embed│
└──────┬──────┘     └────────┬─────┘
       │                     │
       │           ┌─────────┘
       │           │
       │           ▼
       │    ┌──────────────────┐
       │    │ Chroma Vector DB │
       │    │                  │
       │    │ Collection:      │
       │    │ "documents"      │
       │    │                  │
       │    │ - Embeddings     │
       │    │ - Metadata       │
       │    │ - Search Index   │
       │    └────────┬─────────┘
       │             │
       └─────────────┘
              │
    ┌─────────┴─────────┐
    │                   │
    ▼                   ▼
┌────────────┐    ┌─────────────┐
│  MinIO     │    │ Postgres    │
│  Storage   │    │ Metadata    │
│            │    │ (Airflow)   │
│ Bucket:    │    │             │
│ documents  │    │ - DAG state │
│            │    │ - XCom data │
└────────────┘    └─────────────┘
                         │
    ┌────────────────────┴──────────────────────┐
    │                                          │
    ▼                                          ▼
┌──────────────────┐                    ┌─────────────────────┐
│ Apache Airflow   │                    │ Redis               │
│ (Orchestration)  │                    │ (Cache + Broker)    │
│                  │                    │                     │
│ - Scheduler      │                    │ - Task Queue        │
│ - Workers        │                    │ - Query Results     │
│ - DAG Pipeline   │                    │ - Sessions          │
│                  │                    │                     │
│ 6-Task DAG:      │                    └─────────────────────┘
│ 1. Fetch         │
│ 2. Process       │
│ 3. Embed         │
│ 4. Upsert        │
│ 5. Validate      │
│ 6. Notify        │
└──────────────────┘
```

---

## 4. Performance Flow & Bottleneck Analysis

```
SEARCH QUERY LATENCY BREAKDOWN:

  User Input
      │
      ├─ Network latency: 10-50ms
      │
      ▼
  FastAPI Receives Request
      │
      ├─ Parse JSON: 1ms
      ├─ Validate input: 2ms
      │
      ▼
  Generate Query Embedding
      │
      ├─ Network to Ollama: 10ms
      ├─ Embedding inference: 50-100ms (BOTTLENECK)
      ├─ Network return: 10ms
      │
      ▼
  Search Chroma
      │
      ├─ Similarity calculation: 50-150ms (BOTTLENECK)
      ├─ Sort results: 10ms
      │
      ▼
  Format Response
      │
      ├─ JSON serialization: 20-30ms
      │
      ▼
  Network to Frontend: 10-50ms

TOTAL: 200-500ms (Most time in vector search)

OPTIMIZATION OPPORTUNITIES:
1. Cache query embeddings (save 50-100ms)
2. Use 384-dim vectors (faster search, less memory)
3. Add GPU acceleration (embed faster)
4. Implement query result caching (avoid repeat searches)
```

---

## 5. Data Model & Schema

```
CHROMA VECTOR STORE SCHEMA:

Collection: "documents"
├─ Metric: cosine similarity
├─ Dimension: 768
├─ Index: HNSW

Document Structure:
{
  "id": "report_2024_chunk_2",          # Unique identifier
  "document": "Document text content...", # Full text for retrieval
  "embedding": [                          # 768-dim float vector
    0.123, 0.456, 0.789, ...,
    ... (768 values total)
  ],
  "metadata": {                           # Document metadata
    "source": "minio",
    "filename": "report_2024.txt",
    "size": 4096,
    "chunk_index": 2,
    "total_chunks": 12,
    "modified": "2025-12-21T10:00:00",
    "type": "document",
    "processing_timestamp": "2025-12-22T05:00:00"
  }
}

SEARCH QUERY:
├─ Input text: "kubernetes deployment"
├─ Convert to embedding: [0.234, 0.567, ..., 768 dims]
├─ Find similar: cosine_similarity(query_vec, doc_vec)
├─ Return: Top-K results with scores 0.0-1.0

POSTGRESQL STORAGE (Airflow):

xcom table:
├─ dag_id: "document_rag_ingestion_pipeline"
├─ task_id: "fetch_documents_from_minio"
├─ key: "documents"
├─ value: JSON serialized List[Dict]
└─ timestamp: 2025-12-22 05:00:00

Variable table:
├─ key: "embedding_model"
├─ value: "nomic-embed-text"
└─ description: "Active embedding model"
```

---

## 6. Deployment Architecture (Docker)

```
DOCKER NETWORKS:

airflow-network:
├─ airflow-scheduler  (Airflow scheduler service)
├─ airflow-worker     (Celery worker)
├─ airflow-webserver  (Web UI)
├─ airflow-postgres   (Metadata DB)
├─ airflow-redis      (Task queue)
├─ airflow-triggerer  (Event trigger)
└─ minio              (Document storage)

rag-network:
├─ rag-backend        (FastAPI server)
├─ rag-frontend       (Next.js)
├─ chroma             (Vector DB)
└─ ollama             (LLM inference)

CONTAINER DEPENDENCIES:

airflow-postgres ← all airflow services
airflow-redis ← airflow-worker, airflow-scheduler
minio ← airflow-worker (document fetch)
ollama ← rag-backend (embeddings)
chroma ← rag-backend (vector search)
postgres ← airflow-scheduler (XCom storage)

VOLUMES:

Named volumes:
├─ airflow-logs/ (Airflow logs)
├─ airflow-plugins/ (Custom plugins)
├─ chroma_db/ (Vector store persistence)
└─ postgres_data/ (Database persistence)

Host mounts:
├─ ./infra/airflow/dags/ → /opt/airflow/dags
├─ ./backend/src/ → /app/src   (dev overlay only)
└─ ./volumes/ → /data
```

---

## Summary

This multi-layered architecture provides:

- **Scalability**: Each component can scale independently
- **Reliability**: Persistent storage, error handling, retries
- **Performance**: Optimized vector search, batch processing
- **Maintainability**: Clear component separation, standard APIs
- **Extensibility**: Easy to add new models, storage, or services

All components communicate via standard protocols (HTTP/JSON, XCom, S3 API, OpenAI-compatible) making this a production-grade system.

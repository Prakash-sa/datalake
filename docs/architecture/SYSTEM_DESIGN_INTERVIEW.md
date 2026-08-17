# 🎯 Enterprise Document RAG System - Design Interview Q&A

This document covers key system design interview questions and detailed answers about the Document RAG Platform architecture.

---

## Section 1: System Overview & Requirements

### Q1: What is this system designed to do?

**Answer:**
This is a **Retrieval Augmented Generation (RAG) system** that enables enterprises to:
- **Ingest** large document collections automatically via Apache Airflow pipelines
- **Index** documents as vector embeddings (768-dimensional) in Chroma vector database
- **Search** semantically (find by meaning, not just keywords)
- **Generate** context-aware answers using local LLM (Ollama orca-mini)
- **Query** via REST API or web UI

**Key Use Cases:**
- Customer support teams finding relevant documentation
- Compliance teams searching regulations across documents
- Knowledge management in enterprises
- Internal wiki/FAQ systems

---

### Q2: What are the core design goals?

**Answer:**
1. **Scalability** - Handle thousands of documents with fast semantic search
2. **Privacy** - No external APIs; all processing stays on-premises
3. **Real-time** - Sub-second search latency for user queries
4. **Automation** - Daily scheduled ingestion via DAGs
5. **Reliability** - Fault-tolerant with retries and error handling
6. **Cost** - Open-source stack, no vendor lock-in

---

### Q3: What is the expected scale?

**Answer:**
| Metric | Current | Target | Notes |
|--------|---------|--------|-------|
| Documents | 100+ | 10,000+ | With scaling |
| Embeddings Dim | 768-dim | 384-dim | For trade-off |
| Queries/sec | 10 | 100+ | With load balancing |
| Ingestion | Daily | Hourly | With more workers |
| API Response | <500ms | <200ms | With caching |
| Storage | 100GB | 1TB+ | Persistent volume |

---

## Section 2: Architecture & Components

### Q4: Describe the system architecture at high level.

**Answer:**

```
┌─────────────────────────────────────────────────────────────┐
│                    CLIENT LAYER                             │
│  Web UI (Next.js) | Mobile App | CLI Tools                  │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP/REST
┌────────────────────────▼────────────────────────────────────┐
│                   API LAYER                                 │
│         FastAPI (RAG Service)                               │
│  /documents/search  | /documents/ask  | /health             │
└──────┬─────────────────────────────────────┬────────────────┘
       │                                     │
       ▼                                     ▼
┌──────────────────┐              ┌──────────────────────┐
│ Vector Database  │              │   LLM Inference      │
│ Chroma (768-dim) │              │ Ollama (orca-mini)   │
│ Cosine Similarity│              │ Context Aware Q&A    │
│ Persistent Store │              │ nomic-embed-text     │
└──────────────────┘              └──────────────────────┘
       ▲
       │ Embeddings
       │
┌──────────────────────────────────────────────────────────────┐
│               DOCUMENT INGESTION PIPELINE                    │
│          Apache Airflow (6-Task DAG)                         │
│  Fetch → Process → Embed → Upsert → Validate → Notify       │
└──────────┬──────────────────────────────────────────────────┘
           │
           ▼
    ┌──────────────┐
    │ MinIO (S3)   │
    │ Documents    │
    │ Staging      │
    └──────────────┘

Support Infrastructure:
- PostgreSQL: Metadata, Airflow state
- Redis: Celery broker, caching
- Docker: Container orchestration
```

---

### Q5: What are the key components and their responsibilities?

**Answer:**

| Component | Technology | Port | Responsibility |
|-----------|-----------|------|-----------------|
| **Frontend** | Next.js 14 | 3000 | User interface for search & Q&A |
| **API** | FastAPI | 8000 | REST endpoints, business logic |
| **RAG Engine** | Python | 8000 | Search + embedding logic |
| **Vector DB** | Chroma | 8000 | Store & search embeddings |
| **LLM** | Ollama | 11434 | Generate responses |
| **Orchestration** | Airflow | 9093 | Schedule & monitor pipelines |
| **Storage** | MinIO | 9000 | S3-compatible document storage |
| **Database** | PostgreSQL | 5432 | Airflow metadata |
| **Message Broker** | Redis | 6379 | Task queue for Celery |

---

### Q6: Explain the data flow from document upload to search result.

**Answer:**

```
UPLOAD PHASE:
1. User uploads document to MinIO via console
   └─ Document stored in S3 bucket

INGESTION PHASE (Airflow DAG):
2. Fetch task: Reads from MinIO, returns List[Dict] documents
3. Process task: Chunks documents (1000 tokens), receives via XCom
4. Embed task: Generates 768-dim vectors using nomic-embed-text
5. Upsert task: Stores in Chroma with embeddings + metadata
6. Validate task: Verifies all documents indexed correctly
7. Notify task: Logs pipeline completion

QUERY PHASE (User search):
8. User enters query in frontend (http://localhost:3000)
9. Frontend sends to API: POST /documents/search
10. API converts query to embedding using same model
11. API searches Chroma for top-5 similar documents
12. API returns results with scores (0.0-1.0)

ANSWER PHASE (LLM Q&A):
13. User clicks "Ask AI"
14. API sends: question + top-3 search results as context
15. Ollama generates response using orca-mini model
16. API returns: {question, answer, sources}
```

---

## Section 3: Data & Embeddings

### Q7: How are documents stored and indexed?

**Answer:**

**Document Storage (MinIO)**:
```
Bucket: documents/
├── report_2024.txt (stored as binary)
├── manual_api.pdf (converted to text)
├── contract_sample.docx (extracted text)
└── [any supported format]
```

**Embedding Storage (Chroma)**:
```
Collection: "documents"
├── Dimension: 768 (from nomic-embed-text)
├── Distance metric: Cosine similarity
├── Index type: HNSW (Hierarchical Navigable Small World)
└── Document structure:
    {
      "id": "report_2024_chunk_0",
      "document": "Document text chunk...",
      "embedding": [0.123, 0.456, ...],  # 768 dimensions
      "metadata": {
        "source": "minio",
        "filename": "report_2024.txt",
        "chunk_index": 0,
        "total_chunks": 12
      }
    }
```

---

### Q8: Why use 768-dimensional embeddings? What are the trade-offs?

**Answer:**

| Dimension | Pros | Cons | Use Case |
|-----------|------|------|----------|
| **384** | Fast search, low memory | Lower accuracy | Real-time, mobile |
| **768** | Best accuracy | Higher latency | Production RAG |
| **1536** | OpenAI quality | Very slow | Offline batch |

**Our Choice: 768-dimensional**
- Trade-off between accuracy and performance
- ~100-200ms search latency
- ~1KB per embedding
- 10,000 documents = ~10MB storage

**Why nomic-embed-text?**
- Open-source (no API costs)
- Designed for semantic search
- Works well with Chroma
- Local inference with Ollama

---

### Q9: How are documents chunked and why?

**Answer:**

```python
# Configuration
chunk_size = 1000 tokens    # ~3000-4000 characters
chunk_overlap = 200 tokens  # 20% overlap for context continuity

# Example:
Original: "How to implement caching... [10,000 tokens]"
                    ↓
Chunks:
- Chunk 0: tokens 0-1000 (+ context)
- Chunk 1: tokens 800-1800 (overlap 200)
- Chunk 2: tokens 1600-2600 (overlap 200)
           ...
```

**Why Chunk?**
1. **Model Limitations**: LLM context window is limited (~2K-4K tokens)
2. **Granularity**: Smaller chunks = more precise search results
3. **Vector Relevance**: Too long documents dilute embeddings
4. **Memory**: Efficient storage and retrieval

**Trade-offs**:
- Smaller chunks = more vectors = slower search
- Larger chunks = less precise results
- Overlap = redundancy but better continuity

---

## Section 4: Search & Retrieval

### Q10: How does semantic search work in this system?

**Answer:**

```
SEARCH FLOW:
┌─────────────────────────────────────────────┐
│ User Query: "How to implement caching?"     │
└──────────────┬──────────────────────────────┘
               │
               ▼
    ┌─────────────────────────┐
    │ Convert to embedding    │
    │ using nomic-embed-text  │
    │ Result: [0.123, ...768] │
    └──────────┬──────────────┘
               │
               ▼
    ┌──────────────────────────────────┐
    │ Search Chroma using cosine       │
    │ similarity: similarity(query_vec,│
    │            document_vec)         │
    └──────────┬───────────────────────┘
               │
               ▼
    ┌──────────────────────────────────┐
    │ Return top-5 results with scores │
    │ [0.92, 0.87, 0.81, 0.75, 0.68]  │
    └──────────┬───────────────────────┘
               │
               ▼
    ┌──────────────────────────────────┐
    │ Format and return to user        │
    │ with source documents            │
    └──────────────────────────────────┘
```

**Why Cosine Similarity?**
- Measures angle between vectors (not magnitude)
- Values: -1 to +1 (normalized to 0-1)
- Interpretable as relevance score
- Efficient computation (no distance calculation)

**Complexity**:
- Time: O(N * 768) for each search (N = documents)
- Space: O(N * 768) for index storage
- With HNSW indexing: O(log N) nearest neighbor search

---

### Q11: What is the API response structure for a search query?

**Answer:**

```bash
POST /documents/search
Content-Type: application/json

{
  "query": "kubernetes deployment",
  "top_k": 5
}
```

**Response (200 OK)**:
```json
{
  "query": "kubernetes deployment",
  "results": [
    {
      "id": "k8s_guide_chunk_2",
      "content": "To deploy on Kubernetes: 1. Create namespace, 2. Apply manifests...",
      "similarity_score": 0.924,
      "metadata": {
        "source": "minio",
        "filename": "k8s_deployment_guide.txt",
        "chunk_index": 2,
        "total_chunks": 15,
        "size": 4096,
        "modified": "2025-12-21T10:00:00"
      }
    },
    {
      "id": "k8s_guide_chunk_3",
      "content": "Common deployment patterns include...",
      "similarity_score": 0.891,
      "metadata": {...}
    }
    // ... 3 more results
  ],
  "execution_time_ms": 245,
  "total_documents_searched": 847,
  "timestamp": "2025-12-22T05:00:00Z"
}
```

---

### Q12: Explain the LLM question-answering flow.

**Answer:**

```
QUESTION-ANSWERING FLOW:

1. User asks: "Explain kubernetes deployment strategies"
   └─ API receives: POST /documents/ask

2. API searches for relevant documents:
   └─ Top-3 results with score > 0.7

3. API prepares prompt:
   ```
   Context from documents:
   - [Source 1] kubernetes pattern...
   - [Source 2] best practices for...
   - [Source 3] common mistakes...
   
   Question: Explain kubernetes deployment strategies
   
   Answer:
   ```

4. Ollama generates response with orca-mini:
   └─ Temperature: 0.7 (creative but coherent)
   └─ Max tokens: 500
   └─ System prompt: "You are a helpful assistant..."

5. API formats response:
   {
     "question": "Explain kubernetes deployment strategies",
     "answer": "Based on the documents, there are several...",
     "sources": [
       {"id": "chunk_1", "score": 0.91},
       {"id": "chunk_2", "score": 0.88},
       {"id": "chunk_3", "score": 0.85}
     ],
     "model": "orca-mini",
     "generation_time_ms": 2150
   }
```

**Prompt Engineering**:
- Context window: 2K tokens
- Retrieved context: ~500 tokens
- Question + formatting: ~100 tokens
- Generation space: ~1400 tokens

**Graceful Degradation**:
If Ollama fails:
```json
{
  "question": "...",
  "answer": "Based on the following documents:\n- [formatted search results]",
  "sources": [...],
  "model": "context-only",
  "note": "LLM unavailable, returning search context instead"
}
```

---

## Section 5: Document Ingestion Pipeline

### Q13: Explain the Airflow DAG architecture.

**Answer:**

**DAG: document_rag_ingestion_pipeline**

```
Configuration:
├─ DAG ID: document_rag_ingestion_pipeline
├─ Schedule: Daily at 00:00 UTC (default)
├─ Retries: 1 per task
├─ Timeout: 2 hours total
└─ Owner: data-engineering

Task Dependency Graph:
┌────────────────────────┐
│ fetch_documents_from   │
│ minio                  │
│ Returns: List[Dict]    │
└──────────┬─────────────┘
           │ XCom: documents
           ▼
┌────────────────────────┐
│ process_documents      │
│ Chunks: 1000 tokens    │
│ Returns: List[Dict]    │
└──────────┬─────────────┘
           │ XCom: processed_docs
           ▼
┌────────────────────────┐
│ create_embeddings      │
│ Model: nomic-embed     │
│ Dimension: 768         │
│ Returns: List[Dict]    │
└──────────┬─────────────┘
           │ XCom: embedded_docs
           ▼
┌────────────────────────┐
│ upsert_to_chroma       │
│ Persist: embeddings    │
│ Returns: Dict          │
└──────────┬─────────────┘
           │ XCom: upsert_result
           ▼
┌────────────────────────┐
│ validate_vector_db     │
│ Verify: indexing       │
│ Returns: Dict          │
└──────────┬─────────────┘
           │ XCom: validation_result
           ▼
┌────────────────────────┐
│ notify_completion      │
│ Log: summary           │
│ Returns: None          │
└────────────────────────┘
```

---

### Q14: Why use XCom for data passing instead of files?

**Answer:**

**Problem with Files**:
```
Airflow runs each task in different container/process:
├─ fetch_task (container A)
│  └─ Writes: /tmp/documents.json
├─ process_task (container B)
│  └─ Reads: /tmp/documents.json  ❌ FILE NOT FOUND!
│  └─ Container A's /tmp is separate
└─ Task fails: "File not found"
```

**Solution with XCom**:
```
XCom (Cross-Communication) stores data in PostgreSQL:

Task 1: fetch_documents
└─ context.task_instance.xcom_push(
     key='documents',
     value=documents_list
   )

Task 2: process_documents (depends on Task 1)
└─ documents = context.task_instance.xcom_pull(
     key='documents',
     task_ids='fetch_documents_from_minio'
   )

Flow in PostgreSQL:
xcom table:
├─ dag_id: document_rag_ingestion_pipeline
├─ task_id: fetch_documents_from_minio
├─ key: documents
├─ value: [{"id": "doc1", "content": "..."}, ...]
└─ timestamp: 2025-12-22 05:00:00
```

**Advantages**:
- ✅ Works across containers
- ✅ Automatic serialization
- ✅ Persistent storage
- ✅ Failure recovery
- ✅ No temporary files

**Limitations**:
- ❌ Not ideal for very large payloads (>1GB)
- ❌ Slower than in-memory passing

---

### Q15: What happens if a task fails? How does recovery work?

**Answer:**

```
Task Failure Scenario:
┌─────────────────────────────────────┐
│ Task 3: create_embeddings fails     │
│ Error: Ollama not responding        │
└──────────┬────────────────────────────┘
           │
           ▼
    ┌──────────────────────────────────┐
    │ Airflow detects failure          │
    │ Task state → FAILED              │
    └──────────┬───────────────────────┘
               │
               ▼
    ┌──────────────────────────────────┐
    │ Check: max_tries = 1, retries=1  │
    │ Currently: try_number = 1        │
    │ Decision: Mark as FAILED         │
    └──────────┬───────────────────────┘
               │
               ▼
    ┌──────────────────────────────────┐
    │ Downstream tasks skipped         │
    │ - upsert_to_chroma: SKIPPED      │
    │ - validate_vector_db: SKIPPED    │
    │ - notify_completion: SKIPPED     │
    └──────────┬───────────────────────┘
               │
               ▼
    ┌──────────────────────────────────┐
    │ DAG Run marked as FAILED         │
    │ Email notification sent          │
    │ (if configured)                  │
    └──────────────────────────────────┘

RECOVERY OPTIONS:

Option 1: Fix and rerun from Airflow UI
- Fix the issue (restart Ollama, etc.)
- Click: Clear task state
- Click: Trigger DAG again

Option 2: Clear from CLI
docker exec airflow-scheduler \
  airflow tasks clear \
  document_rag_ingestion_pipeline \
  --task-id create_embeddings

Option 3: Automatic retry (if configured)
- Set retries=2 in DAG
- On failure, task reruns automatically
- With exponential backoff
```

---

## Section 6: Performance & Scalability

### Q16: What are the performance bottlenecks?

**Answer:**

| Bottleneck | Current | Cause | Solution |
|-----------|---------|-------|----------|
| **Search Latency** | 200-500ms | Vector search overhead | HNSW indexing, caching |
| **Embedding Gen** | 100-200ms/doc | Ollama inference | GPU acceleration, batching |
| **LLM Response** | 2-5 seconds | Orca-mini generation | Better model, shorter context |
| **Database I/O** | Variable | PostgreSQL for XCom | Redis caching, connection pool |
| **Network** | 50-100ms | Container communication | Host networking |

**Profiling Results**:
```
Ingestion Pipeline (100 documents):
- Fetch from MinIO:        5 seconds
- Process (chunk):        10 seconds
- Create embeddings:      30 seconds (bottleneck)
- Upsert to Chroma:        3 seconds
- Validate:                2 seconds
- Total:                  50 seconds

Search Query (1000 documents):
- Convert query:           10ms
- Chroma search:          100ms
- Format results:          30ms
- Total:                  140ms
```

---

### Q17: How would you scale this for 100,000 documents?

**Answer:**

**Current Limits** (1,000 documents):
- Vector search: O(N * 768) = linear time
- Memory: ~770MB for embeddings
- Storage: ~1GB with metadata

**100,000 Documents Scaling Plan**:

```
1. VECTOR SEARCH OPTIMIZATION
   └─ HNSW index (already in Chroma)
   └─ Trade-off: Memory for speed
   └─ Cost: ~77GB RAM for full index

2. DISTRIBUTED SEARCH
   ├─ Partition by topic/domain
   ├─ Separate Chroma instances
   ├─ Shard key: document_type
   └─ Router API: routes query to correct shard

3. EMBEDDING ACCELERATION
   ├─ Add GPU support to Ollama
   ├─ Batch embedding generation
   │  (Process 64 chunks in parallel)
   ├─ Use faster model (384-dim)
   └─ Async embedding generation

4. AIRFLOW SCALING
   ├─ Increase worker count: 1 → 4-8
   ├─ Parallelize document processing
   ├─ Add task priorities
   └─ Use Kubernetes executor (vs Celery)

5. CACHING LAYER
   ├─ Redis for frequently searched queries
   ├─ Cache TTL: 24 hours
   ├─ Hit rate target: 30-40%
   └─ Memory: ~10GB cache

6. API OPTIMIZATION
   ├─ Load balancer (nginx/HAProxy)
   ├─ API replicas: 1 → 3-5
   ├─ Connection pooling
   └─ Rate limiting: 100 req/sec

7. DATABASE OPTIMIZATION
   ├─ PostgreSQL indexes on metadata
   ├─ Connection pooling (pgBouncer)
   ├─ Read replicas for scaling
   └─ Archive old runs

8. STORAGE SCALING
   ├─ S3 (replace MinIO for huge scale)
   ├─ Cloud Blob Storage (Azure/GCP)
   ├─ Distributed volume (NFS/EBS)
   └─ Data tiering (hot/cold)
```

**Resource Requirements**:
```
100,000 documents = 1M chunks average

Hardware needed (for search tier):
├─ CPU: 16 cores
├─ RAM: 128GB (for vector index + caching)
├─ Storage: 500GB SSD (vectors + metadata)
└─ Network: 10Gbps

Estimated costs (cloud):
├─ Compute: $500-1000/month
├─ Storage: $50-100/month
├─ Database: $200-300/month
└─ Total: ~$1000/month
```

---

### Q18: What about real-time indexing? How would you support it?

**Answer:**

**Current Model** (Batch/Daily):
```
Daily DAG:
00:00 → Process all pending documents
└─ ~1 hour latency
```

**Real-time Indexing Options**:

```
OPTION 1: Kafka/Pub-Sub Stream
┌─────────────────────────────────────┐
│ Document Upload Event               │
└──────────┬──────────────────────────┘
           │
           ▼
    ┌─────────────────────┐
    │ Kafka Topic         │
    │ "document_uploads"  │
    └──────────┬──────────┘
               │ Stream processing
               ▼
    ┌──────────────────────────┐
    │ Flink/Spark Job          │
    │ ├─ 1. Extract text       │
    │ ├─ 2. Chunk document     │
    │ ├─ 3. Generate embedding │
    │ └─ 4. Upsert to Chroma   │
    └──────────┬───────────────┘
               │ ~500ms latency
               ▼
         Search-ready!
```

**OPTION 2: Webhook on Upload**
```
MinIO Event Notification
├─ Upload triggers HTTP webhook
├─ Calls: /api/documents/index
├─ Synchronous processing
└─ ~2-5 second latency

Issues:
- User waits for indexing
- If indexing fails, need retry
```

**OPTION 3: Message Queue + Workers**
```
Upload → RabbitMQ/Redis Queue
    ↓
Distributed workers (5+)
    ├─ Worker 1: Processing
    ├─ Worker 2: Embedding
    ├─ Worker 3: Upserting
    └─ Worker 4: Validating
    ↓
200-500ms latency
```

**Recommendation**:
- **For <100 docs/day**: Keep Airflow DAG
- **For 100-1000 docs/day**: Add Kafka stream
- **For >1000 docs/day**: Distributed stream + workers

---

## Section 7: Advanced Topics

### Q19: How would you implement caching to improve search latency?

**Answer:**

```
CACHING STRATEGY:

Level 1: Query Result Caching (Redis)
├─ Cache key: hash(query_text)
├─ Value: search results
├─ TTL: 24 hours
├─ Size: ~100KB per cached query
└─ Hit rate: 30-40%

Example:
query = "kubernetes deployment"
cache_key = sha256(query) = "a1b2c3..."

redis.setex(
  key=f"search:{cache_key}",
  time=86400,  # 24 hours
  value=json.dumps(results)
)

Level 2: Embedding Cache
├─ Cache key: hash(text_chunk)
├─ Value: embedding vector
├─ TTL: Never (permanent)
├─ Size: ~3KB per embedding
└─ Full cache possible (100,000 docs)

Level 3: Vector Index Cache
├─ HNSW graph in memory
├─ No TTL (persistent)
├─ Size: ~770MB per 1M embeddings
└─ Automatic via Chroma

CACHE INVALIDATION:

Scenario 1: Document Updated
├─ Clear query cache: * (all)
├─ Update embedding cache: hash(new_text)
├─ Reindex in Chroma: upsert with same ID
└─ Trigger: Airflow job or webhook

Scenario 2: New Documents Added
├─ Only add new embeddings
├─ Clear query cache: * (all)
├─ No need to invalidate old embeddings

Scenario 3: Time-based Expiration
├─ Query cache: 24 hour TTL
├─ Embedding cache: forever (unless doc deleted)
└─ Vector index: updated daily

PERFORMANCE IMPROVEMENT:

Without caching:
- 1000 queries/day × 200ms = 200 seconds latency
- Peak load: 100 req/sec = 50 seconds wait

With 40% cache hit rate:
- 400 cached queries × 5ms = 2 seconds
- 600 fresh searches × 200ms = 120 seconds
- Total: 122 seconds (39% improvement)

With 70% cache hit rate:
- 700 cached × 5ms = 3.5 seconds
- 300 fresh × 200ms = 60 seconds
- Total: 63.5 seconds (68% improvement)

IMPLEMENTATION:
```python
from functools import wraps
import redis
import hashlib
import json

redis_client = redis.Redis(host='localhost', port=6379)

def cache_search_results(ttl=86400):
    def decorator(func):
        @wraps(func)
        def wrapper(query, *args, **kwargs):
            cache_key = f"search:{hashlib.sha256(query.encode()).hexdigest()}"
            
            # Try cache first
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
            
            # Cache miss - fetch and store
            results = func(query, *args, **kwargs)
            redis_client.setex(
                cache_key, 
                ttl, 
                json.dumps(results, default=str)
            )
            return results
        return wrapper
    return decorator

@cache_search_results(ttl=86400)
def search_documents(query: str, top_k: int = 5):
    # Actual search logic
    pass
```

---

### Q20: How would you implement role-based access control (RBAC)?

**Answer:**

```
RBAC DESIGN:

Roles:
├─ Admin
│  └─ Can: upload, delete, search, ask, manage users
├─ DataEngineer
│  └─ Can: upload, delete, manage pipeline, view logs
├─ Analyst
│  └─ Can: search, ask, export results
└─ Viewer
   └─ Can: search, ask only

Resources:
├─ /documents/search (PUBLIC, anyone can call)
├─ /documents/ask (PUBLIC, anyone can call)
├─ /admin/upload (RESTRICTED, Analyst+)
├─ /admin/delete (RESTRICTED, Admin+)
├─ /admin/logs (RESTRICTED, DataEngineer+)
└─ /admin/users (RESTRICTED, Admin only)

Implementation:
1. Add JWT authentication
   ├─ Issue tokens on login
   ├─ Include role in token
   └─ Validate on each request

2. Add middleware for authorization
   @app.post("/documents/delete")
   @require_role("admin")
   def delete_document(doc_id: str):
       ...

3. Document-level access control
   ├─ Metadata: document_owners = ["user1", "user2"]
   ├─ Check: request.user in document.owners
   ├─ Or: request.user.role == "admin"
   └─ Deny access if not authorized

4. Audit logging
   └─ Log all access attempts (success/failure)
```

---

## Section 8: Production Deployment

### Q21: How would you deploy this to production?

**Answer:**

```
KUBERNETES DEPLOYMENT:

├─ Namespace: rag-prod
│
├─ Frontend Pod (replicas: 3)
│  ├─ Image: myregistry.com/rag-frontend:v1
│  ├─ Replicas: 3 (load balanced)
│  ├─ Resources: 
│  │  ├─ CPU: 500m
│  │  └─ Memory: 512Mi
│  └─ Service: LoadBalancer
│
├─ Backend Pod (replicas: 5)
│  ├─ Image: myregistry.com/rag-backend:v1
│  ├─ Replicas: 5 (auto-scale 2-10)
│  ├─ Resources:
│  │  ├─ CPU: 2000m
│  │  └─ Memory: 2Gi
│  ├─ Liveness probe: /health
│  ├─ Readiness probe: /health
│  └─ Service: ClusterIP
│
├─ Chroma StatefulSet (replicas: 2)
│  ├─ Image: chromadb/chroma:latest
│  ├─ Persistent Volume: 100Gi
│  └─ Service: Headless
│
├─ Ollama Pod (replicas: 2, GPU)
│  ├─ Image: ollama/ollama:latest
│  ├─ GPU: NVIDIA (2 per pod)
│  └─ Resources:
│     ├─ CPU: 4
│     └─ Memory: 8Gi
│
├─ PostgreSQL StatefulSet
│  ├─ Image: postgres:15
│  ├─ Persistent Volume: 50Gi
│  └─ Backup: Daily snapshots
│
├─ Redis StatefulSet
│  ├─ Image: redis:7-alpine
│  ├─ Persistent Volume: 20Gi
│  └─ Replication: 3
│
├─ Airflow Scheduler Pod
│  ├─ Replicas: 1 (HA: standby replica)
│  ├─ Resources: CPU: 2, Memory: 4Gi
│  └─ DAG sync: git-sync sidecar
│
└─ Airflow Worker Pods
   ├─ Replicas: 8 (auto-scale 2-16)
   ├─ Resources: CPU: 2, Memory: 4Gi
   └─ Scale based on task queue

NETWORKING:
├─ Ingress (nginx):
│  ├─ frontend.example.com → Frontend LB
│  ├─ api.example.com → Backend LB
│  └─ airflow.example.com → Airflow UI
│
└─ Network Policies:
   ├─ Frontend → Backend: allowed
   ├─ Backend → Chroma: allowed
   ├─ Backend → Ollama: allowed
   └─ External → Database: DENIED

STORAGE:
├─ Document storage (MinIO):
│  └─ S3 bucket on AWS (or Azure Blob)
│
├─ Vector storage (Chroma):
│  └─ Persistent volume (EBS/Azure Disk)
│
└─ Metadata (PostgreSQL):
   └─ Managed database (RDS/Azure Database)

MONITORING:
├─ Prometheus (metrics)
├─ Grafana (dashboards)
├─ ELK Stack (logs)
└─ PagerDuty (alerts)
```

---

### Q22: What are the security considerations?

**Answer:**

```
SECURITY LAYERS:

1. NETWORK SECURITY
   ├─ TLS/HTTPS for all external traffic
   ├─ VPC/Private subnet for databases
   ├─ Network policies restrict pod communication
   ├─ WAF (Web Application Firewall)
   └─ DDoS protection

2. AUTHENTICATION & AUTHORIZATION
   ├─ OAuth 2.0 / OIDC for users
   ├─ API keys for service-to-service
   ├─ JWT tokens with expiration
   ├─ RBAC for document access
   └─ Audit logging for all access

3. DATA ENCRYPTION
   ├─ Encryption in transit: TLS 1.3
   ├─ Encryption at rest:
   │  ├─ Database: AES-256
   │  ├─ Storage: S3 Server-side encryption
   │  └─ Cache: Redis auth + TLS
   └─ Secrets management: HashiCorp Vault

4. DOCUMENT SECURITY
   ├─ Sensitive document tagging
   ├─ Redaction during search
   ├─ PII detection and masking
   └─ Document retention policies

5. LLMAPI SECURITY
   ├─ Ollama: Local (no external calls)
   ├─ Model isolation
   ├─ Prompt injection prevention:
   │  └─ Validate & sanitize prompts
   │  └─ Use system prompts effectively
   │  └─ Output filtering
   └─ Rate limiting per user

6. INFRASTRUCTURE SECURITY
   ├─ Container scanning (Trivy)
   ├─ Image signing (Cosign)
   ├─ RBAC in Kubernetes
   ├─ Pod security policies
   ├─ Network segmentation
   └─ Regular patching & updates

7. MONITORING & ALERTS
   ├─ Intrusion detection
   ├─ Anomaly detection
   ├─ Failed login alerts
   ├─ Data access anomalies
   └─ Alert thresholds tuned
```

---

## Section 9: Cost Analysis & Trade-offs

### Q23: What are the cost drivers?

**Answer:**

```
MONTHLY COST BREAKDOWN (100,000 documents):

INFRASTRUCTURE COSTS:
├─ Compute
│  ├─ API servers (5 × m5.large): $300
│  ├─ Ollama GPU servers (2 × g4dn.xlarge): $1,400
│  └─ Airflow workers (8 × m5.xlarge): $900
│  └─ Subtotal: $2,600
│
├─ Storage
│  ├─ Document storage (S3): $500/month (1TB)
│  ├─ Vector DB (100Gi): $200
│  ├─ Database backup: $100
│  └─ Subtotal: $800
│
├─ Network
│  ├─ Data transfer: $100-300
│  └─ Load balancers: $50
│  └─ Subtotal: $350
│
└─ Services
   ├─ Managed database: $200
   ├─ Managed Kubernetes: $150
   └─ Monitoring/Logging: $100
   └─ Subtotal: $450

TOTAL: ~$4,200/month

COST OPTIMIZATION STRATEGIES:
1. Use spot instances for workers (-40%)
2. Reserved instances for base load (-20%)
3. Compress document storage (-30%)
4. Use smaller embedding dimension (-50%)
5. Auto-scale based on usage (-25%)

Optimized total: ~$2,000/month
```

---

### Q24: What are the key trade-offs in this design?

**Answer:**

| Trade-off | Choice | Pros | Cons |
|-----------|--------|------|------|
| **Embedding Dim** | 768 | High accuracy | Slower, more memory |
| **LLM Model** | orca-mini | Cheaper, local | Less capable than GPT-4 |
| **Storage** | MinIO | Open-source | No replication, single point |
| **DAG Schedule** | Daily | Simple, predictable | 24h latency for new docs |
| **Search Method** | Semantic | Better results | Can't do exact match |
| **Caching** | Redis | Fast, scalable | Adds complexity |
| **Deployment** | Kubernetes | Scalable | Complex, operational overhead |

**Recommended Trade-offs**:
- **Accuracy vs Latency**: Current 768-dim is good balance
- **Cost vs Performance**: Switch to 384-dim if cost-critical
- **Simplicity vs Scale**: Add Kafka for >1000 docs/day
- **Self-hosted vs Managed**: Use managed DB to reduce ops work

---

## Section 10: Interview Tips & Summary

### Q25: Common follow-up questions and answers

**"How would you handle document updates?"**
```
Option 1: Re-index entire document
- Delete old chunks by document ID
- Re-process and re-embed
- Upsert to Chroma (same ID = replacement)

Option 2: Incremental indexing
- Detect changes (hash or timestamp)
- Only re-embed changed sections
- Faster but more complex

Recommended: Option 1 for simplicity
```

**"What about multi-language documents?"**
```
- Use multilingual embedding model (multilingual-e5)
- Smaller dimension (384) to handle 100+ languages
- Add language detection to metadata
- May need separate LLM for each language
```

**"How do you prevent hallucinations?"**
```
1. Limit LLM context to retrieved documents
2. Use temperature=0.7 (not too creative)
3. Require source citations
4. Fact-check against knowledge base
5. Human review for critical answers
```

**"Can you scale beyond 1 million documents?"**
```
Yes, but architectural changes needed:
1. Separate read/write paths
2. Distributed vector DB (Milvus/Weaviate)
3. Sharding by document domain
4. Cloud-scale infrastructure
5. Estimated cost: $10,000-50,000/month
```

---

## Quick Reference: Architecture Decision Record

| Decision | Rationale | Alternatives Considered |
|----------|-----------|------------------------|
| **Chroma** | Open-source, Python-friendly, good Ollama integration | Pinecone, Weaviate, Milvus |
| **Ollama** | Local LLM, no API costs, orca-mini sufficient | OpenAI API, Hugging Face, vLLM |
| **Airflow** | Mature, DAG-native, great error handling | Prefect, Dagster, Luigi |
| **FastAPI** | Modern, fast, easy to deploy | Flask, Django, Starlette |
| **Next.js** | Full-stack React, SSR, great DX | Vue, Angular, Svelte |
| **MinIO** | S3-compatible, self-hosted, open-source | AWS S3, Azure Blob, GCS |
| **PostgreSQL** | Reliable, ACID, Airflow default | MySQL, MongoDB, DynamoDB |
| **Celery** | Distributed tasks, Redis broker, fault-tolerant | RQ, APScheduler, Dask |
| **Docker** | Industry standard, reproducible, portable | Singularity, Podman, Nix |

---

## Summary

This system demonstrates a production-grade RAG platform balancing:
- **Scalability**: From 100 to 100,000+ documents
- **Performance**: Sub-second searches, 2-5s LLM responses
- **Privacy**: All local processing, no external APIs
- **Maintainability**: Docker, Kubernetes-ready, open-source stack
- **Cost**: ~$2,000-4,000/month for enterprise scale

The architecture is interview-ready and can be explained at multiple levels of detail depending on the interviewer's interests.

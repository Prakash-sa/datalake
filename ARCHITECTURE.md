# System Architecture & Design

Comprehensive documentation of the Document RAG Engine architecture, components, and design decisions.

## Overview

The Document RAG (Retrieval-Augmented Generation) Engine is a production-ready system for semantic search and intelligent document analysis using LLMs.

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Applications                       │
│              (Web, Mobile, CLI, Third-party APIs)               │
└────────────────────────────┬────────────────────────────────────┘
                             │
                   HTTP/HTTPS │ REST API
                             │
        ┌────────────────────▼────────────────────┐
        │      FastAPI Application                │
        │  (Input Validation & Error Handling)    │
        │                                         │
        │  ┌─────────────────────────────────┐   │
        │  │    Request/Response Models       │   │
        │  │  (Pydantic with Validators)     │   │
        │  └─────────────────────────────────┘   │
        └────────────────────┬────────────────────┘
                             │
            ┌────────────────┼────────────────┐
            │                │                │
      ┌─────▼──────┐   ┌────▼────┐   ┌─────▼──────┐
      │  /query    │   │/search  │   │  /index    │
      │ (Full RAG) │   │(Search) │   │(Indexing)  │
      └─────┬──────┘   └────┬────┘   └─────┬──────┘
            │                │              │
            └────────────────┼──────────────┘
                             │
        ┌────────────────────▼────────────────────┐
        │     RAG Engine (rag_engine.py)          │
        │                                         │
        │  ┌──────────────────────────────────┐  │
        │  │  Semantic Search Pipeline        │  │
        │  │ (Query -> Embedding -> Search)   │  │
        │  └──────────────────────────────────┘  │
        │                                         │
        │  ┌──────────────────────────────────┐  │
        │  │  LLM Analysis Pipeline           │  │
        │  │ (Results -> LLM -> Analysis)     │  │
        │  └──────────────────────────────────┘  │
        │                                         │
        │  ┌──────────────────────────────────┐  │
        │  │  Configuration & Monitoring      │  │
        │  │ (Stats, Logging, Validation)    │  │
        │  └──────────────────────────────────┘  │
        └───────┬──────────────────────────┬─────┘
                │                          │
        ┌───────▼─────┐            ┌──────▼──────┐
        │   Ollama    │            │ In-Memory   │
        │ (LLM + Emb) │            │ Vector DB   │
        │             │            │ (Chroma)    │
        └─────────────┘            └─────────────┘
```

## Component Architecture

### 1. FastAPI Application Layer

**File**: `main.py`  
**Purpose**: REST API gateway with request/response handling

**Responsibilities**:
- HTTP request routing
- Input validation (Pydantic models)
- Error handling (400, 500 status codes)
- Response formatting and serialization
- CORS management
- Health check and monitoring endpoints

**Key Classes**:
- `DocumentQueryRequest`: Query validation model
- `DocumentSearchRequest`: Search validation model
- `DocumentIndexRequest`: Indexing validation model
- `HealthResponse`: Health check response
- `QueryResponse`: Query result format

**Endpoints**:
```python
GET  /                    # API info
GET  /health             # Health check for orchestration
GET  /stats              # Engine statistics
POST /query              # Full RAG query (search + LLM)
POST /documents/search   # Semantic search only
POST /documents/index    # Index new documents
```

**Error Handling**:
- Global exception handlers for ValueError (400) and Exception (500)
- JSON responses with timestamp and status code
- Detailed error messages with validation hints

### 2. RAG Engine Layer

**File**: `rag_engine.py`  
**Purpose**: Core semantic search and LLM integration logic

**Responsibilities**:
- Document indexing with embeddings
- Semantic similarity search
- LLM-powered analysis and question answering
- Resource management and validation
- Statistics and monitoring tracking
- Timeout and error handling

**Key Class**: `DocumentRAGEngine`

**Methods**:

#### `__init__()`
Initializes the engine with:
- Embedding model (Ollama)
- LLM model (Ollama)
- Vector store (Chroma)
- Configuration and limits
- Statistics tracking

```python
def __init__(
    self,
    embedding_model: str = "all-minilm",
    llm_model: str = "mistral",
    temperature: float = 0.5,
    max_documents: int = 10000,
    max_query_length: int = 1000
):
    # Initialize components
    # Set resource limits
    # Initialize stats tracking
```

#### `index_documents(documents, batch_size=5)`
Batch index documents with error handling:
- Validates document format
- Generates embeddings
- Stores in vector database
- Tracks per-document errors
- Returns partial_success status

```python
def index_documents(documents: List[Dict]) -> Dict:
    return {
        "status": "success" | "partial_success" | "error",
        "documents_indexed": int,
        "errors": int,
        "details": [{"id": str, "error": str}]
    }
```

#### `search_documents(query, k=5, min_score=0.0)`
Semantic search without LLM:
- Validates query length
- Generates query embedding
- Finds k most similar documents
- Filters by relevance score
- Truncates content (500 chars)

```python
def search_documents(
    query: str,
    k: int = 5,
    min_score: float = 0.0
) -> List[Dict]:
    return [
        {
            "id": str,
            "content": str,
            "relevance_score": float,  # 0.0-1.0
            "metadata": Dict
        }
    ]
```

#### `query_documents(query, k=5, timeout=30)`
Full RAG with LLM analysis:
- Searches for relevant documents
- Passes to LLM for analysis
- Includes processing time
- Handles timeouts gracefully

```python
def query_documents(
    query: str,
    k: int = 5,
    timeout: int = 30
) -> Dict:
    return {
        "query": str,
        "results": [search_results],
        "llm_analysis": str,
        "processing_time_seconds": float,
        "status": "success" | "error"
    }
```

#### `get_stats()`
Returns engine statistics:
```python
def get_stats() -> Dict:
    return {
        "documents_indexed": int,
        "queries_processed": int,
        "errors": int,
        "total_documents": int,
        "timestamp": str
    }
```

### 3. Configuration Layer

**File**: `config.py`  
**Purpose**: Environment-based configuration management

**Classes**:
- `Config`: Base configuration class
- `DevelopmentConfig`: Development settings
- `ProductionConfig`: Production settings
- `TestingConfig`: Testing settings

**Features**:
- Environment variable sourcing
- Sensible defaults for each environment
- Type validation with Pydantic
- Multi-environment support

```python
def get_config() -> Config:
    """Factory function to get correct config"""
    env = os.getenv("ENV", "production").lower()
    if env == "development":
        return DevelopmentConfig()
    elif env == "testing":
        return TestingConfig()
    else:
        return ProductionConfig()
```

**Configuration by Environment**:

| Setting | Development | Testing | Production |
|---------|-------------|---------|-----------|
| DEBUG | true | true | false |
| LOG_LEVEL | DEBUG | DEBUG | INFO |
| WORKERS | 1 | 1 | 4 |
| ALLOWED_ORIGINS | * | * | specific |
| QUERY_TIMEOUT | 30s | 5s | 30s |

### 4. Supporting Infrastructure

**Docker Services**:

#### Ollama
- **Purpose**: LLM and embedding model inference
- **Port**: 11434
- **Models**: all-minilm (embedding), mistral (LLM)
- **Features**: GPU support, persistent models

#### MinIO
- **Purpose**: S3-compatible document storage
- **Port**: 9000 (API), 9001 (console)
- **Features**: Bucket management, access control
- **Data**: /data volume

#### Prometheus (Optional)
- **Purpose**: Metrics collection
- **Port**: 9090
- **Features**: Time-series database, querying

#### Grafana (Optional)
- **Purpose**: Metrics visualization
- **Port**: 3001
- **Features**: Dashboards, alerting

## Data Flow Diagrams

### Indexing Flow

```
User Request
    │
    ▼
┌─────────────────────┐
│ POST /documents/index
│ - Validate documents
│ - Check max count
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ RAG Engine
│ - Batch documents
│ - Generate embeddings
│ - Store in vector DB
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Vector Database
│ (Chroma with Ollama
│  embeddings)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Return Response
│ - Status: success
│ - Count: indexed
│ - Errors: details
└─────────────────────┘
```

### Search Flow

```
User Request
    │
    ▼
┌─────────────────────┐
│ POST /documents/search
│ - Validate query
│ - Check query length
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ RAG Engine
│ - Generate query
│   embedding
│ - Search for k
│   similar docs
│ - Filter by score
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Vector Database
│ (Similarity search)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Return Results
│ - Documents found
│ - Relevance scores
│ - Metadata
└─────────────────────┘
```

### Full RAG Query Flow

```
User Request
    │
    ▼
┌──────────────────────┐
│ POST /query
│ - Validate input
│ - Set timeout
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Search Documents
│ - Generate embedding
│ - Find top-k results
│ - Prepare context
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Prepare LLM Prompt
│ - System context
│ - Retrieved docs
│ - User question
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Call LLM (Ollama)
│ - Stream response
│ - Measure time
│ - Handle timeout
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Return Full Response
│ - Query
│ - Search results
│ - LLM analysis
│ - Processing time
└──────────────────────┘
```

## Performance Characteristics

### Time Complexity

| Operation | Complexity | Notes |
|-----------|-----------|-------|
| Index document | O(1) | Per document (batch) |
| Generate embedding | O(n) | n = content length |
| Search similarity | O(k log m) | k = results, m = total docs |
| LLM inference | O(output_tokens) | Depends on model |

### Space Complexity

| Component | Space | Notes |
|-----------|-------|-------|
| Vector store | O(d*m) | d = embedding dim, m = docs |
| Embedding cache | O(k*d) | LRU cache, max k items |
| Document store | O(m*c) | m = docs, c = content size |

### Performance Targets

- **Search**: < 100ms for k=5
- **Query**: 1-3 seconds for full RAG
- **Indexing**: 10-50ms per document
- **Throughput**: 10+ concurrent queries

## Scalability Patterns

### Horizontal Scaling

```
┌─────────────────────────┐
│   Load Balancer         │
│   (Nginx/HAProxy)       │
└────────────┬────────────┘
             │
    ┌────────┼────────┐
    │        │        │
┌───▼──┐ ┌──▼───┐ ┌──▼───┐
│ RAG1 │ │ RAG2 │ │ RAG3 │
└───┬──┘ └──┬───┘ └──┬───┘
    │       │       │
    └───────┼───────┘
            │
    ┌───────▼──────┐
    │ Shared Ollama│
    │ (or local)   │
    └──────────────┘
```

### Vertical Scaling

```
Backend Service
├── Workers: 1 → 4 → 8 → 16
├── Memory: 2GB → 4GB → 8GB → 16GB
├── CPU: 1 core → 2 cores → 4 cores → 8 cores
└── Cache: 128 → 256 → 512 → 1024
```

## Security Architecture

### Authentication & Authorization

```
Client Request
    │
    ▼
┌──────────────────────┐
│ API Key / JWT Check  │
│ (Optional Layer)     │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Rate Limiting        │
│ (Prevent DOS)        │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Input Validation     │
│ (Pydantic Models)    │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Process Request      │
│ (RAG Engine)         │
└──────────────────────┘
```

### Network Security

- HTTPS/TLS encryption (reverse proxy)
- CORS policy enforcement
- Rate limiting per IP/token
- Request size limits
- SQL injection prevention (N/A - no SQL)

### Data Security

- Non-root container user
- Environment variable secrets
- No sensitive data in logs
- Data at rest encryption (optional)
- Access control to MinIO buckets

## Monitoring & Observability

### Metrics Exported

```
# Request metrics
http_requests_total{method, status, endpoint}
http_request_duration_seconds{method, endpoint}

# RAG metrics
rag_documents_indexed_total
rag_queries_processed_total
rag_errors_total

# System metrics
process_cpu_seconds_total
process_resident_memory_bytes
python_gc_objects_collected_total
```

### Logging Strategy

```
Development:  DEBUG - All details
Testing:      DEBUG - All test operations
Production:   INFO - Key events only, errors detailed
```

**Log Format**:
```
TIMESTAMP LEVEL MODULE:FUNCTION MESSAGE [context]
2024-01-15 10:30:45,123 INFO main:query_documents Query processed in 2.34s [query_id=abc123]
```

## Deployment Architecture

### Development Deployment

```
┌──────────────────────┐
│ Docker Compose (dev) │
│                      │
├─ Ollama (1 worker)   │
├─ MinIO              │
├─ RAG Backend        │
│  └─ 1 Uvicorn worker│
└──────────────────────┘
```

### Production Deployment

```
┌────────────────────────────────────────┐
│ Docker Compose (production)            │
│                                        │
├─ Ollama (with GPU support)            │
├─ MinIO (persistent volumes)           │
├─ RAG Backend (Gunicorn)               │
│  ├─ 4 Uvicorn workers                 │
│  ├─ Health checks                     │
│  └─ Resource limits (CPU/Memory)      │
├─ Prometheus (metrics)                 │
└─ Grafana (dashboards)                 │
```

### Kubernetes Deployment

```
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rag-backend
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
  template:
    spec:
      containers:
      - name: rag-backend
        image: rag-engine:prod
        resources:
          requests:
            cpu: 1
            memory: 2Gi
          limits:
            cpu: 2
            memory: 4Gi
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
```

## Technology Stack

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| **API** | FastAPI | 0.104+ | REST framework |
| **Validation** | Pydantic | 2.0+ | Input validation |
| **LLM** | Ollama | latest | Model inference |
| **Embeddings** | Ollama | latest | Vector embeddings |
| **Vector DB** | Chroma | latest | Semantic search |
| **Server** | Gunicorn | 21.2.0+ | WSGI server |
| **Container** | Docker | 24.0+ | Containerization |
| **Monitoring** | Prometheus | latest | Metrics |
| **Dashboard** | Grafana | latest | Visualization |
| **Python** | 3.11+ | LTS | Runtime |

## Design Decisions & Rationale

### 1. In-Memory Vector Store (Chroma)

**Decision**: Use Chroma with in-memory storage instead of external vector DB

**Rationale**:
- Simplicity: No external dependencies
- Performance: Sub-millisecond search
- Cost: Zero infrastructure overhead
- Tradeoff: Limited to single instance

**Alternative Considered**:
- Pinecone, Weaviate, Milvus → External dependencies

### 2. Ollama for LLM & Embeddings

**Decision**: Use Ollama for both LLM and embedding models

**Rationale**:
- Unified interface: Same service for both
- Open models: No API keys required
- Local execution: Privacy and cost
- Flexibility: Swap models easily

**Alternative Considered**:
- OpenAI API → Cost and privacy concerns
- HuggingFace Inference → Additional dependencies

### 3. FastAPI with Pydantic

**Decision**: Use FastAPI for REST API with Pydantic validation

**Rationale**:
- Type safety: Automatic validation
- Performance: Fast execution
- Documentation: Auto-generated Swagger UI
- Developer experience: Clean, Pythonic

### 4. Gunicorn + Uvicorn

**Decision**: Use Gunicorn with Uvicorn workers for production

**Rationale**:
- Horizontal scaling: Multiple workers
- Process management: Automatic respawning
- Mature: Proven in production
- Load balancing: Built-in request distribution

### 5. Docker Compose for Orchestration

**Decision**: Use Docker Compose for both dev and production

**Rationale**:
- Simplicity: Single file configuration
- Consistency: Dev parity with prod
- Portability: Works on all platforms

**Alternative Considered**:
- Kubernetes → Overkill for current scale

## Future Enhancements

1. **Distributed Vector Store**: Move to external service for multi-instance
2. **Advanced Caching**: Redis for distributed caching
3. **Authentication**: JWT token support
4. **Rate Limiting**: Per-user API quotas
5. **Async Indexing**: Background job queue
6. **Model Serving**: Fine-tuned models per domain
7. **Analytics**: Document popularity, query patterns
8. **Multi-Tenancy**: Isolated data per tenant

---

**Last Updated**: 2024-01-15  
**Status**: ✅ Production Ready  
**Architecture Version**: 2.0


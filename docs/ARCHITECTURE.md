# DataLake RAG System - Architecture

## System Overview

This is an enterprise-grade Document Retrieval-Augmented Generation (RAG) system designed for semantic search and LLM-powered analysis of large document collections.

### Core Design Principles

- **Separation of Concerns**: Orchestration, services, and infrastructure clearly separated
- **Scalability**: Horizontally scalable components with distributed processing
- **Resilience**: Health checks, retry mechanisms, persistent state management
- **Observability**: Comprehensive logging, monitoring, and health checks
- **Security**: Authentication, isolation, secrets management

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER LAYER                               │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Next.js React Frontend (Port 3000)                      │   │
│  │  - Real-time document queries                            │   │
│  │  - Search results visualization                          │   │
│  │  - Responsive UI                                         │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────┬──────────────────────────────────────────┘
                       │ HTTP/REST
┌──────────────────────▼──────────────────────────────────────────┐
│                    API LAYER                                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  FastAPI RAG Backend (Port 8000)                         │   │
│  │  - Semantic search endpoint                              │   │
│  │  - Document indexing API                                 │   │
│  │  - Query & response handling                             │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────┬──────────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
        ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  Document    │ │  Embedding   │ │  Query       │
│  Ingestion   │ │  Generation  │ │  Processing  │
│              │ │              │ │              │
│  Airflow +   │ │  Ollama      │ │  Chroma +    │
│  MinIO       │ │              │ │  LangChain   │
└──────────────┘ └──────────────┘ └──────────────┘
        │              │              │
└───────┴──────────────┼──────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
        ▼              ▼              ▼
┌──────────────────┐ ┌───────────┐ ┌─────────────────┐
│   STORAGE        │ │ COMPUTE   │ │  ORCHESTRATION  │
├──────────────────┤ ├───────────┤ ├─────────────────┤
│ MinIO (S3)       │ │ Ollama    │ │ Apache Airflow  │
│ Chroma (Vector) │ │ (Local    │ │ - DAG execution │
│ PostgreSQL (Meta)│ │  LLM)     │ │ - Scheduling    │
└──────────────────┘ └───────────┘ └─────────────────┘
```

## Component Architecture

### 1. Orchestration Layer (`src/orchestration/`)

#### Apache Airflow 2.9.0
- **Purpose**: Workflow orchestration and scheduling
- **Components**:
  - Webserver (HTTP API & UI at port 9093)
  - Scheduler (Task scheduling & execution planning)
  - Worker (Celery task execution)
  - Triggerer (Event-driven task triggering)

#### DAGs
- `document_rag_ingestion_pipeline` - Daily document ingestion workflow
  1. Fetch documents from MinIO
  2. Process & chunk documents
  3. Generate embeddings with Ollama
  4. Upsert to Chroma vector DB
  5. Validate indexing completion

### 2. Service Layer (`src/services/`)

#### RAG Engine Backend (FastAPI)
- **Purpose**: REST API for RAG operations
- **Endpoints**:
  - `POST /documents/search` - Semantic search
  - `POST /documents/index` - Manual indexing
  - `POST /query` - LLM-powered query response
  - `GET /health` - Health check

#### Frontend (Next.js)
- **Purpose**: User interface for document search
- **Features**:
  - Real-time query execution
  - Search result visualization
  - Document preview
  - Query history

### 3. Infrastructure Layer

#### Storage Services
- **MinIO**: S3-compatible object storage (Port 9000)
  - Bucket: `documents/` for uploaded files
  - CORS enabled for frontend access

- **Chroma**: Vector database (Port 8001)
  - Collection: `documents` with HNSW indexing
  - Persistent storage: `./volumes/chroma_data/`

- **PostgreSQL**: Relational database (Port 5432)
  - Airflow metadata & state
  - User & connection information

#### Compute Services
- **Ollama**: Local LLM inference (Port 11434)
  - Model: `nomic-embed-text` (768-dim embeddings)
  - CPU-optimized inference
  - No external API calls

#### Messaging & Caching
- **Redis**: Message broker & cache (Port 6379)
  - Celery task queue for Airflow
  - Session caching
  - Rate limiting

## Data Flow

### Document Ingestion Pipeline

```
1. UPLOAD
   User/System → MinIO (S3)
   └─ File stored in `documents` bucket

2. TRIGGER
   Daily schedule → Airflow Scheduler
   └─ Triggers `document_rag_ingestion_pipeline` DAG

3. FETCH
   Airflow Worker → MinIO API
   └─ Retrieve document list & content (max 5000 chars)

4. PROCESS
   Process Task → LangChain TextSplitter
   └─ Chunk documents (1000 chars, 200 overlap)
   └─ Add metadata (source, timestamp, chunk index)

5. EMBED
   Embedding Task → Ollama API
   └─ Generate 768-dim embeddings per chunk
   └─ Batch processing (10 docs at a time)

6. INDEX
   Upsert Task → Chroma API
   └─ Store embeddings + metadata
   └─ HNSW indexing for similarity search

7. VALIDATE
   Validation Task → Chroma Query
   └─ Verify collection stats
   └─ Test sample queries
   └─ Generate validation report
```

### Query Execution Flow

```
1. USER QUERY
   Frontend Input → FastAPI Backend
   └─ Example: "What is Kubernetes?"

2. EMBEDDING
   Backend → Ollama API
   └─ Convert query to 768-dim embedding

3. SEARCH
   Backend → Chroma API
   └─ Semantic similarity search
   └─ Return top-5 matching chunks with scores

4. LLM RESPONSE
   Backend → Ollama LLM
   └─ Prompt: Query + Context + Instructions
   └─ Generate natural language response

5. RESPONSE
   Backend → Frontend
   └─ JSON response with results & sources
   └─ Display in UI with relevance scores
```

## Technology Stack

| Layer | Technology | Purpose | Version |
|-------|-----------|---------|---------|
| **Orchestration** | Apache Airflow | Workflow scheduling | 2.9.0 |
| **Backend** | FastAPI | REST API | 0.104+ |
| **Frontend** | Next.js | Web UI | 14+ |
| **Vector DB** | Chroma | Embeddings storage | 0.4.24+ |
| **LLM** | Ollama | Local inference | latest |
| **Storage** | MinIO | S3-compatible | latest |
| **Database** | PostgreSQL | Metadata store | 13 |
| **Broker** | Redis | Task queue | 7 |
| **Runtime** | Docker | Containerization | 24+ |
| **Orchestration** | Docker Compose | Multi-container | 3.8+ |

## Performance Characteristics

### Scalability
- **Horizontal**: Add Airflow workers for parallel DAG execution
- **Vertical**: Increase Ollama threads, Chroma index size
- **Storage**: MinIO can handle petabyte-scale collections

### Throughput
- **Document Processing**: ~10 docs/min (depends on size)
- **Query Latency**: ~200-500ms (search + embedding + response)
- **Embedding Generation**: ~100 chunks/min with Ollama CPU

### Reliability
- **Airflow Retries**: 2 attempts per task with 5-min delay
- **Health Checks**: All services monitored every 30s
- **Data Persistence**: Volumes survive container restarts

## Security

### Authentication
- Airflow: Basic auth (username/password)
- MinIO: Access key/secret
- API: No auth (localhost-only in dev, add OAuth in prod)

### Network Isolation
- Services on dedicated Docker networks
- Airflow on `airflow-network`
- RAG services on `rag-network`
- No external network exposure

### Secrets Management
- Credentials in `.env` file (not versioned)
- Environment variable injection
- PostgreSQL password protection
- Redis no authentication (internal network)

## Monitoring & Observability

### Health Checks
- Airflow Webserver: HTTP `/health` endpoint
- RAG Backend: HTTP `/health` endpoint  
- Frontend: HTTP `/` response check
- Infrastructure: Database connectivity, port availability

### Logging
- Airflow: `/volumes/airflow_logs/` (task logs)
- FastAPI: Uvicorn stdout/stderr
- Docker: `docker-compose logs [service]`
- All logs timestamped and searchable

### Metrics (Optional)
- Airflow: Task execution time, success/failure rates
- Chroma: Index size, query latency
- Ollama: Model inference time, queue depth
- System: CPU, memory, disk usage

## Deployment Patterns

### Development (Current)
- Single docker-compose.yml with all services
- Localhost access only
- Persistent volumes for data
- Debug logging enabled

### Staging
- Same docker-compose, different .env
- SSL/TLS for API endpoints
- Basic monitoring & alerting
- Backup volumes configuration

### Production (Recommended)
- Kubernetes manifests with resource limits
- Persistent volumes on shared storage
- Service mesh (Istio) for networking
- Comprehensive monitoring & logging
- Auto-scaling based on queue depth
- Database replication & backup
- Load balancer for high availability

## Troubleshooting Guide

### Service won't start
1. Check Docker daemon: `docker ps`
2. View logs: `docker-compose logs [service]`
3. Verify ports: `lsof -i :PORT`
4. Restart: `./scripts/stop.sh && ./scripts/start.sh`

### Documents not indexed
1. Verify MinIO has documents: `localhost:9001`
2. Check Airflow DAG: `http://localhost:9093/dags`
3. View worker logs: `docker-compose logs airflow-worker`
4. Ensure Ollama is running: `curl localhost:11434/api/tags`

### Query returns no results
1. Check Chroma collection: `curl localhost:8001/api/v1/collections`
2. Verify embeddings exist: Check collection count
3. Test with simple query: "hello" or "test"
4. Check similarity threshold in code

## Future Enhancements

- [ ] Kubernetes deployment manifests
- [ ] Multi-user authentication with OAuth2
- [ ] Advanced search filters & facets
- [ ] Document streaming for large files
- [ ] Real-time document updates
- [ ] Analytics & usage tracking
- [ ] Custom LLM model deployment
- [ ] Distributed Chroma across regions

---

Last Updated: December 2025
Version: 1.0.0 Production

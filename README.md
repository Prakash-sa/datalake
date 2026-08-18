# 🚀 Enterprise Document RAG Platform

## 🎯 Semantic Search & LLM Analysis at Scale

A production-grade **Retrieval Augmented Generation (RAG) system** for intelligent document discovery and analysis across large enterprise document collections. 

### Key Features
- **🔍 Semantic Search** - Find documents by meaning, not just keywords
- **🤖 LLM-Powered Answers** - Generate context-aware responses from documents
- **⚡ Real-time Ingestion** - Automated document processing via Airflow DAGs
- **🔒 No prerequisites** - Import and search need no external software; embeddings run in-process
- **🔒 Enterprise-Ready** - No external APIs, all local inference
- **📊 Vector Database** - Efficient similarity search at scale
- **🎨 Modern UI** - Intuitive Next.js frontend for document exploration

### Technology Stack
| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Orchestration** | Apache Airflow | Document ingestion pipeline scheduling |
| **API** | FastAPI | High-performance REST API for search & analysis |
| **Frontend** | Next.js 14 | Modern React UI with Tailwind CSS |
| **Vector DB** | Chroma | Persistent storage for embeddings (384/768-dim) |
| **LLM** | Ollama | Local inference with orca-mini & nomic-embed-text |
| **Storage** | MinIO | S3-compatible object storage for documents |
| **Database** | PostgreSQL | Metadata, state, and Airflow scheduling |
| **Message Broker** | Redis | Celery task queue and caching |
| **Execution** | Celery | Distributed task execution for DAGs |

## 🏗️ System Architecture

### Data Flow Diagram
```
┌─────────────────────────────────────────────────────────────┐
│                     USER INTERFACE                          │
│  Next.js Frontend (http://localhost:3000)                   │
└─────────────┬───────────────────────────────────────────────┘
              │ HTTP/JSON
              ↓
┌─────────────────────────────────────────────────────────────┐
│                   QUERY PROCESSING                          │
│  FastAPI Backend (http://localhost:8000)                    │
│  - /documents/search          (semantic search)             │
│  - /documents/ask             (LLM with context)            │
│  - /documents/health          (health check)                │
└──────────┬────────────────────────────┬────────────────────┘
           │                            │
           ↓                            ↓
    ┌─────────────┐          ┌──────────────────┐
    │   Chroma    │          │   Ollama LLM     │
    │   Vector DB │          │   Inference      │
    │ (Embeddings)│          │ (orca-mini)      │
    └─────────────┘          └──────────────────┘
           ↑
           │ Embedding generation
           │ (nomic-embed-text)
           │
┌──────────┴────────────────────────────────────────┐
│         DOCUMENT INGESTION PIPELINE               │
│     Apache Airflow DAG (Port 9093)                │
│                                                    │
│  1. Fetch Documents    (from MinIO)               │
│  2. Process Documents  (chunk & split)            │
│  3. Create Embeddings  (via Ollama)               │
│  4. Upsert to Chroma   (vector storage)           │
│  5. Validate Results   (verify indexing)          │
│  6. Notify Completion  (log summary)              │
└──────────┬────────────────────────────────────────┘
           │
           ↓
    ┌─────────────────┐
    │     MinIO       │
    │ S3-Compatible   │
    │    Storage      │
    │ (Port 9000)     │
    └─────────────────┘

Infrastructure:
- PostgreSQL (Port 5432)    - Airflow metadata & state
- Redis (Port 6379)         - Celery broker & cache
- Chroma (Port 8000)        - Vector database
```

### Component Details

**Frontend (Next.js)**
- User interface for document search and Q&A
- Real-time response streaming
- Environment: `NEXT_PUBLIC_API_URL=http://localhost:8000`

**API Server (FastAPI)**
- REST endpoints for semantic search and LLM queries
- CORS enabled for localhost:3000
- Graceful degradation when LLM unavailable
- Returns search results with formatted context

**Vector Database (Chroma)**
- Persistent storage: `/opt/airflow/chroma_db`
- Collection: "documents" (768-dimensional embeddings)
- Search method: cosine similarity
- Automatic compression and indexing

**Orchestration (Airflow)**
- Scheduler: Processes DAGs and schedules tasks
- Worker: Executes tasks via Celery
- Executor: Celery with Redis broker
- DAG: `document_rag_ingestion_pipeline` (daily schedule)

**Storage (MinIO)**
- S3-compatible API at `http://minio:9000`
- Console: `http://localhost:9001`
- Bucket: "documents"
- Used for staging uploaded documents

## 📚 Documentation

Complete documentation is organized in the `docs/` folder:

Start at [docs/INDEX.md](docs/INDEX.md) for the full map.

| Document | Purpose |
|----------|---------|
| [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) | Detailed system design, components, data flow |
| [backend/ARCHITECTURE.md](backend/ARCHITECTURE.md) | Backend layering, composition, retrieval pipeline |
| [docs/operations/DEPLOYMENT.md](docs/operations/DEPLOYMENT.md) | Setup for dev/staging/production, Kubernetes |
| [docs/reference/API_REFERENCE.md](docs/reference/API_REFERENCE.md) | REST API endpoints, request/response examples |
| [docs/operations/TROUBLESHOOTING.md](docs/operations/TROUBLESHOOTING.md) | Common issues, solutions, debugging guide |
| [docs/architecture/SYSTEM_DESIGN_INTERVIEW.md](docs/architecture/SYSTEM_DESIGN_INTERVIEW.md) | System design walkthrough in Q&A form |

### Port Reference
| Service | Port | URL |
|---------|------|-----|
| Frontend | 3000 | http://localhost:3000 |
| API | 8000 | http://localhost:8000 |
| Airflow Web | 9093 | http://localhost:9093 |
| MinIO Console | 9001 | http://localhost:9001 |
| Chroma | 8000 | http://localhost:8000 |
| Ollama | 11434 | http://localhost:11434 |
| PostgreSQL | 5432 | localhost:5432 |
| Redis | 6379 | localhost:6379 |

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose installed
- 4GB RAM minimum (8GB recommended for full Ollama)
- macOS/Linux/Windows with WSL2

### 1. Start Services
```bash
cd datalake-project
cp compose/.env.example compose/.env

make up              # base stack with dev overrides
# make up-airflow    # ...plus the Airflow orchestration stack
# make up-prod       # production overlay, detached

# Verify services are running
docker ps | grep -E "rag-|airflow-|ollama"
```

`make help` lists every target. The equivalent raw command is:

```bash
docker compose -f compose/compose.yml -f compose/compose.dev.yml up --build
```

### 2. Verify Health
```bash
# Check API health
curl http://localhost:8000/health

# Check Ollama models
curl http://localhost:11434/api/tags

# Access UI at http://localhost:3000
```

### 3. Ingest Sample Documents
```bash
# Upload documents via MinIO console
# http://localhost:9001 (minioadmin/minioadmin)
# Create bucket: documents
# Upload sample .txt files
```

### 4. Trigger Airflow Pipeline
```bash
# Access Airflow at http://localhost:9093
# DAG: document_rag_ingestion_pipeline
# Click: "Trigger DAG" button
# Monitor: All 6 tasks should succeed
```

### 5. Search Documents
```bash
# Frontend UI
# http://localhost:3000

# Or use API directly
curl -X POST http://localhost:8000/documents/search \
  -H "Content-Type: application/json" \
  -d '{"query":"your search query"}'
```

### Stop Services
```bash
make down

# Remove volumes too (deletes indexed data)
docker compose -f compose/compose.yml -f compose/compose.dev.yml down -v
```

### Backend development

```bash
make setup-backend   # venv + editable install with dev extras
make check           # lint, format check, type check, tests
make backend-run     # run the API directly
```

## 📂 Project Structure

```
datalake-project/
├── Makefile                          # Developer entry points (`make help`)
├── package.json                      # npm entrypoint for frontend/desktop commands
├── .editorconfig
├── .pre-commit-config.yaml
│
├── compose/                          # Container orchestration
│   ├── compose.yml                   # Base stack: ollama, minio, chroma, backend, frontend
│   ├── compose.dev.yml               # Dev overlay: source mounting and reload
│   ├── compose.prod.yml              # Prod overlay: hardened images, limits, restart
│   ├── compose.airflow.yml           # Add-on: postgres, redis, Airflow services
│   └── .env.example                  # Compose variable template
│
├── backend/                          # FastAPI service
│   ├── pyproject.toml                # Dependencies, lint, test, build config
│   ├── rag-backend.spec              # PyInstaller sidecar bundle
│   ├── ARCHITECTURE.md               # Layering and composition
│   ├── .env.example
│   ├── src/rag_backend/
│   │   ├── app.py                    # create_app() factory
│   │   ├── __main__.py               # `python -m rag_backend`
│   │   ├── settings.py               # Environment-driven config
│   │   ├── lifespan.py               # Startup/shutdown wiring
│   │   ├── dependencies.py           # FastAPI DI providers
│   │   ├── middleware/               # Bearer-token auth
│   │   ├── api/routes/               # health, models, settings, documents, search, evals
│   │   ├── schemas/                  # Request/response models
│   │   ├── domain/                   # Entities, no I/O
│   │   ├── application/              # Use cases and retrieval logic
│   │   └── infrastructure/           # Chroma, Ollama, SQLite adapters
│   └── tests/{unit,integration}/
│
├── frontend/                         # Next.js + Electron desktop UI
│   ├── app/                          # App router pages and styles
│   ├── electron/                     # Main and preload processes
│   ├── scripts/                      # Sidecar packaging
│   └── electron-builder.yml
│
├── evals/                            # Deterministic eval fixtures and guide
│
├── infra/airflow/                    # Airflow image and DAGs
│   ├── dags/rag_vector_db_ingestion_dag.py
│   └── Dockerfile
│
├── ops/scripts/                      # Operational shell scripts
│
├── docs/
│   ├── INDEX.md                      # Documentation map
│   ├── adr/                          # Architecture decision records
│   ├── architecture/                 # System design and diagrams
│   ├── reference/                    # API reference
│   ├── operations/                   # Deployment, pipeline, release, troubleshooting
│   ├── security/                     # Threat model and privacy
│   └── assets/
│
└── volumes/                          # Generated runtime data (git-ignored)
```

## 🎯 Core Features

| Feature | Description | Status |
|---------|-------------|--------|
| **📄 Document Ingestion** | Upload documents via MinIO, process with Airflow | ✅ Production |
| **🔍 Semantic Search** | Find documents by meaning using vector embeddings | ✅ Production |
| **🤖 LLM Integration** | Local Ollama inference for Q&A on documents | ✅ Production |
| **⚡ REST API** | FastAPI with JSON request/response | ✅ Production |
| **🎨 Web UI** | Next.js React interface for end-users | ✅ Production |
| **📊 Vector Database** | Chroma with persistent storage | ✅ Production |
| **🔄 Workflow Automation** | Apache Airflow DAGs for document pipeline | ✅ Production |
| **💾 State Management** | PostgreSQL for Airflow metadata | ✅ Production |
| **⚙️ Task Distribution** | Celery workers with Redis broker | ✅ Production |

## 🔌 API Usage

### Search Documents (Semantic)
```bash
curl -X POST http://localhost:8000/documents/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How to implement caching?",
    "top_k": 5
  }'

# Response: [
#   {
#     "id": "doc1_chunk_0",
#     "content": "...",
#     "similarity_score": 0.92,
#     "metadata": {...}
#   }, ...
# ]
```

### Ask LLM Question (with context)
```bash
curl -X POST http://localhost:8000/documents/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Explain caching strategies",
    "top_k": 3
  }'

# Response: {
#   "question": "Explain caching strategies",
#   "answer": "Based on the documents...",
#   "sources": [
#     {"id": "doc1", "score": 0.91}
#   ],
#   "model": "orca-mini",
#   "timestamp": "2025-12-22T..."
# }
```

### Health Check
```bash
curl http://localhost:8000/health

# Response: {
#   "status": "healthy",
#   "timestamp": "2025-12-22T04:59:40..."
# }
```

## 🔄 Airflow Pipeline Details

### DAG: document_rag_ingestion_pipeline

**Schedule**: Daily at 00:00 UTC
**Timeout**: 2 hours per run

**6-Task Pipeline**:

| # | Task | Input | Output | Purpose |
|---|------|-------|--------|---------|
| 1 | `fetch_documents_from_minio` | Bucket name | `List[Dict]` documents | Retrieve documents from S3 |
| 2 | `process_documents` | `List[Dict]` | `List[Dict]` chunks | Split into chunks (1000 tokens) |
| 3 | `create_embeddings` | `List[Dict]` | `List[Dict]` + vectors | Generate 768-dim embeddings |
| 4 | `upsert_to_chroma` | Embeddings | Upsert stats | Index into vector DB |
| 5 | `validate_vector_db` | Stats | Validation result | Verify indexing success |
| 6 | `notify_completion` | Result dict | Summary log | Log pipeline completion |

**Data Flow**: XCom-based (inter-task communication, no files)

**Retry Policy**: 1 retry on failure

**Expected Metrics**:
- ~100 documents per run
- ~5-10 chunks per document
- Processing time: 5-10 minutes

## 🐛 Troubleshooting

### Common Issues

**"Model not found" error**
```bash
# Verify Ollama models
curl http://localhost:11434/api/tags

# Expected models:
# - orca-mini (LLM, 2GB)
# - nomic-embed-text (embeddings, 768-dim)
```

**API returns 502 Bad Gateway**
```bash
# Check backend logs
docker logs rag-backend | tail -20

# Restart backend
docker restart rag-backend
```

**Airflow tasks failing**
```bash
# Check task logs
docker exec airflow-scheduler airflow tasks list --dag-id document_rag_ingestion_pipeline

# Check worker logs
docker logs airflow-worker | tail -50
```

**Vector DB dimension mismatch**
```bash
# Clear Chroma collection if dimension changed
docker exec rag-backend rm -rf /opt/airflow/chroma_db

# Restart pipeline
docker restart airflow-scheduler
```

See [docs/operations/TROUBLESHOOTING.md](docs/operations/TROUBLESHOOTING.md) for more solutions.

## 📈 Performance Tuning

| Parameter | Default | Recommendation |
|-----------|---------|-----------------|
| Chunk size | 1000 tokens | Increase to 2000 for longer docs |
| Chunk overlap | 200 tokens | Keep at 20% of chunk size |
| Top K results | 5 | Increase to 10 for better context |
| Embedding dim | 768 | Use 384 for faster search |
| Airflow workers | 1 | Increase for parallel ingestion |

## 🔐 Security Considerations

- **MinIO**: Default credentials (change in production)
- **PostgreSQL**: Default password (change in production)
- **API**: CORS enabled for localhost only
- **LLM**: Local inference (no external API keys)
- **Data**: Stored in Docker volumes (ensure backups)

## 🚀 Deployment

### Development
```bash
make up
```

### Production
```bash
make up-prod
```

See [docs/operations/DEPLOYMENT.md](docs/operations/DEPLOYMENT.md) for Kubernetes and cloud deployment.

## 📖 Learning Resources

- **LLM & Embeddings**: [Ollama docs](https://ollama.ai)
- **Vector Database**: [Chroma docs](https://docs.trychroma.com)
- **Workflow Orchestration**: [Airflow docs](https://airflow.apache.org)
- **REST API**: [FastAPI docs](http://localhost:8000/docs)
- **Frontend**: [Next.js docs](https://nextjs.org)

## 🤝 Contributing

For issues, feature requests, or improvements:
1. Check [docs/operations/TROUBLESHOOTING.md](docs/operations/TROUBLESHOOTING.md)
2. Review existing issues
3. Submit detailed bug reports with logs
4. Create pull requests with tests

## 📄 License

MIT License - See LICENSE file for details

## 🔐 Security and Privacy

- [Security policy](SECURITY.md)
- [Threat model](docs/security/SECURITY_THREAT_MODEL.md)
- [Privacy policy](docs/security/PRIVACY.md)
- [Release and signing process](docs/operations/RELEASE.md)

## 📞 Support

- **Documentation**: See `docs/` folder
- **Issues**: Check TROUBLESHOOTING.md
- **Architecture**: See SYSTEM_DESIGN_INTERVIEW.md
- **API**: Visit http://localhost:8000/docs when running
| Ollama | ✅ Ready | Local LLM inference |
| MinIO | ✅ Ready | Object storage |
| PostgreSQL | ✅ Ready | Metadata store |

## 🔍 Common Commands

```bash
# View logs
make logs

# Stop services
./ops/scripts/stop.sh

# Clean everything
make down

# Rebuild images
docker compose -f compose/compose.yml build --no-cache

# Access Airflow
open http://localhost:9093

# Access API docs
open http://localhost:8000/docs

# Test search endpoint
curl -X POST http://localhost:8000/documents/search \
  -H "Content-Type: application/json" \
  -d '{"query":"example search"}'
```

## 📞 Support & Documentation

- **Architecture**: See [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) for system design
- **Deployment**: See [docs/operations/DEPLOYMENT.md](docs/operations/DEPLOYMENT.md) for setup help
- **API Usage**: See [docs/reference/API_REFERENCE.md](docs/reference/API_REFERENCE.md) for endpoints
- **Issues**: See [docs/operations/TROUBLESHOOTING.md](docs/operations/TROUBLESHOOTING.md) for solutions

## 🎓 Learning Resources

- [Apache Airflow Documentation](https://airflow.apache.org/)
- [FastAPI Guide](https://fastapi.tiangolo.com/)
- [Next.js Handbook](https://nextjs.org/learn)
- [Chroma Documentation](https://docs.trychroma.com/)
- [Ollama Models](https://ollama.ai/library)

## 📝 License

This project is private and proprietary.

---

**Last Updated**: December 21, 2025  
**Status**: ✅ Production-Ready  
**Version**: 1.0.0

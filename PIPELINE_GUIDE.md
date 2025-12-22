# 🚀 RAG Pipeline - Complete Setup & Execution Guide

## ✅ Status: FULLY OPERATIONAL

All services are running and the document ingestion pipeline is active!

---

## 📊 System Overview

### Running Services
- **Airflow 2.9.0**: Workflow orchestration & scheduling
- **MinIO**: S3-compatible document storage  
- **Ollama**: Local LLM for embeddings (orca-mini + nomic-embed-text)
- **Chroma**: Vector database for embeddings storage
- **FastAPI**: RAG search engine backend
- **Next.js**: React frontend for document exploration
- **PostgreSQL**: Airflow metadata database
- **Redis**: Message broker for Celery tasks

### Network Architecture
- `airflow-network`: Airflow services + PostgreSQL + Redis
- `rag-network`: RAG services (backend, frontend, Chroma, MinIO, Ollama)

---

## 🔗 Quick Access Links

### Web Interfaces
| Service | URL | Credentials |
|---------|-----|-----------|
| **Airflow Web UI** | http://localhost:9093 | airflow / airflow |
| **MinIO Console** | http://localhost:9001 | minioadmin / minioadmin |
| **FastAPI Documentation** | http://localhost:8000/docs | None required |
| **Frontend Application** | http://localhost:3000 | None required |

### APIs
| Service | Endpoint | Purpose |
|---------|----------|---------|
| **Chroma Vector DB** | http://localhost:8001/api/v2 | Query embeddings |
| **Ollama LLM** | http://localhost:11434 | Generate embeddings |
| **FastAPI RAG** | http://localhost:8000 | Search documents |

---

## 📋 Pipeline Workflow

### Document Processing Pipeline
```
User Uploads Document
         ↓
      MinIO (S3 Storage)
         ↓
  Airflow DAG: document_rag_ingestion_pipeline
         ↓
  ┌─────────────────────────────────────────┐
  │ Task 1: Fetch Documents from MinIO      │
  │ Task 2: Process & Chunk Documents       │
  │ Task 3: Generate Embeddings (Ollama)    │
  │ Task 4: Upsert to Chroma Vector DB      │
  │ Task 5: Validate Data Integrity         │
  │ Task 6: Notify Completion               │
  └─────────────────────────────────────────┘
         ↓
  Chroma (Vector Database)
         ↓
  FastAPI RAG Engine
         ↓
  Frontend Search Results
```

---

## 🚀 Getting Started

### 1. Access Airflow Dashboard
```bash
# Open in browser:
http://localhost:9093

# Login with:
Username: airflow
Password: airflow
```

### 2. Upload Documents to MinIO
```bash
# Option A: Using MinIO Console
# 1. Go to: http://localhost:9001
# 2. Login: minioadmin / minioadmin
# 3. Navigate to "documents" bucket
# 4. Upload PDF, TXT, or other documents

# Option B: Using MinIO CLI
mc cp /path/to/document.pdf minio/documents/
```

### 3. Trigger Pipeline Execution
```bash
# The pipeline can be triggered via:

# A. Airflow Web UI:
# 1. Navigate to DAGs view
# 2. Find: document_rag_ingestion_pipeline
# 3. Click "Trigger DAG" button

# B. Using curl:
curl -X POST -u "airflow:airflow" \
  "http://localhost:9093/api/v1/dags/document_rag_ingestion_pipeline/dagRuns" \
  -H "Content-Type: application/json" \
  -d '{}'

# C. Using the upload script:
./scripts/upload-and-trigger.sh
```

### 4. Monitor Execution
```bash
# Real-time monitoring dashboard:
./scripts/monitor-pipeline.sh

# Or watch live status:
./scripts/live-status.sh

# Or view Airflow scheduler logs:
docker logs airflow-scheduler -f
```

### 5. Search Documents
```bash
# Once ingested, search via:

# A. Frontend UI:
http://localhost:3000

# B. FastAPI Direct:
curl -X POST "http://localhost:8000/documents/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "your search query", "top_k": 5}'

# C. Swagger UI:
http://localhost:8000/docs
```

---

## 📊 Monitoring & Debugging

### Check Service Health
```bash
# Test all services:
./scripts/test-pipeline.sh

# Docker status:
docker-compose ps

# Specific service logs:
docker logs airflow-webserver
docker logs rag-backend  
docker logs ollama
docker logs chroma
```

### View Documents in MinIO
```bash
# List uploaded documents:
mc ls minio/documents

# Delete a document:
mc rm minio/documents/filename.pdf
```

### Check Vector DB
```bash
# List Chroma collections:
curl http://localhost:8001/api/v2/collections

# Get collection stats:
curl http://localhost:8001/api/v2/collections/{collection_name}
```

### Monitor Task Execution
```bash
# Airflow scheduler logs:
docker logs airflow-scheduler -f

# Airflow worker logs:
docker logs airflow-worker -f

# Airflow webserver logs:
docker logs airflow-webserver -f
```

---

## 🛠️ Common Tasks

### Restart Services
```bash
# Restart all:
docker-compose restart

# Restart specific service:
docker-compose restart rag-backend
docker-compose restart airflow-scheduler
```

### Clear Data
```bash
# Clear MinIO bucket:
mc rm --recursive minio/documents/*

# Clear Chroma database:
docker volume rm datalake-project_chroma_data

# Clear Airflow logs:
docker exec airflow-webserver rm -rf /opt/airflow/logs/*
```

### View Detailed Logs
```bash
# Fetch task logs from Airflow:
# UI Path: DAG → Task Instance → Logs

# Or via CLI:
docker exec airflow-webserver airflow tasks logs \
  document_rag_ingestion_pipeline fetch_documents_from_minio \
  manual__2025-12-22T01:35:53.927492+00:00
```

---

## 🔧 Configuration Files

### Key Locations
```
Project Root
├── docker-compose.yml          # All service definitions
├── airflow-db/dags/
│   └── rag_vector_db_ingestion_dag.py  # Main DAG
├── src/services/rag-engine/
│   ├── main.py                 # FastAPI entry point
│   ├── rag_engine.py           # RAG logic
│   └── requirements.txt        # Dependencies
└── src/services/frontend/      # Next.js frontend
```

### Environment Variables
```bash
# MinIO
MINIO_HOST: localhost:9000
MINIO_ROOT_USER: minioadmin
MINIO_ROOT_PASSWORD: minioadmin

# Ollama
OLLAMA_URL: http://localhost:11434
EMBEDDING_MODEL: nomic-embed-text
LLM_MODEL: orca-mini

# Chroma
CHROMA_HOST: localhost
CHROMA_PORT: 8001

# Airflow
AIRFLOW__CORE__DAGS_FOLDER: /opt/airflow/dags
AIRFLOW__CORE__EXECUTOR: CeleryExecutor
```

---

## 📈 Performance Tips

1. **For Large Documents**: Enable text chunking in DAG
2. **For Multiple Searches**: Cache embeddings in Redis
3. **For Production**: Use managed Chroma Cloud instead of local
4. **For Scaling**: Deploy Airflow in HA mode with multiple workers

---

## 🆘 Troubleshooting

### Pipeline Tasks Stuck
```bash
# Clear failed tasks:
docker exec airflow-webserver airflow tasks clear -f \
  document_rag_ingestion_pipeline -d 2025-01-01

# Trigger new run:
curl -X POST -u "airflow:airflow" \
  "http://localhost:9093/api/v1/dags/document_rag_ingestion_pipeline/dagRuns" \
  -H "Content-Type: application/json" -d '{}'
```

### MinIO Connection Issues
```bash
# Test MinIO connectivity:
curl http://localhost:9000/minio/health/live

# Check MinIO logs:
docker logs minio
```

### Ollama Not Generating Embeddings
```bash
# Check Ollama health:
curl http://localhost:11434/api/tags

# Restart Ollama:
docker-compose restart ollama
```

### Chroma Vector DB Issues
```bash
# Check Chroma health:
curl http://localhost:8001/api/v2

# View Chroma logs:
docker logs chroma
```

---

## 📚 Documentation

- [Airflow Documentation](https://airflow.apache.org/)
- [MinIO Documentation](https://docs.min.io/)
- [Chroma Documentation](https://docs.trychroma.com/)
- [Ollama Documentation](https://github.com/ollama/ollama)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

---

## ✅ Verification Checklist

- [x] All Docker services running and healthy
- [x] MinIO bucket created and documents uploaded
- [x] Airflow DAG unpaused and executable
- [x] Ollama models available (orca-mini, nomic-embed-text)
- [x] Chroma vector database initialized
- [x] FastAPI backend responding
- [x] Frontend application accessible
- [x] PostgreSQL database connected
- [x] Redis message broker operational

---

## 🎉 You're All Set!

Your RAG pipeline is fully operational and ready to ingest documents, generate embeddings, and provide semantic search capabilities!

**Next Steps:**
1. Upload documents via MinIO console
2. Monitor pipeline in Airflow UI
3. Search through indexed documents in frontend
4. Use FastAPI for programmatic access

For any issues, check the logs using the commands above or visit the troubleshooting section.

Happy documenting! 📚✨

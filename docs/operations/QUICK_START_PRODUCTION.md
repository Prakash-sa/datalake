# 🚀 Production Quick Start Guide

## 5-Minute Setup for Enterprise Document RAG Platform

### Step 1: Check Prerequisites (1 min)

```bash
# Verify Docker is installed
docker --version
# Expected: Docker version 24.0+

# Check available disk space (need 50GB minimum)
df -h

# Verify ports are available
netstat -tuln | grep -E "3000|8000|9093|11434"
# Should show no output (ports free)
```

### Step 2: Clone and Setup (2 min)

```bash
# Clone repository
git clone <your-repo>
cd datalake-project

# Copy environment file
cp .env.example .env

# Verify environment
cat .env
```

### Step 3: Start Services (1 min)

```bash
# Start all services in background
docker-compose up -d

# Wait for services to be healthy (2-3 minutes)
sleep 30

# Check status
docker ps --format "table {{.Names}}\t{{.Status}}"
```

### Step 4: Verify Installation (1 min)

```bash
# Check backend health
curl http://localhost:8000/health
# Expected: {"status":"healthy","timestamp":"..."}

# Check Ollama models
curl http://localhost:11434/api/tags | python3 -m json.tool
# Expected: orca-mini, nomic-embed-text present

# Open UI in browser
open http://localhost:3000
```

---

## Common Tasks

### Upload Documents

```bash
# 1. Access MinIO Console
open http://localhost:9001  # minioadmin / minioadmin

# 2. Create bucket "documents" (if not exists)

# 3. Upload .txt files or documents

# Expected: Files visible in bucket
```

### Trigger Document Ingestion

```bash
# Option A: Via Airflow Web UI
open http://localhost:9093
# Find: document_rag_ingestion_pipeline
# Click: Trigger DAG
# Monitor: 6 tasks should complete

# Option B: Via CLI
docker exec airflow-scheduler \
  airflow dags trigger document_rag_ingestion_pipeline

# Option C: Check logs
docker logs airflow-scheduler | tail -50
```

### Search Documents

```bash
# Via API
curl -X POST http://localhost:8000/documents/search \
  -H "Content-Type: application/json" \
  -d '{"query":"kubernetes"}'

# Via Web UI
open http://localhost:3000
# Type your search query
```

### Ask AI Question

```bash
# Via API
curl -X POST http://localhost:8000/documents/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Explain deployment strategies"}'

# Via Web UI
open http://localhost:3000
# Click "Ask AI" after searching
```

---

## Monitoring

### Real-time Logs

```bash
# Backend API logs
docker logs -f rag-backend

# Airflow scheduler logs
docker logs -f airflow-scheduler

# Ollama logs
docker logs -f ollama
```

### Service Health

```bash
# All services status
docker ps -a

# Specific service health
docker inspect rag-backend | grep -A 5 "Health"

# Network connectivity
docker exec rag-backend curl -s http://ollama:11434/api/tags
```

### Performance Metrics

```bash
# API response time
time curl http://localhost:8000/health

# Chroma vector DB size
docker exec rag-backend python3 -c \
  "import chromadb; c = chromadb.PersistentClient('/opt/airflow/chroma_db'); \
   col = c.get_collection('documents'); \
   print(f'Total embeddings: {col.count()}')"

# Document count in MinIO
docker exec minio minio-client ls minio/documents
```

---

## Troubleshooting Quick Fixes

### "Connection refused" to API

```bash
# Check if backend is running
docker ps | grep rag-backend

# Restart if needed
docker restart rag-backend

# Wait 5 seconds and retry
sleep 5
curl http://localhost:8000/health
```

### Ollama "model not found"

```bash
# Verify models exist
curl http://localhost:11434/api/tags

# If empty, pull models
docker exec ollama ollama pull orca-mini
docker exec ollama ollama pull nomic-embed-text

# Verify again
curl http://localhost:11434/api/tags
```

### Airflow DAG not running

```bash
# Check if scheduler is running
docker ps | grep airflow-scheduler

# Restart scheduler
docker restart airflow-scheduler

# Check DAG is loaded
docker exec airflow-scheduler airflow dags list

# Manually trigger
docker exec airflow-scheduler \
  airflow dags trigger document_rag_ingestion_pipeline
```

### Frontend blank or not loading

```bash
# Check if frontend is running
docker ps | grep rag-frontend

# Restart frontend
docker restart rag-frontend

# Check logs
docker logs rag-frontend | tail -20

# Verify API connection
curl http://localhost:8000/health
```

---

## Environment Variables

Edit `.env` to configure:

```bash
# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
ENV=development  # or production

# Frontend Configuration
NEXT_PUBLIC_API_URL=http://localhost:8000

# Vector Database
CHROMA_PATH=/opt/airflow/chroma_db

# Ollama
OLLAMA_BASE_URL=http://ollama:11434
EMBEDDING_MODEL=nomic-embed-text
LLM_MODEL=orca-mini

# MinIO
MINIO_ENDPOINT=minio:9000
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin

# Database
DB_HOST=postgres
DB_PORT=5432
DB_USER=airflow
DB_PASSWORD=airflow

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
```

---

## Scaling Checklist

### For 100+ Documents/Day

```bash
☐ Increase Airflow workers: 1 → 4
☐ Enable document batching (chunks of 50)
☐ Add Redis caching layer
☐ Monitor disk usage (need ~100MB per 1000 docs)
☐ Set up PostgreSQL backups
```

### For 1,000+ Documents/Day

```bash
☐ Add GPU support to Ollama
☐ Implement distributed embedding generation
☐ Use Kafka for streaming ingestion
☐ Add read replicas for database
☐ Scale API servers: 1 → 5
```

### For Production Deployment

```bash
☐ Deploy on Kubernetes (vs Docker Compose)
☐ Use managed PostgreSQL (RDS/Azure Database)
☐ Move MinIO to S3/Azure Blob
☐ Add monitoring (Prometheus/Grafana)
☐ Set up automated backups
☐ Configure SSL/TLS
☐ Enable authentication (OAuth2)
☐ Add rate limiting & API keys
☐ Implement RBAC for documents
```

---

## Port Reference

| Service | Port | URL |
|---------|------|-----|
| **Frontend** | 3000 | http://localhost:3000 |
| **API** | 8000 | http://localhost:8000 |
| **Airflow** | 9093 | http://localhost:9093 |
| **MinIO Console** | 9001 | http://localhost:9001 |
| **MinIO API** | 9000 | http://localhost:9000 |
| **Ollama** | 11434 | http://localhost:11434 |
| **PostgreSQL** | 5432 | localhost:5432 |
| **Redis** | 6379 | localhost:6379 |
| **Chroma** | 8000 | http://localhost:8000 |

---

## Useful Commands

### Stop All Services

```bash
docker-compose down
```

### Stop Without Losing Data

```bash
docker-compose stop
```

### View Logs

```bash
docker-compose logs -f [service-name]
# Examples:
# docker-compose logs -f rag-backend
# docker-compose logs -f airflow-scheduler
```

### Execute Commands in Containers

```bash
docker exec [container-name] [command]
# Examples:
docker exec rag-backend curl http://localhost:8000/health
docker exec airflow-scheduler airflow dags list
```

### Reset Everything (Delete All Data)

```bash
docker-compose down -v
docker system prune -a
# Warning: This deletes all volumes and data!
```

---

## Next Steps

1. **Read Full Documentation**
   - [docs/architecture/ARCHITECTURE.md](../architecture/ARCHITECTURE.md) - Detailed system design
   - [docs/architecture/SYSTEM_DESIGN_INTERVIEW.md](../architecture/SYSTEM_DESIGN_INTERVIEW.md) - Interview Q&A
   - [docs/operations/DEPLOYMENT.md](DEPLOYMENT.md) - Production setup

2. **Try API Endpoints**
   - Visit http://localhost:8000/docs for interactive API docs
   - Test search, ask, and health endpoints

3. **Upload Sample Data**
   - Add documents to MinIO bucket
   - Trigger Airflow DAG to index them
   - Search for documents via API/UI

4. **Monitor & Scale**
   - Watch Airflow UI for pipeline execution
   - Check API logs for errors
   - Monitor resource usage with `docker stats`

---

## Support

- **API Documentation**: http://localhost:8000/docs
- **Airflow Web UI**: http://localhost:9093
- **MinIO Console**: http://localhost:9001
- **Troubleshooting**: See [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- **Interview Questions**: See [SYSTEM_DESIGN_INTERVIEW.md](../architecture/SYSTEM_DESIGN_INTERVIEW.md)

**Estimated setup time**: 5-10 minutes (including service startup)

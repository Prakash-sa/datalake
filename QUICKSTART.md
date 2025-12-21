# Quick Start Guide

Get the Document RAG Engine running in 5 minutes.

## Prerequisites

- **Docker & Docker Compose** (Recommended)
- **Python 3.11+** (For local development)
- **2GB RAM minimum** (1GB for development)
- **Ollama** (LLM inference engine)

## Option 1: Docker Compose (Fastest)

### 1. Start Services

```bash
cd backend

# Start all services
docker-compose up -d

# Wait 30 seconds for services to be ready
sleep 30

# Check status
docker-compose ps
```

**Expected Output**:
```
NAME            STATUS
ollama          Up (healthy)
minio           Up (healthy)
rag-backend     Up (healthy)
```

### 2. Test the API

```bash
# Health check
curl http://localhost:8000/health

# Index sample documents
curl -X POST http://localhost:8000/documents/index \
  -H "Content-Type: application/json" \
  -d '{
    "documents": [
      {
        "id": "doc1",
        "content": "Python is a powerful programming language for data science and AI",
        "metadata": {"source": "tutorial.md"}
      },
      {
        "id": "doc2",
        "content": "Machine learning models can predict patterns in data",
        "metadata": {"source": "ml_guide.md"}
      }
    ]
  }'

# Search documents
curl -X POST http://localhost:8000/documents/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Python data science",
    "k": 5
  }'

# Query with LLM analysis
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is Python used for?",
    "k": 5
  }'
```

### 3. Access Dashboards

- **API Docs**: http://localhost:8000/docs
- **API Health**: http://localhost:8000/health
- **Stats**: http://localhost:8000/stats
- **MinIO Console**: http://localhost:9001 (admin/minioadmin)

### 4. Stop Services

```bash
docker-compose down

# Remove data volumes
docker-compose down -v
```

---

## Option 2: Local Development

### 1. Setup Python Environment

```bash
# Navigate to backend
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # macOS/Linux
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Start Ollama (Required)

```bash
# Option A: Install Ollama locally
# Visit: https://ollama.ai/download

# Option B: Run Ollama in Docker
docker run -d -p 11434:11434 --name ollama ollama/ollama:latest

# Pull a model (first run)
docker exec ollama ollama pull all-minilm
docker exec ollama ollama pull mistral

# Or locally (after installing Ollama)
ollama pull all-minilm
ollama pull mistral
```

### 3. Configure Environment

```bash
# Create .env file
cp .env.example .env

# Edit .env (all defaults work for development)
nano .env

# Example development settings:
# ENV=development
# LOG_LEVEL=DEBUG
# OLLAMA_URL=http://localhost:11434
# ALLOWED_ORIGINS=*
```

### 4. Start Development Server

```bash
# From backend directory
python -m uvicorn main:app --reload

# Or use the configured settings
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Expected Output**:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

### 5. Test the API

```bash
# In another terminal
curl http://localhost:8000/health
curl http://localhost:8000/docs  # Open in browser
```

---

## Option 3: Production Deployment

### 1. Configure Production Environment

```bash
cd backend

# Copy production config
cp .env.production .env

# Edit for your environment
nano .env

# Required settings:
# ENV=production
# ALLOWED_ORIGINS=https://yourdomain.com
# WORKERS=4
# LLM_TEMPERATURE=0.3
```

### 2. Build Production Image

```bash
# Build
docker build -f Dockerfile.prod -t rag-engine:prod .

# Tag for registry
docker tag rag-engine:prod myregistry/rag-engine:prod
```

### 3. Deploy Production Stack

```bash
# Start production services
docker-compose -f docker-compose.prod.yml up -d

# Wait for health checks
sleep 40

# Verify all services healthy
docker-compose -f docker-compose.prod.yml ps
```

### 4. Verify Production Deployment

```bash
# Health check
curl https://yourdomain.com/health

# View logs
docker-compose -f docker-compose.prod.yml logs -f rag-backend

# Check metrics
curl http://localhost:9090/metrics
```

### 5. Setup Monitoring (Optional)

```bash
# Start with metrics stack
docker-compose -f docker-compose.prod.yml --profile metrics up -d

# Access Grafana
# http://localhost:3001
# Login: admin / admin
```

---

## Common Tasks

### Restart Services

```bash
# Docker Compose
docker-compose restart rag-backend

# Production
docker-compose -f docker-compose.prod.yml restart rag-backend
```

### View Logs

```bash
# Last 50 lines
docker-compose logs --tail=50 rag-backend

# Follow logs
docker-compose logs -f rag-backend

# Specific service
docker-compose logs ollama
```

### Check Service Health

```bash
# All services
docker-compose ps

# Specific endpoint
curl http://localhost:8000/health
curl http://localhost:11434/api/tags  # Ollama
curl http://localhost:9000/minio/health/live  # MinIO
```

### Scale Workers

```bash
# Update .env
WORKERS=8

# Rebuild and restart
docker-compose -f docker-compose.prod.yml up -d --build
```

### Backup Data

```bash
# Backup MinIO documents
docker exec minio mc mirror minio/documents /backup/documents

# Backup Ollama models
docker exec ollama tar -czf /backup/ollama.tar.gz /root/.ollama
```

---

## Troubleshooting

### Port Already in Use

```bash
# Find and kill process
lsof -i :8000
kill -9 <PID>

# Or use different port
docker-compose run rag-backend -p 8001:8000
```

### Ollama Connection Error

```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Restart Ollama
docker restart ollama

# Check logs
docker logs ollama
```

### Out of Memory

```bash
# Reduce workers
WORKERS=2

# Reduce cache
EMBEDDING_CACHE_SIZE=64

# Restart
docker-compose restart rag-backend
```

### No Documents Indexed

```bash
# Verify MinIO is running
curl http://localhost:9000/minio/health/live

# Check backend logs
docker-compose logs rag-backend

# Try indexing again with simpler request
curl -X POST http://localhost:8000/documents/index \
  -H "Content-Type: application/json" \
  -d '{"documents": [{"id": "test", "content": "test", "metadata": {}}]}'
```

---

## API Quick Reference

### Index Documents
```bash
POST /documents/index
Body: {
  "documents": [
    {"id": "...", "content": "...", "metadata": {...}}
  ]
}
```

### Search Documents
```bash
POST /documents/search
Body: {
  "query": "search term",
  "k": 5,
  "min_score": 0.3
}
```

### Query with LLM
```bash
POST /query
Body: {
  "query": "question",
  "k": 5,
  "min_score": 0.3
}
```

### Health Check
```bash
GET /health
```

### Engine Stats
```bash
GET /stats
```

### API Documentation
```bash
GET /docs  # Swagger UI
GET /redoc  # ReDoc
```

---

## Environment Variables Cheat Sheet

```bash
# Server
ENV=development              # or production, testing
LOG_LEVEL=DEBUG             # or INFO, WARNING, ERROR
HOST=0.0.0.0
PORT=8000
WORKERS=1

# LLM
OLLAMA_URL=http://localhost:11434
EMBEDDING_MODEL=all-minilm
LLM_MODEL=mistral
LLM_TEMPERATURE=0.5

# Limits
MAX_DOCUMENTS=10000
MAX_QUERY_LENGTH=1000
QUERY_TIMEOUT=30

# CORS
ALLOWED_ORIGINS=*           # dev: * or specific domains
```

---

## Next Steps

1. **Read API Documentation**: http://localhost:8000/docs
2. **Review [README.md](README.md)** for detailed configuration
3. **Check [TESTING.md](TESTING.md)** for running tests
4. **See [PRODUCTION_DEPLOYMENT.md](../PRODUCTION_DEPLOYMENT.md)** for production setup
5. **Monitor with Prometheus** for metrics

---

**Total Setup Time**: 5-10 minutes  
**Minimum Requirements**: Docker + 2GB RAM  
**Status**: ✅ Ready to Use

Questions? Check logs:
```bash
docker-compose logs -f
```

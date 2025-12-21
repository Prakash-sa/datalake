# Quick Start Guide - Document RAG Query Engine

## Current Status: ✅ RUNNING

All services are up and ready to use.

## Access Points

| Service | URL | Purpose |
|---------|-----|---------|
| **Frontend UI** | http://localhost:3000 | Document RAG interface |
| **API Documentation** | http://localhost:8000/docs | Interactive API explorer |
| **MinIO Console** | http://localhost:9001 | Document storage (minioadmin/minioadmin) |
| **API Base URL** | http://localhost:8000 | REST API endpoints |

## Quick API Tests

### 1. Health Check
```bash
curl http://localhost:8000/health
```
Expected: `{"status":"healthy","timestamp":"..."}`

### 2. Index Documents
```bash
curl -X POST http://localhost:8000/documents/index \
  -H "Content-Type: application/json" \
  -d '{
    "documents": [
      {
        "id": "doc1",
        "content": "Python is a programming language.",
        "metadata": {"source": "example"}
      }
    ]
  }'
```

### 3. Search Documents
```bash
curl -X POST http://localhost:8000/documents/search \
  -H "Content-Type: application/json" \
  -d '{"query": "What is Python?", "k": 5}'
```

### 4. Query with RAG
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is Python used for?", "k": 3}'
```

### 5. Get Statistics
```bash
curl http://localhost:8000/stats
```

## Command Reference

### Start Services
```bash
cd rag-query-engine
docker-compose up -d
```

### Stop Services
```bash
docker-compose down
```

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f rag-backend
docker-compose logs -f rag-frontend
docker-compose logs -f ollama
docker-compose logs -f minio
```

### Restart a Service
```bash
docker-compose restart rag-backend
```

### Full Rebuild
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (Next.js) - Port 3000                            │
│  - Document upload interface                               │
│  - Search results display                                  │
│  - RAG query interface                                     │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP/REST
┌────────────────────▼────────────────────────────────────────┐
│  Backend (FastAPI) - Port 8000                             │
│  - Document indexing API                                   │
│  - Semantic search endpoint                                │
│  - RAG query pipeline                                      │
│  - Statistics & monitoring                                 │
└────────────┬─────────────────────────────┬─────────────────┘
             │                             │
      ┌──────▼──────┐               ┌──────▼──────┐
      │ Ollama LLM   │               │ MinIO       │
      │ Port 11434   │               │ Port 9000   │
      │              │               │             │
      │ Models:      │               │ Document    │
      │ - mistral    │               │ storage     │
      │ - nomic-*    │               │             │
      └──────────────┘               └─────────────┘
```

## Configuration

Environment variables are set in `docker-compose.yml`:

```yaml
LLM_MODEL: mistral                    # LLM for responses
EMBEDDING_MODEL: nomic-embed-text    # Embedding generator
OLLAMA_URL: http://ollama:11434      # LLM service
MINIO_HOST: minio:9000               # Storage service
```

To modify, edit `docker-compose.yml` and rebuild:
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## Troubleshooting

### Backend not responding
```bash
# Check logs
docker-compose logs rag-backend

# Restart
docker-compose restart rag-backend
```

### LLM not responding
```bash
# Check Ollama
curl http://localhost:11434/api/tags

# Restart Ollama
docker-compose restart ollama
```

### Frontend not loading
```bash
# Check frontend logs
docker-compose logs rag-frontend

# Rebuild frontend
docker-compose down
docker-compose build --no-cache rag-frontend
docker-compose up -d
```

### Out of memory errors
- Increase Docker memory allocation
- Use smaller LLM model
- Check `docker stats` for resource usage

## Key Features

✅ **Semantic Search** - Find documents by meaning, not keywords  
✅ **RAG Pipeline** - Generate responses from document context  
✅ **Error Handling** - Graceful degradation with informative messages  
✅ **Performance** - Sub-second search and retrieval  
✅ **Monitoring** - Track indexing, queries, and errors  
✅ **API-First** - RESTful API with OpenAPI documentation  

## Testing

All functionality has been tested end-to-end:
- ✅ Health checks
- ✅ Document indexing
- ✅ Semantic search
- ✅ RAG query generation
- ✅ Statistics
- ✅ Frontend connectivity
- ✅ CORS configuration

See `E2E_TEST_RESULTS.md` for detailed test report.

## Documentation

- `PROJECT_COMPLETION_SUMMARY.md` - Full project overview
- `E2E_TEST_RESULTS.md` - Comprehensive test results
- `README.md` - Project description
- `ARCHITECTURE.md` - System design details
- `backend/README.md` - Backend-specific documentation

## Support

For issues or questions:
1. Check logs: `docker-compose logs`
2. Review documentation files
3. Test API endpoints individually
4. Verify all services are running: `docker-compose ps`

---

**Status**: ✅ Production Ready  
**Last Updated**: December 21, 2025  
**All Services**: Running and Healthy


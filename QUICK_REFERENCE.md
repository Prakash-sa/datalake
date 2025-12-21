# Production RAG Engine - Quick Reference Card

## 🚀 Get Started in 2 Minutes

### Option 1: Docker Compose
```bash
docker-compose up -d && sleep 30
curl http://localhost:8000/health
```

### Option 2: Local Development
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt && cp .env.example .env
uvicorn main:app --reload
```

### Option 3: Production
```bash
docker-compose -f docker-compose.prod.yml up -d && sleep 40
curl https://your-domain.com/health
```

---

## 📚 API Endpoints Cheat Sheet

### Health & Monitoring
```bash
GET /health                          # Health check
GET /stats                           # Engine statistics
GET /                                # API info & docs
```

### Document Operations
```bash
POST /documents/index                # Index documents
POST /documents/search               # Semantic search
```

### RAG Query
```bash
POST /query                          # Full RAG (search + LLM)
```

---

## 🔧 API Examples

### Index Documents
```bash
curl -X POST http://localhost:8000/documents/index \
  -H "Content-Type: application/json" \
  -d '{
    "documents": [
      {
        "id": "doc1",
        "content": "Document text here...",
        "metadata": {"source": "file.pdf"}
      }
    ]
  }'
```

### Search
```bash
curl -X POST http://localhost:8000/documents/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "search term",
    "k": 5,
    "min_score": 0.3
  }'
```

### Full RAG Query
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the meaning of life?",
    "k": 5,
    "min_score": 0.3
  }'
```

---

## 🎯 Key Configuration Variables

| Variable | Dev Value | Prod Value | Purpose |
|----------|-----------|-----------|---------|
| ENV | development | production | Environment mode |
| LOG_LEVEL | DEBUG | INFO | Logging verbosity |
| WORKERS | 1 | 4 | Parallel request handlers |
| ALLOWED_ORIGINS | * | domain.com | CORS policy |
| MAX_DOCUMENTS | 10000 | 10000 | Max docs to index |
| MAX_QUERY_LENGTH | 1000 | 1000 | Max query chars |
| QUERY_TIMEOUT | 30 | 30 | Query timeout (sec) |
| LLM_TEMPERATURE | 0.5 | 0.3 | LLM creativity |

---

## 📊 Monitoring Commands

```bash
# Check service status
docker-compose ps

# View logs
docker-compose logs -f rag-backend

# Health check
curl http://localhost:8000/health

# Stats
curl http://localhost:8000/stats

# Metrics
curl http://localhost:9090/metrics

# Prometheus UI
http://localhost:9090

# Grafana UI
http://localhost:3001  # admin/admin

# MinIO Console
http://localhost:9001  # minioadmin/minioadmin

# API Docs
http://localhost:8000/docs
```

---

## 🔍 Common Tasks

### Restart Service
```bash
docker-compose restart rag-backend
```

### View Recent Logs
```bash
docker-compose logs --tail=50 rag-backend
```

### Scale Workers
```bash
# Edit .env: WORKERS=8
docker-compose up -d --build
```

### Backup Data
```bash
docker exec minio mc mirror minio/documents /backup/documents
```

### Test Connection
```bash
docker exec rag-backend curl http://ollama:11434/api/tags
```

### Check Memory Usage
```bash
docker stats rag-backend
```

---

## ⚠️ Troubleshooting Quick Fixes

### Port 8000 Already in Use
```bash
lsof -i :8000 && kill -9 <PID>
# Or use: docker-compose run rag-backend -p 8001:8000
```

### Ollama Not Responding
```bash
docker logs ollama
curl http://localhost:11434/api/tags
docker restart ollama
```

### Out of Memory
```bash
# In .env: WORKERS=2, EMBEDDING_CACHE_SIZE=64
docker-compose up -d
```

### MinIO Connection Error
```bash
curl http://localhost:9000/minio/health/live
docker logs minio
docker restart minio
```

---

## 📋 Environment Template

```bash
# Development (.env)
ENV=development
LOG_LEVEL=DEBUG
WORKERS=1
ALLOWED_ORIGINS=*
OLLAMA_URL=http://localhost:11434

# Production (.env.production)
ENV=production
LOG_LEVEL=INFO
WORKERS=4
ALLOWED_ORIGINS=https://yourdomain.com
OLLAMA_URL=http://ollama:11434
```

---

## 📚 Documentation Reference

| Document | Purpose | Read Time |
|----------|---------|-----------|
| [QUICKSTART.md](QUICKSTART.md) | 5-min setup guide | 5 min |
| [backend/README.md](backend/README.md) | API reference | 15 min |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design | 20 min |
| [PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md) | Ops guide | 20 min |
| [backend/TESTING.md](backend/TESTING.md) | Testing guide | 15 min |

---

## 🚨 Important Limits

- **Max Query Length**: 1,000 characters
- **Max Results (k)**: 100 documents
- **Query Timeout**: 30 seconds
- **Max Documents**: 10,000
- **Container Memory**: 4GB (configurable)
- **Cache Size**: 128 embeddings (LRU)

---

## ✅ Health Check Status Codes

- **200**: Healthy - all systems operational
- **400**: Bad Request - invalid input parameters
- **500**: Server Error - internal issue, check logs
- **503**: Service Unavailable - dependencies offline

---

## 🔐 Security Checklist

- [ ] CORS set to specific domain (not "*")
- [ ] Non-root user in container ✅
- [ ] Secrets in .env (not in code) ✅
- [ ] Input validation enabled ✅
- [ ] Error handling comprehensive ✅
- [ ] Health checks configured ✅
- [ ] Resource limits set ✅
- [ ] Logging configured ✅

---

## 📈 Performance Tips

### Faster Searches
- Increase `k` to reduce LLM overhead
- Use `/documents/search` instead of `/query`
- Check relevance scores for quality

### Handle More Requests
- Increase `WORKERS` (formula: 2×CPU + 1)
- Enable Prometheus metrics for monitoring
- Use caching for repeated queries

### Reduce Memory Usage
- Lower `EMBEDDING_CACHE_SIZE`
- Reduce `MAX_DOCUMENTS`
- Use smaller LLM model

---

## 🎯 Status

**Version**: 2.0.0  
**Status**: ✅ Production Ready  
**Last Updated**: 2024-01-15

---

**Need Help?** Check the relevant guide above or review full documentation.

Print this page for quick reference during deployment! 📌

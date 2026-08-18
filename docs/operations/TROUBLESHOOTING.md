# Troubleshooting Guide

## Quick Diagnostics

```bash
# Run complete health check
./ops/scripts/health-check.sh

# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f [service-name]

# Check resource usage
docker stats
```

## Common Issues & Solutions

### 1. Services Won't Start

**Symptom:** Docker containers fail to start

**Diagnosis:**
```bash
docker-compose logs [service]
# Look for error messages
```

**Solutions:**

A. **Port Already in Use**
```bash
# Check which process uses the port
lsof -i :8000
lsof -i :9093

# Kill the process
kill -9 <PID>

# Or change the port in .env
PORT_BACKEND=8001
PORT_AIRFLOW=9094
```

B. **Insufficient Memory**
```bash
# Check available memory
docker stats

# Reduce resource limits in docker-compose.yml
mem_limit: 1g  # Reduce from 2g

# Or allocate more to Docker
# Docker Desktop → Preferences → Resources → Memory
```

C. **Volume Permission Issues**
```bash
# Fix volume permissions
sudo chmod -R 755 ./volumes/

# Rebuild without cache
docker-compose build --no-cache
```

---

### 2. Documents Not Indexed

**Symptom:** Uploaded documents don't appear in search results

**Diagnosis:**
```bash
# 1. Check if documents exist in MinIO
curl -X GET http://localhost:9000/minio/v2/buckets/documents/objects

# 2. Check Airflow DAG status
# Visit: http://localhost:9093/dags/document_rag_ingestion_pipeline

# 3. Check Chroma collection
curl http://localhost:8001/api/v1/collections

# 4. Check worker logs
docker-compose logs airflow-worker
```

**Solutions:**

A. **MinIO Documents Not Found**
```bash
# Upload test document
curl -X PUT http://localhost:9000/documents/test.txt \
  -d "Test content"

# Verify upload
curl http://localhost:9001  # Access console
```

B. **Airflow DAG Not Triggered**
```bash
# Manual trigger
curl -X POST http://localhost:9093/api/v1/dags/document_rag_ingestion_pipeline/dagRuns \
  -H "Content-Type: application/json" \
  -d '{}'

# Or visit UI and click "Trigger DAG"
```

C. **Embedding Generation Failed**
```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Check logs
docker-compose logs ollama

# Verify model exists
docker exec ollama ollama list
```

D. **Chroma Indexing Failed**
```bash
# Check Chroma is accessible
curl http://localhost:8001/api/v1/heartbeat

# Check collection exists
curl http://localhost:8001/api/v1/collections

# Recreate collection if needed
curl -X POST http://localhost:8001/api/v1/collections \
  -H "Content-Type: application/json" \
  -d '{"name":"documents","metadata":{"hnsw:space":"cosine"}}'
```

---

### 3. Search Returns No Results

**Symptom:** Queries return empty results despite documents being indexed

**Diagnosis:**
```bash
# 1. Test with simple query
curl -X POST http://localhost:8000/documents/search \
  -H "Content-Type: application/json" \
  -d '{"query":"test","limit":10,"threshold":0.0}'

# 2. Check vector database directly
curl http://localhost:8001/api/v1/collections/documents/query

# 3. Check embedding model
curl http://localhost:11434/api/generate \
  -d '{"model":"nomic-embed-text","prompt":"test"}'
```

**Solutions:**

A. **Threshold Too High**
```bash
# Lower similarity threshold
curl -X POST http://localhost:8000/documents/search \
  -H "Content-Type: application/json" \
  -d '{"query":"your query","threshold":0.3}'  # Lower from 0.5
```

B. **Wrong Embedding Model**
```bash
# Verify model matches indexing
# Check code: src/infrastructure/config.py

# Expected model: nomic-embed-text (768 dimensions)

# If changed, re-index all documents
docker-compose exec airflow-worker \
  python -c "from src.tasks import reindex_all; reindex_all()"
```

C. **Collection Empty**
```bash
# Count documents in collection
curl http://localhost:8001/api/v1/collections/documents

# Expected: count > 0

# If empty, re-trigger indexing pipeline
```

D. **Metadata Filter Too Restrictive**
```bash
# Try without filters
curl -X POST http://localhost:8000/documents/search \
  -H "Content-Type: application/json" \
  -d '{"query":"your query"}'  # Remove metadata_filter
```

---

### 4. High Memory Usage

**Symptom:** Docker containers consuming excessive memory

**Diagnosis:**
```bash
# Check memory usage
docker stats

# Identify problematic container
docker top [container-id]

# Check application logs for leaks
docker-compose logs [service] | grep -i memory
```

**Solutions:**

A. **Chroma Index Too Large**
```bash
# Reduce index size
# Option 1: Delete old documents
curl -X DELETE http://localhost:8001/api/v1/collections/documents

# Option 2: Archive old documents
./ops/scripts/archive-documents.sh

# Option 3: Increase memory limit
# docker-compose.yml:
# services:
#   chroma:
#     mem_limit: 4g  # Increase from 2g
```

B. **Airflow Metadata Bloat**
```bash
# Clean old task logs
docker-compose exec postgres \
  psql -U airflow -c "DELETE FROM log WHERE dttm < now() - interval '30 days';"

# Restart Airflow to clear caches
docker-compose restart airflow-webserver airflow-scheduler
```

C. **Python Memory Leak**
```bash
# Check for memory leaks
docker-compose logs [service] | grep -i "memory\|leak"

# Profile application
pip install memory-profiler

# Restart service
docker-compose restart [service]
```

---

### 5. API Timeouts

**Symptom:** Requests to API return 408 timeout errors

**Diagnosis:**
```bash
# Check API logs
docker-compose logs rag-backend

# Monitor query performance
# Check: /stats endpoint for avg query time

# Check system resources
docker stats rag-backend
```

**Solutions:**

A. **Slow Embedding Generation**
```bash
# Increase timeout in code
# config.py:
# EMBEDDING_TIMEOUT = 60  # seconds (increase from 30)

# Or use faster model
# OLLAMA_MODEL = "nomic-embed-text"  # Already fast

# Restart backend
docker-compose restart rag-backend
```

B. **Slow Vector Search**
```bash
# Reduce query limit
curl -X POST http://localhost:8000/documents/search \
  -H "Content-Type: application/json" \
  -d '{"query":"...","limit":3}'  # Reduce from 5

# Or rebuild Chroma index
docker-compose exec chroma \
  /bin/bash -c "chroma-cli rebuild-index"
```

C. **Database Slow Queries**
```bash
# Check slow query log
docker-compose exec postgres \
  psql -U airflow -c "SELECT * FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;"

# Add index if needed
docker-compose exec postgres \
  psql -U airflow -c "CREATE INDEX idx_documents ON documents(source);"
```

---

### 6. Airflow Tasks Failing

**Symptom:** DAG tasks marked as failed or stuck

**Diagnosis:**
```bash
# 1. Visit Airflow UI
# http://localhost:9093/dags/document_rag_ingestion_pipeline

# 2. Click on failed task
# 3. View logs tab for error details

# 4. Check worker logs
docker-compose logs airflow-worker

# 5. Check PostgreSQL connection
docker-compose exec postgres \
  psql -U airflow -c "SELECT 1"
```

**Solutions:**

A. **PostgreSQL Connection Failed**
```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Restart if needed
docker-compose restart postgres

# Check connection string
docker-compose exec airflow-webserver \
  env | grep DATABASE_URL
```

B. **Task Dependencies Not Met**
```bash
# Check task order in DAG
# DAG should be: fetch → process → embed → upsert → validate

# Manually mark previous task as success
# Airflow UI → Task → Mark Success → Trigger downstream

# Or clear all and retry
docker-compose exec airflow-webserver \
  airflow dags clear document_rag_ingestion_pipeline
```

C. **Worker Out of Resources**
```bash
# Check worker logs for memory/CPU issues
docker stats airflow-worker

# Increase worker resources
# docker-compose.yml:
# services:
#   airflow-worker:
#     mem_limit: 2g  # Increase

# Reduce parallelism
docker-compose exec airflow-webserver \
  airflow config set core parallelism 4
```

D. **Timeout During Processing**
```bash
# Increase task timeout
docker-compose exec airflow-webserver \
  airflow config set celery task_time_limit 1800

# Restart worker
docker-compose restart airflow-worker
```

---

### 7. Ollama Model Issues

**Symptom:** Embedding or LLM generation fails

**Diagnosis:**
```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Check available models
docker exec ollama ollama list

# Check logs
docker-compose logs ollama
```

**Solutions:**

A. **Model Not Found**
```bash
# Pull the model
docker exec ollama ollama pull nomic-embed-text

# Verify it's available
docker exec ollama ollama list
```

B. **Ollama Out of Memory**
```bash
# Check Ollama resources
docker stats ollama

# Increase memory limit
# docker-compose.yml:
# services:
#   ollama:
#     mem_limit: 4g  # Increase

# Or reduce context size
docker exec ollama \
  curl -X POST http://localhost:11434/api/generate \
  -d '{"model":"nomic-embed-text","stream":false}'
```

C. **Slow Inference**
```bash
# Check CPU usage
docker stats ollama

# Expected: ~200-500ms per embedding
# If slower, check for contention

# Try CPU pinning (advanced)
docker-compose restart ollama
```

---

### 8. MinIO Connection Issues

**Symptom:** Cannot upload or retrieve documents from MinIO

**Diagnosis:**
```bash
# Check MinIO is running
curl http://localhost:9000/minio/health/live

# Check console is accessible
# http://localhost:9001

# Check credentials
docker-compose logs minio | grep -i "error\|auth"
```

**Solutions:**

A. **Authentication Failed**
```bash
# Check credentials in .env
cat .env | grep MINIO

# Reset if needed
docker-compose down -v
docker-compose up -d minio
# Re-add documents
```

B. **Bucket Not Found**
```bash
# Create bucket via console
# http://localhost:9001
# Or via API:
curl -X PUT http://localhost:9000/documents

# Verify bucket exists
curl http://localhost:9000/minio/v2/buckets
```

C. **Upload Size Limit**
```bash
# Check max upload size in MinIO config
# Increase if needed: minio.cfg
# MINIO_MAX_PART_SIZE = 5GB

# Restart MinIO
docker-compose restart minio
```

---

### 9. Redis Connection Problems

**Symptom:** Celery tasks not queuing or processing

**Diagnosis:**
```bash
# Check Redis is running
docker-compose exec redis redis-cli ping

# Check queue depth
docker-compose exec redis redis-cli LLEN celery

# Check memory usage
docker-compose exec redis redis-cli INFO memory
```

**Solutions:**

A. **Redis Out of Memory**
```bash
# Check current usage
docker-compose exec redis redis-cli INFO memory

# Clear cache
docker-compose exec redis redis-cli FLUSHDB

# Or increase memory limit
# docker-compose.yml:
# services:
#   redis:
#     mem_limit: 1g  # Increase from 512m
```

B. **Connection Timeout**
```bash
# Check Redis logs
docker-compose logs redis

# Restart Redis
docker-compose restart redis

# Verify Airflow can connect
docker-compose exec airflow-webserver \
  airflow config get celery broker_url
```

---

### 10. Frontend Not Loading

**Symptom:** Browser shows blank page or errors

**Diagnosis:**
```bash
# Check frontend is running
curl http://localhost:3000

# Check build logs
docker-compose logs rag-frontend

# Check browser console for errors
# Open DevTools → Console tab

# Check API connection
curl http://localhost:8000/health
```

**Solutions:**

A. **API Unreachable**
```bash
# Check API is running
docker-compose ps rag-backend

# Check CORS is enabled
curl -H "Origin: http://localhost:3000" \
  http://localhost:8000/health

# Restart API
docker-compose restart rag-backend
```

B. **Build Failed**
```bash
# Rebuild frontend
docker-compose build --no-cache rag-frontend

# Restart
docker-compose restart rag-frontend
```

C. **Environment Variables Missing**
```bash
# Check .env has NEXT_PUBLIC_API_URL
cat .env | grep NEXT_PUBLIC_API_URL

# Should be: NEXT_PUBLIC_API_URL=http://localhost:8000

# Restart frontend
docker-compose restart rag-frontend
```

---

## Performance Optimization

### Query Optimization

```bash
# 1. Check query stats
curl http://localhost:8000/stats

# 2. Lower threshold for faster results
# threshold: 0.3 instead of 0.5

# 3. Reduce result limit
# limit: 3 instead of 5

# 4. Add caching
# CACHE_ENABLED=true in .env
```

### Indexing Optimization

```bash
# 1. Batch index documents
# Use /documents/batch-index endpoint

# 2. Increase chunk overlap for better context
# chunk_overlap: 300 instead of 200

# 3. Schedule indexing during off-hours
# Airflow DAG schedule_interval: "0 2 * * *"  (2 AM daily)
```

### System Optimization

```bash
# 1. Monitor resource usage
docker stats --no-stream

# 2. Clean up unused volumes/images
docker volume prune
docker image prune

# 3. Enable persistence
# Ensure all volumes have backup configured
```

---

## Debug Mode

Enable detailed logging:

```bash
# In .env
DEBUG=true
LOG_LEVEL=DEBUG

# Restart services
docker-compose restart

# View detailed logs
docker-compose logs -f --tail=100
```

---

## Getting Help

1. **Check logs first**
   ```bash
   docker-compose logs [service] | head -100
   ```

2. **Search documentation**
   - [Architecture Guide](../architecture/ARCHITECTURE.md)
   - [API Reference](../reference/API_REFERENCE.md)
   - [Deployment Guide](./DEPLOYMENT.md)

3. **Run diagnostics**
   ```bash
   ./ops/scripts/health-check.sh
   ./ops/scripts/diagnose.sh
   ```

4. **Common fixes**
   - Restart services: `./ops/scripts/restart.sh`
   - Clean state: `./ops/scripts/clean.sh`
   - Full rebuild: `./ops/scripts/rebuild.sh`

5. **System information**
   ```bash
   docker --version
   docker-compose --version
   docker-compose config | grep -A5 services
   ```

---

Last Updated: January 2025
Version: 1.0.0

## "Collection expecting embedding with dimension of N, got M"

The vector index was built with a different embedding model. A Chroma
collection's vector width is fixed when it is first written, so the existing
index cannot accept vectors from the new model.

This is expected after switching `EMBEDDING_PROVIDER`, changing the embedding
model, or upgrading from a release that used Ollama embeddings.

Rebuild the index:

- In the app, open **Activity** and use **Rebuild**, or
- `curl -X POST http://127.0.0.1:<port>/jobs/rebuild`

Rebuilding recreates the collection and re-queues every catalogued document, so
the original files must still be at their recorded paths. Documents whose source
has moved are reported in `missing_sources` and need re-importing.

Newer builds refuse the import up front with `index_model_mismatch` and name the
remedy, rather than surfacing the driver's dimension error.

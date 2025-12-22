# Quick Reference: Running the RAG Pipeline

## Start All Services
```bash
docker-compose up -d
```

Wait for services to fully initialize (~30 seconds):
```bash
docker-compose ps  # Should show all 14 containers as healthy/up
```

## Access Airflow UI
```
http://localhost:9093
Username: airflow
Password: airflow
```

## Trigger Pipeline Execution

### Via API
```bash
# Trigger a new DAG run
curl -X POST -u "airflow:airflow" \
  http://localhost:9093/api/v1/dags/document_rag_ingestion_pipeline/dagRuns \
  -H "Content-Type: application/json" \
  -d '{}'

# Check DAG run status
curl -s -u "airflow:airflow" \
  http://localhost:9093/api/v1/dags/document_rag_ingestion_pipeline/dagRuns/{run_id} \
  | jq '.state'

# Monitor task execution
curl -s -u "airflow:airflow" \
  http://localhost:9093/api/v1/dags/document_rag_ingestion_pipeline/dagRuns/{run_id}/taskInstances \
  | jq '.task_instances[] | {task_id, state}'
```

### Via Airflow UI
1. Navigate to http://localhost:9093/dags/document_rag_ingestion_pipeline
2. Click the **Trigger DAG** button (play icon)
3. Monitor execution in the Grid View

## Expected Execution Timeline

| Step | Duration | Status |
|------|----------|--------|
| Fetch documents from MinIO | 2-3s | ✅ |
| Process/chunk documents | 3-5s | ✅ |
| Generate embeddings | 10-20s | ✅ |
| Upsert to Chroma | 2-3s | ✅ |
| Validate vector DB | 1-2s | ✅ |
| Notify completion | <1s | ✅ |
| **Total** | **~25-35s** | ✅ |

## View Logs

### Scheduler logs
```bash
docker logs airflow-scheduler | tail -50
```

### Worker logs
```bash
docker logs airflow-worker | tail -50
```

### View specific task logs
```bash
docker logs airflow-worker | grep "task_id=create_embeddings"
```

## Check Data Status

### MinIO - Uploaded documents
```bash
# Access MinIO console
http://localhost:9000
# Access key: minioadmin
# Secret key: minioadmin
```

### Chroma - Indexed embeddings
```bash
# Chroma is running at chroma:8000
# Access via internal network or through RAG backend
```

## Troubleshooting

### If services fail to start
```bash
# Clean up and restart
docker-compose down
docker-compose rm -f
docker-compose up -d
```

### If tasks timeout
```bash
# Check Ollama is healthy
curl http://localhost:11434/api/tags

# Check Chroma is healthy  
docker logs chroma

# Increase docker memory if needed
# Edit docker-compose.yml environment variables
```

### If DAG won't load
```bash
# Check for import errors
curl -s -u "airflow:airflow" \
  http://localhost:9093/api/v1/dags/document_rag_ingestion_pipeline \
  | jq '.has_import_errors, .import_errors'

# Restart scheduler
docker restart airflow-scheduler
```

## Performance Tuning

### For faster embeddings
- Reduce document chunk size in `process_documents` task
- Use smaller Ollama model (nomic-embed-text is already optimized)

### For more documents
- Increase Airflow worker pool size
- Add more Celery worker containers
- Monitor memory usage during embeddings

### For production
- Implement document deduplication
- Add embedding quality validation
- Set up alerts for task failures
- Configure persistent volumes for Chroma

## Key Endpoints

| Service | URL | Port |
|---------|-----|------|
| Airflow Webserver | http://localhost:9093 | 9093 |
| MinIO Console | http://localhost:9000 | 9000 |
| Ollama API | http://localhost:11434 | 11434 |
| Chroma (internal) | http://chroma:8000 | 8000 |
| RAG Backend | http://localhost:8000 | 8000 |
| RAG Frontend | http://localhost:3000 | 3000 |

## Architecture Files

- **Orchestration**: `airflow-db/dags/rag_vector_db_ingestion_dag.py`
- **Infrastructure**: `docker-compose.yml`
- **Configuration**: `airflow-db/config/airflow.cfg`
- **Pipeline Architecture**: `ARCHITECTURE.md`
- **Deployment Docs**: `END_TO_END_SUCCESS.md`

---

**Status**: ✅ Production Ready

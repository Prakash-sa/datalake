# RAG System - Quick Start Guide

## System Status
✅ **All Services Running and Operational**

## Access Points
- **Frontend**: http://localhost:3000 - User interface for document queries
- **RAG API**: http://localhost:8000 - REST API endpoints
- **Airflow UI**: http://localhost:8080 - DAG monitoring and triggers
- **MinIO Console**: http://localhost:9000 - Document storage UI
- **Ollama API**: http://localhost:11434 - LLM/Embedding API

## Quick Commands

### Search for Documents (API)
```bash
# Search for documents by query
curl -X POST http://localhost:8000/documents/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "what is kubernetes?",
    "k": 5,
    "min_score": 0.3
  }'
```

### Full RAG Query (Search + LLM Response)
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "explain kubernetes architecture",
    "k": 3
  }'
```

### Get Search Statistics
```bash
curl http://localhost:8000/stats
```

### Health Check
```bash
curl http://localhost:8000/health
```

## Running the Airflow DAG

### Trigger Document Ingestion
```bash
docker exec airflow-webserver airflow dags trigger document_rag_ingestion_pipeline
```

### Check DAG Status
```bash
docker exec airflow-webserver airflow dags list
docker exec airflow-webserver airflow dags state document_rag_ingestion_pipeline
```

### View DAG Runs
Open http://localhost:8080 and look for `document_rag_ingestion_pipeline`

## Database Operations

### View Documents in Chroma
```python
import chromadb

client = chromadb.PersistentClient(
    path="./volumes/chroma_db"
)
collection = client.get_collection("documents")

# Count documents
print(f"Documents: {collection.count()}")

# Query documents
results = collection.query(
    query_texts=["your query here"],
    n_results=5
)
```

### Add Test Documents
```python
collection.add(
    ids=["doc1"],
    documents=["Your document text"],
    metadatas=[{"source": "manual"}]
)
```

## Docker Container Management

### View Running Containers
```bash
docker ps
```

### Check Service Logs
```bash
docker logs rag-backend -f        # RAG backend logs
docker logs rag-frontend -f       # Frontend logs
docker logs airflow-scheduler -f  # Airflow scheduler
docker logs rag-backend 2>&1 | grep "Chroma"  # Chroma initialization
```

### Restart Services
```bash
docker restart rag-backend        # Restart RAG backend
docker restart rag-frontend       # Restart frontend
docker-compose restart             # Restart all services
```

## Troubleshooting

### RAG Search Returns No Results
1. Check Chroma has documents:
   ```bash
   docker logs rag-backend | grep "📊 Chroma collection"
   ```
2. Verify collection count > 0
3. Restart backend if needed: `docker restart rag-backend`

### Ollama LLM Not Available (404 error)
1. Check Ollama is running: `curl http://localhost:11434/api/tags`
2. Documents still searchable without LLM
3. Ollama may need to warm up after restart

### High Latency on Searches
1. Check Chroma collection size: `docker logs rag-backend`
2. Reduce `k` parameter (number of results)
3. Verify MinIO is healthy: `curl http://localhost:9000`

### Airflow DAG Not Executing
1. Check scheduler is running: `docker logs airflow-scheduler`
2. Verify DAG syntax: `docker exec airflow-webserver airflow dags validate`
3. Check Redis for task queue: `docker logs redis`

## Performance Tips

### For Large Document Sets
- Increase chunk size in `process_documents()` (trade: fewer chunks vs larger contexts)
- Adjust `k` parameter based on document size
- Use `min_score` to filter low-relevance results

### For Faster Response Times
- Reduce `k` parameter
- Increase `min_score` threshold
- Use specific queries (avoid very broad searches)

### For Better Search Quality
- Decrease `min_score` to 0.2 for broader matching
- Increase `k` to 10 for more context
- Ensure documents are well-chunked (1000 char chunks)

## Integration Points

### Adding New Documents
1. Upload to MinIO bucket: `documents`
2. Trigger Airflow DAG (auto-runs daily)
3. Documents appear in Chroma (indexed with embeddings)
4. Immediately searchable via RAG API

### Custom Embeddings Model
Edit `embedding_model` in docker-compose.yml:
- `nomic-embed-text` (current, 768 dims)
- `all-minilm-l6-v2` (384 dims, faster)
- `all-mpnet-base-v2` (768 dims, higher quality)

### Custom LLM Model
Edit `llm_model` in docker-compose.yml:
- `orca-mini` (current, fast, 7B params)
- `mistral` (faster)
- `neural-chat` (balanced)
- `llama2` (higher quality, slower)

## API Response Examples

### Successful Search (3 documents found)
```json
{
  "status": "success",
  "results": [
    {
      "id": "kubernetes_1",
      "content": "Kubernetes is an open-source container...",
      "relevance_score": 0.785,
      "metadata": {"topic": "kubernetes", "type": "definition"}
    }
  ],
  "timestamp": "2025-12-22T03:15:35.380888"
}
```

### No Results Found
```json
{
  "status": "no_results",
  "query": "nonexistent topic",
  "answer": "No relevant documents found in the knowledge base.",
  "retrieved_documents": [],
  "document_count": 0,
  "timestamp": "2025-12-22T03:15:35.380888"
}
```

## Next Steps

1. **Upload Documents**: Add PDFs/text files to MinIO `documents` bucket
2. **Trigger Pipeline**: Run Airflow DAG to process and embed documents
3. **Query Documents**: Use frontend or API to search
4. **Monitor Results**: Check Airflow UI for pipeline status
5. **Iterate**: Refine documents or adjust search parameters

## Support

For detailed technical information, see:
- `CHROMA_INTEGRATION_SUMMARY.md` - Complete integration details
- `ARCHITECTURE.md` - System architecture overview
- `PRODUCTION_DEPLOYMENT.md` - Production deployment guide

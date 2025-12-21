# Document RAG Engine - Backend

Production-ready Retrieval-Augmented Generation (RAG) engine for semantic search and intelligent document analysis.

## ✅ Production Ready Features

- **Validated API**: Pydantic models with input constraints and field validators
- **Error Handling**: Global exception handlers with proper HTTP status codes
- **Monitoring**: Prometheus-ready metrics and /stats endpoint
- **Multi-Worker**: Gunicorn with 4 Uvicorn workers for concurrent requests
- **Resource Limits**: Max documents, query length, and timeout constraints
- **Security**: Non-root container user, restricted CORS, environment-based config
- **Logging**: Structured logging with configurable levels and comprehensive debugging
- **Health Checks**: Endpoint-based health checks for orchestration
- **Configuration**: Multi-environment support (development, production, testing)

## Quick Start

### Development Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # macOS/Linux
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
nano .env  # Edit as needed

# Start development server (single worker)
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Or: Make sure .env has ENV=development
uvicorn main:app --reload
```

### Production Setup

```bash
# Use docker-compose for production
docker-compose -f docker-compose.prod.yml up -d

# Or: Build and run manually
docker build -f Dockerfile.prod -t rag-engine:prod .
docker run -d \
  --name rag-engine \
  -p 8000:8000 \
  -p 9090:9090 \
  -e ENV=production \
  -e WORKERS=4 \
  rag-engine:prod
```

## API Endpoints

### Core Endpoints

#### `GET /health`
Health check for orchestration and monitoring.

```bash
curl http://localhost:8000/health
# Response:
# {
#   "status": "healthy",
#   "version": "2.0.0",
#   "timestamp": "2024-01-15T10:30:45.123Z"
# }
```

#### `GET /stats`
Engine statistics and metrics.

```bash
curl http://localhost:8000/stats
# Response:
# {
#   "documents_indexed": 150,
#   "queries_processed": 1024,
#   "errors": 5,
#   "total_documents": 150,
#   "timestamp": "2024-01-15T10:30:45.123Z"
# }
```

#### `POST /query`
Semantic search with LLM-powered analysis.

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the main sales trends?",
    "k": 5,
    "min_score": 0.3
  }'

# Response:
# {
#   "query": "What are the main sales trends?",
#   "results": [
#     {
#       "content": "2024 sales increased by 25%...",
#       "relevance_score": 0.95,
#       "source": "sales_report.pdf"
#     }
#   ],
#   "llm_analysis": "Based on the documents, key trends include...",
#   "processing_time_seconds": 2.34
# }
```

**Parameters**:
- `query` (string, required): Search query (1-1000 chars)
- `k` (integer, optional): Number of results (1-100, default: 5)
- `min_score` (float, optional): Minimum relevance score (0-1, default: 0.0)

#### `POST /documents/search`
Semantic search without LLM analysis (faster).

```bash
curl -X POST http://localhost:8000/documents/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "sales trends",
    "k": 10,
    "min_score": 0.2
  }'
```

#### `POST /documents/index`
Index documents for semantic search.

```bash
curl -X POST http://localhost:8000/documents/index \
  -H "Content-Type: application/json" \
  -d '{
    "documents": [
      {
        "id": "doc1",
        "content": "Document content here...",
        "metadata": {"source": "report.pdf", "date": "2024-01-15"}
      }
    ]
  }'

# Response:
# {
#   "status": "success",
#   "documents_indexed": 1,
#   "errors": 0,
#   "details": []
# }
```

### Documentation

#### `GET /`
API documentation and status.

```bash
curl http://localhost:8000/
```

## Configuration

### Environment Variables

```bash
# Environment
ENV=production                    # development, testing, production
LOG_LEVEL=INFO                   # DEBUG, INFO, WARNING, ERROR

# Server
HOST=0.0.0.0
PORT=8000
WORKERS=4                        # Gunicorn workers (prod default: 4)

# CORS
ALLOWED_ORIGINS=https://yourdomain.com,https://app.yourdomain.com

# RAG Engine
OLLAMA_URL=http://ollama:11434
EMBEDDING_MODEL=all-minilm      # Embedding model name
LLM_MODEL=mistral               # LLM model name
LLM_TEMPERATURE=0.3             # 0.0-1.0, lower = more deterministic

# Resource Limits
MAX_DOCUMENTS=10000             # Max documents to index
MAX_QUERY_LENGTH=1000           # Max query string length
MAX_RESULTS=100                 # Max search results
QUERY_TIMEOUT=30                # Query timeout in seconds

# Performance
EMBEDDING_CACHE_SIZE=128        # LRU cache size for embeddings
CORS_CACHE_MAX_AGE=3600         # CORS cache age in seconds

# Monitoring
ENABLE_METRICS=true
METRICS_PORT=9090
```

### Using Config Classes

```python
from config import get_config

# Automatically detects environment
config = get_config()

print(config.LOG_LEVEL)      # INFO (production) or DEBUG (development)
print(config.WORKERS)         # 4 (production) or 1 (development)
print(config.DEBUG)           # False (production) or True (development)
print(config.ALLOWED_ORIGINS) # Restricted (prod) or ["*"] (dev)
```

## Error Handling

### HTTP Status Codes

- **200 OK**: Successful request
- **400 Bad Request**: Invalid input (validation error)
- **404 Not Found**: Resource not found
- **500 Internal Server Error**: Unexpected server error

### Error Response Format

```json
{
  "detail": "Query must be between 1 and 1000 characters",
  "status_code": 400,
  "timestamp": "2024-01-15T10:30:45.123Z"
}
```

### Common Errors

**Invalid Query Length**
```
400 Bad Request: "Query must be between 1 and 1000 characters"
```

**No Documents Available**
```
400 Bad Request: "No documents have been indexed yet"
```

**LLM Inference Failed**
```
500 Internal Server Error: "Failed to generate analysis from LLM"
```

**Ollama Connection Failed**
```
500 Internal Server Error: "Could not connect to Ollama service at http://ollama:11434"
```

## Monitoring & Metrics

### Prometheus Metrics

All metrics are exposed at `/metrics` endpoint (when enabled):

```bash
curl http://localhost:9090/metrics
```

**Available Metrics**:
- `http_requests_total`: Total HTTP requests
- `http_request_duration_seconds`: Request duration histogram
- `rag_documents_indexed_total`: Total documents indexed
- `rag_queries_processed_total`: Total queries processed
- `rag_errors_total`: Total errors encountered

### Stats Endpoint

```bash
curl http://localhost:8000/stats
```

Returns:
- `documents_indexed`: Current total
- `queries_processed`: Current total
- `errors`: Current total
- `total_documents`: Active documents in store
- `timestamp`: Current timestamp

## Development

### Project Structure

```
backend/
├── main.py                 # FastAPI application
├── rag_engine.py          # RAG logic and LLM integration
├── config.py              # Configuration management
├── requirements.txt       # Python dependencies
├── Dockerfile             # Development container
├── Dockerfile.prod        # Production container
├── .env.example           # Example environment variables
└── README.md              # This file
```

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test
pytest tests/test_main.py::test_health_endpoint
```

### Code Quality

```bash
# Format code
black *.py

# Check style
ruff check .

# Type checking
mypy main.py rag_engine.py
```

### Adding New Endpoints

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v2", tags=["custom"])

class MyRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)

@router.post("/custom")
async def custom_endpoint(request: MyRequest):
    """
    Detailed endpoint documentation.
    
    Args:
        request: Request object with query
        
    Returns:
        Response with analysis
    """
    try:
        # Implementation
        return {"status": "success", "data": []}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Error in custom endpoint")
        raise HTTPException(status_code=500, detail="Internal server error")

app.include_router(router)
```

## Performance Tuning

### For High Traffic

```bash
# Increase workers based on CPU cores
# Formula: (2 * CPU_cores) + 1
WORKERS=9  # For 4-core server

# Increase result cache
EMBEDDING_CACHE_SIZE=512

# Reduce query timeout (if appropriate)
QUERY_TIMEOUT=20
```

### For Resource-Constrained Environments

```bash
# Reduce workers
WORKERS=2

# Reduce cache
EMBEDDING_CACHE_SIZE=64

# Limit document indexing
MAX_DOCUMENTS=1000

# Reduce LLM model complexity
LLM_MODEL=orca-mini  # Smaller model
```

## Deployment

### Docker Compose (Recommended)

```bash
# Development
docker-compose up

# Production
docker-compose -f docker-compose.prod.yml up -d
```

### Kubernetes

See [Kubernetes deployment guide](../kubernetes/README.md) for Helm charts and manifests.

### Manual Deployment

```bash
# Build production image
docker build -f Dockerfile.prod -t rag-engine:prod .

# Push to registry
docker tag rag-engine:prod myregistry/rag-engine:prod
docker push myregistry/rag-engine:prod

# Run container
docker run -d \
  --name rag-engine \
  -p 8000:8000 \
  -e ENV=production \
  myregistry/rag-engine:prod
```

## Troubleshooting

### Port Already in Use

```bash
# Find process using port 8000
lsof -i :8000

# Kill process
kill -9 <PID>

# Or use different port
python -m uvicorn main:app --port 8001
```

### High Memory Usage

```bash
# Reduce cache size
EMBEDDING_CACHE_SIZE=64

# Limit concurrent workers
WORKERS=2

# Restart service
docker-compose -f docker-compose.prod.yml restart rag-backend
```

### Slow Queries

1. Check `processing_time_seconds` in response
2. Increase `k` to reduce LLM analysis time
3. Check Ollama logs: `docker logs ollama`
4. Monitor CPU/memory: `docker stats`

### Connection Errors

```bash
# Verify Ollama is running
curl http://ollama:11434/api/tags

# Verify MinIO is running
curl http://minio:9000/minio/health/live

# Check network connectivity
docker exec rag-backend ping ollama
```

## Contributing

1. Create feature branch: `git checkout -b feature/my-feature`
2. Make changes with tests
3. Run quality checks: `black . && ruff check . && pytest`
4. Create pull request

## License

Proprietary - Internal Use Only

## Support

For issues or questions:
1. Check logs: `docker-compose logs rag-backend`
2. Review metrics: `http://localhost:9090`
3. Check API docs: `http://localhost:8000/docs`
4. See [PRODUCTION_DEPLOYMENT.md](../PRODUCTION_DEPLOYMENT.md) for production issues

---

**Version**: 2.0.0  
**Status**: ✅ Production Ready  
**Last Updated**: 2024-01-15

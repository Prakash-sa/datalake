# RAG Engine API Reference

## Base URL
```
http://localhost:8000
```

## Authentication
Currently no authentication required (add OAuth2 in production).

## Endpoints

### 1. Health Check

**Endpoint:** `GET /health`

**Description:** Check if the API is running and all services are connected.

**Response:**
```json
{
  "status": "healthy",
  "services": {
    "database": "connected",
    "cache": "connected",
    "vector_db": "connected",
    "llm": "connected"
  },
  "timestamp": "2025-01-10T10:00:00Z"
}
```

**Status Codes:**
- `200`: All services healthy
- `503`: One or more services unavailable

---

### 2. Search Documents

**Endpoint:** `POST /documents/search`

**Description:** Semantic search across indexed documents using similarity matching.

**Request Body:**
```json
{
  "query": "What is machine learning?",
  "limit": 5,
  "threshold": 0.5,
  "metadata_filter": {
    "source": "documents/technical.pdf"
  }
}
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | Search query text |
| `limit` | integer | No | Max results (default: 5, max: 50) |
| `threshold` | float | No | Similarity score threshold (0-1, default: 0.5) |
| `metadata_filter` | object | No | Filter results by metadata |

**Response:**
```json
{
  "query": "What is machine learning?",
  "results": [
    {
      "id": "chunk_123",
      "content": "Machine learning is a type of artificial intelligence...",
      "score": 0.92,
      "metadata": {
        "source": "documents/technical.pdf",
        "page": 42,
        "chunk_index": 3,
        "timestamp": "2025-01-10T09:00:00Z"
      }
    },
    {
      "id": "chunk_124",
      "content": "ML models learn patterns from data...",
      "score": 0.87,
      "metadata": {
        "source": "documents/intro.md",
        "page": 1,
        "chunk_index": 0,
        "timestamp": "2025-01-10T09:00:00Z"
      }
    }
  ],
  "count": 2,
  "execution_time_ms": 245
}
```

**Status Codes:**
- `200`: Success
- `400`: Invalid query or parameters
- `503`: Vector database unavailable

**Example cURL:**
```bash
curl -X POST http://localhost:8000/documents/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is machine learning?",
    "limit": 5,
    "threshold": 0.5
  }'
```

---

### 3. Query with LLM Response

**Endpoint:** `POST /query`

**Description:** Search documents and generate an LLM response based on context.

**Request Body:**
```json
{
  "query": "Explain machine learning in simple terms",
  "system_prompt": "You are a helpful assistant...",
  "max_tokens": 500,
  "temperature": 0.7,
  "include_sources": true
}
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | Question or prompt |
| `system_prompt` | string | No | Custom system prompt |
| `max_tokens` | integer | No | Max response tokens (default: 1000) |
| `temperature` | float | No | LLM creativity (0-1, default: 0.7) |
| `include_sources` | boolean | No | Include source documents (default: true) |

**Response:**
```json
{
  "query": "Explain machine learning in simple terms",
  "response": "Machine learning is a technology that allows computers to learn from data without being explicitly programmed...",
  "sources": [
    {
      "id": "chunk_123",
      "content": "Machine learning is a type of artificial intelligence...",
      "score": 0.92,
      "metadata": {
        "source": "documents/technical.pdf",
        "page": 42
      }
    }
  ],
  "model": "ollama/nomic-embed-text",
  "execution_time_ms": 3456,
  "tokens_used": 245
}
```

**Status Codes:**
- `200`: Success
- `400`: Invalid query
- `503`: LLM or database unavailable
- `408`: Request timeout (LLM inference too slow)

**Example cURL:**
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Explain machine learning",
    "max_tokens": 500,
    "temperature": 0.7
  }'
```

---

### 4. Index Document

**Endpoint:** `POST /documents/index`

**Description:** Manually index a document (usually done via Airflow).

**Request Body:**
```json
{
  "file_path": "documents/new-doc.pdf",
  "content": "Full document content here...",
  "metadata": {
    "title": "New Document",
    "author": "John Doe",
    "date": "2025-01-10"
  },
  "chunk_size": 1000,
  "chunk_overlap": 200
}
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file_path` | string | Yes | Path in MinIO |
| `content` | string | Yes | Document content |
| `metadata` | object | No | Custom metadata |
| `chunk_size` | integer | No | Characters per chunk (default: 1000) |
| `chunk_overlap` | integer | No | Overlap between chunks (default: 200) |

**Response:**
```json
{
  "status": "success",
  "file_path": "documents/new-doc.pdf",
  "chunks_created": 5,
  "embeddings_generated": 5,
  "indexed_at": "2025-01-10T10:00:00Z",
  "execution_time_ms": 2345
}
```

**Status Codes:**
- `200`: Success
- `400`: Missing required fields
- `413`: Content too large
- `503`: Database unavailable

---

### 5. Get Document Metadata

**Endpoint:** `GET /documents/:doc_id`

**Description:** Get metadata about an indexed document.

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `doc_id` | string | Document chunk ID |

**Response:**
```json
{
  "id": "chunk_123",
  "document_id": "doc_456",
  "source": "documents/technical.pdf",
  "content_preview": "Machine learning is a type of...",
  "metadata": {
    "page": 42,
    "chunk_index": 3,
    "timestamp": "2025-01-10T09:00:00Z",
    "embedding_model": "nomic-embed-text"
  },
  "chunk_count": 5,
  "vector_dim": 768
}
```

**Status Codes:**
- `200`: Success
- `404`: Document not found
- `503`: Database unavailable

---

### 6. List Collections

**Endpoint:** `GET /collections`

**Description:** List all indexed document collections.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 50 | Max results |
| `offset` | integer | 0 | Pagination offset |

**Response:**
```json
{
  "collections": [
    {
      "name": "documents",
      "document_count": 42,
      "chunk_count": 1240,
      "size_mb": 145.2,
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-10T10:00:00Z",
      "metadata_fields": ["source", "page", "author"]
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

**Status Codes:**
- `200`: Success
- `503`: Vector database unavailable

---

### 7. Delete Document

**Endpoint:** `DELETE /documents/:doc_id`

**Description:** Delete a document and its embeddings from the database.

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `doc_id` | string | Document ID to delete |

**Response:**
```json
{
  "status": "success",
  "deleted_id": "chunk_123",
  "chunks_deleted": 5,
  "execution_time_ms": 345
}
```

**Status Codes:**
- `200`: Success
- `404`: Document not found
- `503`: Database unavailable

---

### 8. Batch Index

**Endpoint:** `POST /documents/batch-index`

**Description:** Index multiple documents at once.

**Request Body:**
```json
{
  "documents": [
    {
      "file_path": "doc1.pdf",
      "content": "...",
      "metadata": {"title": "Doc 1"}
    },
    {
      "file_path": "doc2.txt",
      "content": "...",
      "metadata": {"title": "Doc 2"}
    }
  ],
  "parallel": true
}
```

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `documents` | array | Array of document objects |
| `parallel` | boolean | Process in parallel (default: true) |

**Response:**
```json
{
  "status": "success",
  "total_documents": 2,
  "successful": 2,
  "failed": 0,
  "results": [
    {
      "file_path": "doc1.pdf",
      "status": "success",
      "chunks_created": 5
    },
    {
      "file_path": "doc2.txt",
      "status": "success",
      "chunks_created": 3
    }
  ],
  "execution_time_ms": 5678
}
```

**Status Codes:**
- `200`: Completed (check results for individual failures)
- `400`: Invalid request format
- `503`: Database unavailable

---

### 9. Statistics

**Endpoint:** `GET /stats`

**Description:** Get system statistics and performance metrics.

**Response:**
```json
{
  "system": {
    "total_documents": 42,
    "total_chunks": 1240,
    "total_embeddings": 1240,
    "database_size_mb": 145.2,
    "indexed_at": "2025-01-10T10:00:00Z"
  },
  "performance": {
    "avg_query_time_ms": 234,
    "avg_embedding_time_ms": 45,
    "p95_query_time_ms": 456,
    "p99_query_time_ms": 789
  },
  "cache": {
    "hit_rate": 0.78,
    "size_mb": 52.3,
    "entries": 1024
  },
  "health": {
    "database": "healthy",
    "cache": "healthy",
    "llm": "healthy"
  }
}
```

**Status Codes:**
- `200`: Success
- `503`: Some services unavailable

---

## Error Responses

All error responses follow this format:

```json
{
  "error": {
    "code": "INVALID_QUERY",
    "message": "Query string cannot be empty",
    "details": {
      "field": "query",
      "reason": "required"
    },
    "timestamp": "2025-01-10T10:00:00Z",
    "request_id": "req_abc123def"
  }
}
```

### Common Error Codes

| Code | Status | Description |
|------|--------|-------------|
| `INVALID_QUERY` | 400 | Query validation failed |
| `INVALID_PARAMETER` | 400 | Invalid parameter value |
| `MISSING_FIELD` | 400 | Required field missing |
| `NOT_FOUND` | 404 | Resource not found |
| `CONFLICT` | 409 | Resource already exists |
| `RATE_LIMITED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Server error |
| `SERVICE_UNAVAILABLE` | 503 | Database/service down |
| `TIMEOUT` | 408 | Request timeout |

---

## Rate Limiting

- **Requests/minute:** 60 (default)
- **Concurrent requests:** 10
- **Query timeout:** 30 seconds
- **Max request size:** 10MB

Headers:
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 59
X-RateLimit-Reset: 2025-01-10T10:01:00Z
```

---

## Authentication (Production)

Add OAuth2 authentication:

```python
# Example bearer token
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

---

## Interactive Documentation

Access OpenAPI/Swagger UI:
```
http://localhost:8000/docs
```

Access ReDoc alternative:
```
http://localhost:8000/redoc
```

---

## Code Examples

### Python
```python
import requests
import json

API_URL = "http://localhost:8000"

# Search documents
response = requests.post(
    f"{API_URL}/documents/search",
    json={
        "query": "machine learning",
        "limit": 5
    }
)
results = response.json()
print(json.dumps(results, indent=2))

# Query with LLM response
response = requests.post(
    f"{API_URL}/query",
    json={
        "query": "Explain machine learning",
        "max_tokens": 500
    }
)
response_data = response.json()
print(response_data["response"])
```

### JavaScript/Node.js
```javascript
const API_URL = "http://localhost:8000";

// Search documents
async function search(query) {
  const response = await fetch(`${API_URL}/documents/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query: query,
      limit: 5
    })
  });
  return response.json();
}

// Query with response
async function queryWithResponse(question) {
  const response = await fetch(`${API_URL}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query: question,
      max_tokens: 500
    })
  });
  const data = await response.json();
  return data.response;
}

// Usage
search("machine learning").then(console.log);
queryWithResponse("What is AI?").then(console.log);
```

### cURL
```bash
# Search
curl -X POST http://localhost:8000/documents/search \
  -H "Content-Type: application/json" \
  -d '{"query":"machine learning","limit":5}'

# Query
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query":"What is AI?","max_tokens":500}'

# Health check
curl http://localhost:8000/health

# Stats
curl http://localhost:8000/stats
```

---

## Webhooks (Optional)

Configure webhooks for async notifications:

```json
{
  "event": "document.indexed",
  "url": "https://example.com/webhook",
  "events": ["document.indexed", "index.complete"],
  "active": true
}
```

---

Last Updated: January 2025
Version: 1.0.0

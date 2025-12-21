# Testing Guide

Complete testing guide for the Document RAG Engine backend.

## Test Setup

### Installation

```bash
# Install test dependencies
pip install -r requirements.txt
pip install pytest pytest-asyncio pytest-cov pytest-mock

# Verify installation
pytest --version
```

### Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with coverage report
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/test_main.py

# Run specific test
pytest tests/test_main.py::test_health_endpoint

# Run with markers
pytest -m "unit"
pytest -m "integration"

# Run in parallel (if pytest-xdist installed)
pytest -n auto
```

## Unit Tests

### Configuration Tests

```python
# test_config.py
import os
from config import get_config, DevelopmentConfig, ProductionConfig

def test_development_config():
    os.environ['ENV'] = 'development'
    config = get_config()
    assert config.DEBUG is True
    assert config.WORKERS == 1
    assert config.LOG_LEVEL == "DEBUG"

def test_production_config():
    os.environ['ENV'] = 'production'
    config = get_config()
    assert config.DEBUG is False
    assert config.WORKERS == 4
    assert config.LOG_LEVEL == "INFO"

def test_config_from_env():
    os.environ['MAX_DOCUMENTS'] = '5000'
    config = get_config()
    assert config.MAX_DOCUMENTS == 5000
```

### RAG Engine Tests

```python
# test_rag_engine.py
import pytest
from rag_engine import DocumentRAGEngine

@pytest.fixture
def engine():
    """Create RAG engine for testing"""
    return DocumentRAGEngine()

def test_index_documents(engine):
    documents = [
        {
            "id": "doc1",
            "content": "Sample document content",
            "metadata": {"source": "test.pdf"}
        }
    ]
    result = engine.index_documents(documents)
    assert result['status'] == 'success'
    assert result['documents_indexed'] == 1

def test_search_documents(engine):
    # First index documents
    documents = [
        {
            "id": "doc1",
            "content": "The quick brown fox jumps over the lazy dog",
            "metadata": {}
        }
    ]
    engine.index_documents(documents)
    
    # Then search
    results = engine.search_documents("quick fox", k=5, min_score=0.0)
    assert len(results) > 0
    assert 'relevance_score' in results[0]

def test_query_documents(engine):
    # Index documents first
    documents = [
        {
            "id": "doc1",
            "content": "Python is a popular programming language",
            "metadata": {}
        }
    ]
    engine.index_documents(documents)
    
    # Query with LLM
    result = engine.query_documents("What is Python?", k=5)
    assert 'query' in result
    assert 'llm_analysis' in result
    assert result['status'] == 'success'

def test_query_timeout(engine):
    # This test verifies timeout handling
    with pytest.raises(TimeoutError):
        engine.query_documents("test" * 1000, k=100, timeout=0.001)

def test_input_validation(engine):
    # Test empty query
    with pytest.raises(ValueError, match="Query cannot be empty"):
        engine.search_documents("")
    
    # Test query too long
    with pytest.raises(ValueError, match="Query exceeds maximum length"):
        engine.search_documents("x" * 2000)
    
    # Test invalid k
    with pytest.raises(ValueError, match="k must be between"):
        engine.search_documents("test", k=101)

def test_get_stats(engine):
    stats = engine.get_stats()
    assert 'documents_indexed' in stats
    assert 'queries_processed' in stats
    assert 'errors' in stats
    assert 'total_documents' in stats
    assert 'timestamp' in stats
```

### API Endpoint Tests

```python
# test_main.py
import pytest
from fastapi.testclient import TestClient
from main import app

@pytest.fixture
def client():
    return TestClient(app)

def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()['status'] == 'healthy'
    assert 'timestamp' in response.json()

def test_stats_endpoint(client):
    response = client.get("/stats")
    assert response.status_code == 200
    assert 'documents_indexed' in response.json()

def test_query_endpoint_valid(client):
    response = client.post("/query", json={
        "query": "What is this?",
        "k": 5,
        "min_score": 0.3
    })
    assert response.status_code == 200
    assert 'query' in response.json()
    assert 'processing_time_seconds' in response.json()

def test_query_endpoint_validation_error(client):
    # Empty query
    response = client.post("/query", json={
        "query": ""
    })
    assert response.status_code == 400

def test_query_endpoint_query_too_long(client):
    response = client.post("/query", json={
        "query": "x" * 2000
    })
    assert response.status_code == 400

def test_index_endpoint_valid(client):
    response = client.post("/documents/index", json={
        "documents": [
            {
                "id": "doc1",
                "content": "Test document",
                "metadata": {}
            }
        ]
    })
    assert response.status_code == 200
    assert response.json()['status'] in ['success', 'partial_success']

def test_index_endpoint_empty_documents(client):
    response = client.post("/documents/index", json={
        "documents": []
    })
    assert response.status_code == 400

def test_search_endpoint_valid(client):
    # Index first
    client.post("/documents/index", json={
        "documents": [
            {
                "id": "doc1",
                "content": "Sample document",
                "metadata": {}
            }
        ]
    })
    
    # Search
    response = client.get("/documents/search?query=sample&k=5&min_score=0.0")
    assert response.status_code == 200

def test_search_endpoint_missing_query(client):
    response = client.get("/documents/search?k=5")
    assert response.status_code == 422  # Validation error
```

## Integration Tests

### API Integration

```python
# tests/integration/test_api_integration.py
import pytest
from fastapi.testclient import TestClient
from main import app

@pytest.fixture
def client():
    return TestClient(app)

def test_full_workflow(client):
    """Test complete workflow: index -> search -> query"""
    
    # 1. Index documents
    documents = [
        {
            "id": "sales_2024",
            "content": "Total sales increased by 25% in Q1 2024",
            "metadata": {"source": "sales_report.pdf", "date": "2024-01-15"}
        },
        {
            "id": "market_trends",
            "content": "Market trends show increased demand for AI solutions",
            "metadata": {"source": "market_analysis.pdf", "date": "2024-01-10"}
        }
    ]
    
    index_response = client.post("/documents/index", json={"documents": documents})
    assert index_response.status_code == 200
    assert index_response.json()['status'] == 'success'
    
    # 2. Search documents
    search_response = client.post("/documents/search", json={
        "query": "sales trends",
        "k": 10,
        "min_score": 0.2
    })
    assert search_response.status_code == 200
    assert len(search_response.json()['results']) > 0
    
    # 3. Query with LLM analysis
    query_response = client.post("/query", json={
        "query": "What were the sales trends in Q1 2024?",
        "k": 5
    })
    assert query_response.status_code == 200
    assert 'llm_analysis' in query_response.json()
    
    # 4. Verify stats updated
    stats_response = client.get("/stats")
    assert stats_response.status_code == 200
    assert stats_response.json()['documents_indexed'] >= 2
    assert stats_response.json()['queries_processed'] >= 1

def test_error_recovery(client):
    """Test error handling and recovery"""
    
    # Send invalid document
    response = client.post("/documents/index", json={
        "documents": [
            {
                "id": "bad_doc",
                "content": "",  # Empty content
                "metadata": {}
            }
        ]
    })
    
    # Should still return response (partial success or error)
    assert response.status_code in [200, 400]
    
    # Subsequent valid request should work
    response = client.post("/documents/index", json={
        "documents": [
            {
                "id": "good_doc",
                "content": "Valid content",
                "metadata": {}
            }
        ]
    })
    assert response.status_code == 200
```

## Performance Tests

### Load Testing

```bash
# Install load testing tool
pip install locust

# Create load test
# tests/load/locustfile.py
from locust import HttpUser, task, between

class RAGEngineUser(HttpUser):
    wait_time = between(1, 3)
    
    @task(3)
    def query_documents(self):
        self.client.post("/query", json={
            "query": "What is the meaning of life?",
            "k": 5
        })
    
    @task(1)
    def health_check(self):
        self.client.get("/health")

# Run load test
locust -f tests/load/locustfile.py --host=http://localhost:8000
```

### Stress Testing

```python
# test_stress.py
import pytest
import asyncio
from fastapi.testclient import TestClient
from main import app

@pytest.fixture
def client():
    return TestClient(app)

def test_concurrent_queries(client):
    """Test 100 concurrent queries"""
    import concurrent.futures
    
    def query():
        response = client.post("/query", json={
            "query": "Test query",
            "k": 5
        })
        return response.status_code
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(query) for _ in range(100)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    
    # All should succeed
    assert all(status == 200 for status in results)

def test_memory_stability(client):
    """Test memory usage under load"""
    import psutil
    import time
    
    # Get initial memory
    process = psutil.Process()
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB
    
    # Send 50 requests
    for _ in range(50):
        client.post("/query", json={"query": "test"})
    
    # Check final memory
    final_memory = process.memory_info().rss / 1024 / 1024
    memory_increase = final_memory - initial_memory
    
    # Memory increase should be reasonable (< 100MB)
    assert memory_increase < 100, f"Memory increased by {memory_increase}MB"
```

## Continuous Integration

### GitHub Actions Workflow

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      ollama:
        image: ollama/ollama:latest
        ports:
          - 11434:11434
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.11
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov pytest-asyncio
    
    - name: Run tests
      run: |
        pytest --cov=. --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v2
      with:
        files: ./coverage.xml
```

## Manual Testing

### Health Check

```bash
curl -X GET http://localhost:8000/health
```

### Index Documents

```bash
curl -X POST http://localhost:8000/documents/index \
  -H "Content-Type: application/json" \
  -d '{
    "documents": [
      {
        "id": "test1",
        "content": "This is a test document about Python programming",
        "metadata": {"source": "test.txt"}
      }
    ]
  }'
```

### Search Documents

```bash
curl -X POST http://localhost:8000/documents/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Python programming",
    "k": 5,
    "min_score": 0.3
  }'
```

### Query with LLM

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is Python?",
    "k": 5,
    "min_score": 0.3
  }'
```

## Test Coverage

Target coverage goals:
- **Unit Tests**: 80%+ coverage
- **Integration Tests**: 50%+ coverage
- **Critical Paths**: 100% coverage

### Generate Coverage Report

```bash
# Generate HTML report
pytest --cov=. --cov-report=html

# View report
open htmlcov/index.html  # macOS
# or
xdg-open htmlcov/index.html  # Linux
# or
start htmlcov\index.html  # Windows
```

## Debugging Failed Tests

### Verbose Output

```bash
pytest -vv -s test_file.py::test_name
```

### Print Debug Info

```python
def test_something():
    print("Debug info here")  # Captured with -s flag
    assert True
```

### Use Debugger

```python
def test_something():
    import pdb; pdb.set_trace()  # Breakpoint
    assert True
```

## Test Best Practices

1. **Isolation**: Each test should be independent
2. **Fixtures**: Use pytest fixtures for setup/teardown
3. **Naming**: Use descriptive test names
4. **Mocking**: Mock external services (Ollama, MinIO)
5. **Coverage**: Aim for high coverage of critical paths
6. **Performance**: Tests should complete in < 1 second each
7. **Deterministic**: Tests should have consistent results
8. **Documentation**: Document complex test logic

---

**Testing Framework**: pytest  
**Coverage Tool**: pytest-cov  
**Load Testing**: locust  
**Stress Testing**: concurrent.futures, psutil  
**Status**: ✅ Production Ready


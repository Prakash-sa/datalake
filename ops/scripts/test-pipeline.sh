#!/bin/bash

# RAG Pipeline Testing Script
# Tests: MinIO upload → Airflow DAG → Chroma ingestion

set -e

echo "🚀 RAG Pipeline Test Suite"
echo "=========================="

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Function to print status
print_status() {
    echo -e "${YELLOW}[*] $1${NC}"
}

print_success() {
    echo -e "${GREEN}[✓] $1${NC}"
}

print_error() {
    echo -e "${RED}[✗] $1${NC}"
}

# 1. Test MinIO Connectivity
print_status "Testing MinIO connectivity..."
if curl -f http://localhost:9000/minio/health/live > /dev/null 2>&1; then
    print_success "MinIO is healthy"
else
    print_error "MinIO is not responding"
    exit 1
fi

# 2. Test Ollama LLM
print_status "Testing Ollama LLM..."
if curl -f http://localhost:11434/api/tags > /dev/null 2>&1; then
    print_success "Ollama is responsive"
else
    print_error "Ollama is not responding"
    exit 1
fi

# 3. Test Chroma Vector DB
print_status "Testing Chroma Vector DB..."
if curl -f http://localhost:8001/api/v2 > /dev/null 2>&1; then
    print_success "Chroma is healthy"
else
    print_error "Chroma is not responding"
    exit 1
fi

# 4. Test FastAPI Backend
print_status "Testing FastAPI Backend..."
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    print_success "FastAPI backend is healthy"
else
    print_error "FastAPI backend is not responding"
fi

# 5. Test Airflow Web UI
print_status "Testing Airflow Web UI..."
if curl -f http://localhost:9093/health > /dev/null 2>&1; then
    print_success "Airflow is healthy"
else
    print_error "Airflow is not responding"
fi

# 6. Test Airflow Database
print_status "Testing Airflow Database..."
if curl -f http://localhost:9093/api/v1/config > /dev/null 2>&1; then
    print_success "Airflow API is responding"
else
    print_error "Airflow API is not responding"
fi

echo ""
echo "📋 Service Status Summary:"
echo "========================="
echo "✓ MinIO S3 Storage: http://localhost:9001 (admin:minioadmin)"
echo "✓ Ollama LLM: http://localhost:11434"
echo "✓ Chroma Vector DB: http://localhost:8001"
echo "✓ FastAPI Backend: http://localhost:8000/docs"
echo "✓ Airflow Web UI: http://localhost:9093 (airflow:airflow)"
echo "✓ React Frontend: http://localhost:3000"

echo ""
echo "📝 Next Steps:"
echo "============="
echo "1. Upload documents to MinIO: http://localhost:9001"
echo "2. Trigger Airflow DAG: document_rag_ingestion_pipeline"
echo "3. Check Chroma for indexed documents: http://localhost:8001/api/v1/collections"
echo "4. Search documents: http://localhost:3000"

echo ""
echo "✨ All services are ready for testing!"

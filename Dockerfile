# Multi-stage build for DataLake RAG System
# This is a reference Dockerfile - use docker-compose which builds individual images

FROM apache/airflow:2.9.0 as airflow-base

# Install additional Python dependencies for RAG integration
RUN pip install --no-cache-dir \
    minio==7.2.0 \
    chromadb==0.4.24 \
    langchain==0.1.1 \
    langchain-community==0.0.10 \
    langchain-ollama==0.1.1 \
    ollama==0.1.35 \
    fastapi==0.104.1 \
    uvicorn==0.24.0 \
    requests==2.31.0

# Use individual Dockerfiles in src/services/ for backend and frontend

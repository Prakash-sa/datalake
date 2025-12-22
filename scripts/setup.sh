#!/bin/bash

# ============================================================================
# DataLake RAG System - Setup Script
# ============================================================================
# Initializes environment and prepares the system for first run
# Usage: ./scripts/setup.sh
# ============================================================================

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}DataLake RAG System - Setup${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}\n"

# Create .env file if it doesn't exist
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo -e "${BLUE}[*] Creating .env file...${NC}"
    cat > "$PROJECT_DIR/.env" << 'EOF'
# Airflow Configuration
AIRFLOW_UID=50000
AIRFLOW_IMAGE_NAME=apache/airflow:2.9.0

# Airflow Default User
_AIRFLOW_WWW_USER_USERNAME=airflow
_AIRFLOW_WWW_USER_PASSWORD=airflow

# MinIO Configuration
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
MINIO_ENDPOINT=host.docker.internal:9000

# Ollama Configuration
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=nomic-embed-text

# Chroma Configuration
CHROMA_PATH=/opt/airflow/chroma_db

# Database Configuration
POSTGRES_USER=airflow
POSTGRES_PASSWORD=airflow
POSTGRES_DB=airflow

# Redis Configuration
REDIS_HOST=redis
REDIS_PORT=6379

# Environment
ENVIRONMENT=development
DEBUG=false
EOF
    echo -e "${GREEN}[✓] .env file created${NC}"
else
    echo -e "${YELLOW}[!] .env file already exists${NC}"
fi

# Make scripts executable
echo -e "${BLUE}[*] Making scripts executable...${NC}"
chmod +x "$PROJECT_DIR"/scripts/*.sh
echo -e "${GREEN}[✓] Scripts are executable${NC}"

# Create directories
echo -e "${BLUE}[*] Creating directories...${NC}"
mkdir -p "$PROJECT_DIR"/{volumes/{postgres_data,chroma_data,minio_data,ollama_data,airflow_logs,airflow_plugins},.logs}
mkdir -p "$PROJECT_DIR"/src/orchestration/{dags,config}
mkdir -p "$PROJECT_DIR"/{tests/{integration,e2e},deployment/{kubernetes,terraform},docs}
echo -e "${GREEN}[✓] Directories created${NC}"

# Create .gitignore entries if needed
if [ ! -f "$PROJECT_DIR/.gitignore" ]; then
    echo -e "${BLUE}[*] Creating .gitignore...${NC}"
    cat > "$PROJECT_DIR/.gitignore" << 'EOF'
# Environment
.env
.env.local
.venv/
venv/

# Docker
volumes/
.docker/

# Logs
.logs/
*.log

# Python
__pycache__/
*.pyc
*.pyo
*.egg-info/
.pytest_cache/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Build
build/
dist/

# Temporary
.tmp/
*.tmp
EOF
    echo -e "${GREEN}[✓] .gitignore created${NC}"
fi

# Copy DAG template if it doesn't exist
if [ ! -f "$PROJECT_DIR/src/orchestration/dags/rag_vector_db_ingestion_dag.py" ]; then
    echo -e "${BLUE}[*] DAG file already exists or will be created${NC}"
fi

echo -e "\n${GREEN}Setup Complete!${NC}"
echo -e "\n${YELLOW}Next Steps:${NC}"
echo -e "  1. Review .env file: ${BLUE}vi .env${NC}"
echo -e "  2. Start services:  ${BLUE}./scripts/start.sh${NC}"
echo -e "  3. Check health:    ${BLUE}./scripts/health-check.sh${NC}"
echo ""

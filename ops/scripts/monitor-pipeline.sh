#!/bin/bash

# Real-time Pipeline Monitoring Script
# Monitors: MinIO uploads → Airflow DAG execution → Chroma vector DB population

cd "/Users/prakashsaini/Documents/Projects/Data Engineer/datalake-project"

# Configuration
AIRFLOW_URL="http://localhost:9093"
AIRFLOW_USER="airflow"
AIRFLOW_PASS="airflow"
DAG_ID="document_rag_ingestion_pipeline"
CHROMA_URL="http://localhost:8001"
MINIO_URL="http://localhost:9000"
MINIO_CONSOLE="http://localhost:9001"
BACKEND_URL="http://localhost:8000"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

clear

echo -e "${CYAN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║        🚀 RAG Pipeline Real-Time Monitoring Dashboard          ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Function to print section headers
print_header() {
    echo -e "${BLUE}▶ $1${NC}"
}

# Function to print success
print_success() {
    echo -e "${GREEN}  ✓ $1${NC}"
}

# Function to print error
print_error() {
    echo -e "${RED}  ✗ $1${NC}"
}

# Function to print info
print_info() {
    echo -e "${YELLOW}  ℹ $1${NC}"
}

# 1. Check MinIO Status
print_header "MinIO Document Storage"
if curl -f -s "$MINIO_URL/minio/health/live" > /dev/null; then
    print_success "MinIO is healthy"
    
    # Count documents in bucket
    DOC_COUNT=$(docker exec minio mc ls minio/documents 2>/dev/null | wc -l)
    if [ "$DOC_COUNT" -gt 0 ]; then
        print_success "Documents in bucket: $((DOC_COUNT - 1))"
    else
        print_error "No documents in MinIO bucket"
    fi
else
    print_error "MinIO is not responding"
fi
echo ""

# 2. Check Infrastructure Services
print_header "Infrastructure Services"

# Ollama
if curl -f -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    print_success "Ollama LLM service is running"
else
    print_error "Ollama LLM service is not responding"
fi

# Chroma
if curl -f -s "$CHROMA_URL/api/v2" > /dev/null 2>&1; then
    print_success "Chroma Vector DB is running"
else
    print_error "Chroma Vector DB is not responding"
fi

# FastAPI Backend
if curl -f -s "$BACKEND_URL/health" > /dev/null 2>&1; then
    print_success "FastAPI Backend is running"
else
    print_error "FastAPI Backend is not responding"
fi
echo ""

# 3. Check Airflow DAG Status
print_header "Airflow DAG Pipeline"

# Get latest DAG run
DAG_RUN=$(curl -s -u "$AIRFLOW_USER:$AIRFLOW_PASS" \
    "$AIRFLOW_URL/api/v1/dags/$DAG_ID/dagRuns?limit=1" \
    -H "Content-Type: application/json")

STATE=$(echo "$DAG_RUN" | grep -o '"state":"[^"]*' | cut -d'"' -f4 | head -1)
EXEC_DATE=$(echo "$DAG_RUN" | grep -o '"execution_date":"[^"]*' | cut -d'"' -f4 | head -1)
START_DATE=$(echo "$DAG_RUN" | grep -o '"start_date":"[^"]*' | cut -d'"' -f4 | head -1)

if [ -n "$STATE" ]; then
    case "$STATE" in
        "success")
            print_success "DAG State: SUCCESS ✨"
            ;;
        "running")
            print_info "DAG State: RUNNING 🔄"
            ;;
        "queued")
            print_info "DAG State: QUEUED ⏳"
            ;;
        "failed")
            print_error "DAG State: FAILED ❌"
            ;;
        *)
            print_info "DAG State: $STATE"
            ;;
    esac
    
    print_info "Execution Date: $EXEC_DATE"
    if [ "$STATE" = "running" ]; then
        print_info "Started: $START_DATE"
    fi
else
    print_error "Could not fetch DAG status"
fi
echo ""

# 4. Get DAG Task Status
print_header "Pipeline Tasks Status"

# Get tasks
TASKS=$(curl -s -u "$AIRFLOW_USER:$AIRFLOW_PASS" \
    "$AIRFLOW_URL/api/v1/dags/$DAG_ID/dagRuns?limit=1" \
    -H "Content-Type: application/json")

# Extract task group info
echo "$TASKS" | grep -o '"task[^"]*"' | head -10 || print_info "No task information available yet"
echo ""

# 5. Check Vector DB Content
print_header "Vector Database (Chroma) Status"

COLLECTIONS=$(curl -s "$CHROMA_URL/api/v2/collections" 2>/dev/null)
if [ -n "$COLLECTIONS" ]; then
    COL_COUNT=$(echo "$COLLECTIONS" | grep -o '"id"' | wc -l)
    print_info "Collections in Chroma: $COL_COUNT"
    echo "$COLLECTIONS" | grep -o '"name":"[^"]*' | cut -d'"' -f4 | while read col; do
        print_success "Collection: $col"
    done
else
    print_info "Chroma is empty or not responding"
fi
echo ""

# 6. System Health Summary
print_header "System Health Summary"
HEALTHY_SERVICES=$(docker compose ps 2>/dev/null | grep "Up.*healthy" | wc -l)
TOTAL_SERVICES=$(docker compose ps 2>/dev/null | grep "Up" | wc -l)

print_info "Healthy Services: $HEALTHY_SERVICES / $TOTAL_SERVICES"

if [ "$HEALTHY_SERVICES" -eq "$TOTAL_SERVICES" ]; then
    print_success "All services are healthy!"
else
    print_error "Some services are unhealthy or starting"
fi
echo ""

# 7. Quick Links
print_header "Quick Access Links"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  MinIO Console:      ${BLUE}${MINIO_CONSOLE}${NC} (minioadmin:minioadmin)"
echo -e "  Airflow Web UI:     ${BLUE}${AIRFLOW_URL}${NC} (airflow:airflow)"
echo -e "  FastAPI Docs:       ${BLUE}${BACKEND_URL}/docs${NC}"
echo -e "  Frontend App:       ${BLUE}http://localhost:3000${NC}"
echo -e "  Chroma API:         ${BLUE}${CHROMA_URL}/api/v2${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# 8. Next Steps Based on DAG State
print_header "Recommended Next Steps"
case "$STATE" in
    "success")
        echo -e "${GREEN}✨ Pipeline execution completed successfully!${NC}"
        echo "1. Check documents in Chroma: $CHROMA_URL/api/v2/collections"
        echo "2. Try searching documents: $BACKEND_URL/docs"
        echo "3. Use frontend to explore results: http://localhost:3000"
        ;;
    "running")
        echo -e "${YELLOW}🔄 Pipeline is currently executing...${NC}"
        echo "1. Monitor task execution in Airflow: $AIRFLOW_URL"
        echo "2. Check logs for each task"
        echo "3. Wait for all tasks to complete"
        ;;
    "queued")
        echo -e "${YELLOW}⏳ Pipeline is queued and waiting to start...${NC}"
        echo "1. Ensure scheduler is running: ./ops/scripts/health-check.sh"
        echo "2. Verify all DAG dependencies are met"
        echo "3. Check for any errors in Airflow logs"
        ;;
    "failed")
        echo -e "${RED}❌ Pipeline execution failed!${NC}"
        echo "1. Check Airflow logs: $AIRFLOW_URL/log"
        echo "2. Review task failures"
        echo "3. Fix issues and trigger again"
        ;;
esac

echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}Dashboard updated: $(date '+%Y-%m-%d %H:%M:%S')${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"

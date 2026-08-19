#!/bin/bash

# ============================================================================
# Airflow ingestion pipeline - startup script
# ============================================================================
# Starts the pipeline and the services it depends on. The desktop application
# does not use any of this; run it with `make desktop`.
# Usage: ./ops/scripts/start.sh [OPTIONS]
# Options:
#   --clean           Clean volumes before startup
#   --detach          Run in background (default)
#   --foreground      Run in foreground
#   --build           Rebuild Docker images
#   --skip-checks     Skip health checks
# ============================================================================

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_FILE="${PROJECT_DIR}/.logs/startup.log"
COMPOSE_DIR="${PROJECT_DIR}/compose"

# The Airflow ingestion pipeline and the services it depends on.
compose() {
    docker compose \
        -f "${COMPOSE_DIR}/compose.yml" \
        -f "${COMPOSE_DIR}/compose.airflow.yml" \
        "$@"
}

# Defaults
CLEAN=false
DETACH="-d"
BUILD=false
SKIP_CHECKS=false

# ============================================================================
# Functions
# ============================================================================

log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}[✓]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[✗]${NC} $1" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}[!]${NC} $1" | tee -a "$LOG_FILE"
}

header() {
    echo -e "\n${BLUE}═══════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}\n"
}

check_requirements() {
    header "Checking Requirements"
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed"
        exit 1
    fi
    success "Docker found: $(docker --version)"
    
    # Check Docker Compose (v2 plugin)
    if ! docker compose version &> /dev/null; then
        error "Docker Compose v2 is not available"
        exit 1
    fi
    success "Docker Compose found: $(docker compose version --short)"
    
    # Check Docker daemon
    if ! docker ps > /dev/null 2>&1; then
        error "Docker daemon is not running"
        exit 1
    fi
    success "Docker daemon is running"
    
    # Check available disk space
    AVAILABLE_SPACE=$(df "$PROJECT_DIR" | awk 'NR==2 {print $4}')
    if [ "$AVAILABLE_SPACE" -lt 5242880 ]; then  # 5GB in KB
        warning "Low disk space available: ${AVAILABLE_SPACE}KB"
    fi
    success "System requirements met"
}

create_directories() {
    header "Creating Required Directories"
    
    mkdir -p "$PROJECT_DIR"/.logs
    mkdir -p "$PROJECT_DIR"/volumes/{postgres_data,chroma_data,minio_data,ollama_data,airflow_logs,airflow_plugins}
    mkdir -p "$PROJECT_DIR"/src/orchestration/{dags,config}
    
    success "Directory structure created"
}

load_env() {
    header "Loading Environment"
    
    if [ -f "$PROJECT_DIR/.env" ]; then
        set -a
        source "$PROJECT_DIR/.env"
        set +a
        success "Environment loaded from .env"
    else
        warning ".env file not found, using defaults"
        export AIRFLOW_UID=${AIRFLOW_UID:-50000}
    fi
    
    log "AIRFLOW_UID: ${AIRFLOW_UID:-50000}"
}

clean_volumes() {
    if [ "$CLEAN" = true ]; then
        header "Cleaning Volumes"
        log "Stopping containers..."
        compose down -v || true
        log "Removing old data..."
        rm -rf "$PROJECT_DIR"/volumes/*
        create_directories
        success "Volumes cleaned"
    fi
}

build_images() {
    if [ "$BUILD" = true ]; then
        header "Building Docker Images"
        compose build
        success "Images built"
    fi
}

start_services() {
    header "Starting Services"
    
    cd "$PROJECT_DIR"
    
    if [ "$DETACH" = "-d" ]; then
        log "Starting services in background..."
        compose up $DETACH
        success "Services started in background"
    else
        log "Starting services in foreground..."
        compose up
    fi
}

wait_for_services() {
    header "Waiting for Services"
    
    local max_attempts=30
    local attempt=1
    
    # Wait for Airflow Webserver
    log "Waiting for Airflow Webserver (port 9093)..."
    while [ $attempt -le $max_attempts ]; do
        if curl -s http://localhost:9093/health > /dev/null 2>&1; then
            success "Airflow Webserver is ready"
            break
        fi
        echo -n "."
        sleep 2
        ((attempt++))
    done
    
    if [ $attempt -gt $max_attempts ]; then
        warning "Airflow Webserver not responding after ${max_attempts}0 seconds"
    fi
    
}

health_check() {
    if [ "$SKIP_CHECKS" = true ]; then
        return
    fi
    
    header "Health Check"
    
    local services=("Airflow" "MinIO" "Ollama" "Chroma" "PostgreSQL" "Redis")
    local endpoints=("localhost:9093" "localhost:9001" "localhost:11434" "localhost:8001" "localhost:5432" "localhost:6379")
    local healthy=0
    
    for i in "${!services[@]}"; do
        service="${services[$i]}"
        endpoint="${endpoints[$i]}"
        
        if timeout 3 bash -c "echo > /dev/tcp/${endpoint%:*}/${endpoint##*:}" 2>/dev/null; then
            success "$service is accessible"
            ((healthy++))
        else
            warning "$service is not responding"
        fi
    done
    
    log "\nServices healthy: ${healthy}/${#services[@]}"
}

print_summary() {
    header "Startup Complete!"
    
    echo -e "${GREEN}Services are running:${NC}\n"
    echo "  Airflow UI:      ${BLUE}http://localhost:9093${NC} (airflow/airflow)"
    echo "  MinIO Console:   ${BLUE}http://localhost:9001${NC} (minioadmin/minioadmin)"
    echo "  Ollama:          ${BLUE}http://localhost:11434${NC}"
    echo "  Chroma:          ${BLUE}http://localhost:8001${NC}"
    echo ""
    
    echo -e "${GREEN}Next Steps:${NC}"
    echo "  1. Access Airflow:  http://localhost:9093"
    echo "  2. Trigger DAG:     document_rag_ingestion_pipeline"
    echo "  3. Upload docs:     Upload files to MinIO console"
    echo "  4. Query docs:      run the desktop app with 'make desktop'"
    echo ""
    
    echo -e "${GREEN}Useful Commands:${NC}"
    echo "  View logs:         ./ops/scripts/health-check.sh"
    echo "  Stop services:     ./ops/scripts/stop.sh"
    echo "  Cleanup:           ./ops/scripts/stop.sh --clean"
    echo ""
}

# ============================================================================
# Parse Arguments
# ============================================================================

while [[ $# -gt 0 ]]; do
    case $1 in
        --clean)
            CLEAN=true
            shift
            ;;
        --foreground)
            DETACH=""
            shift
            ;;
        --build)
            BUILD=true
            shift
            ;;
        --skip-checks)
            SKIP_CHECKS=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--clean] [--foreground] [--build] [--skip-checks]"
            exit 1
            ;;
    esac
done

# ============================================================================
# Main Execution
# ============================================================================

main() {
    log "Starting DataLake RAG System..."
    log "Project Directory: $PROJECT_DIR"
    
    check_requirements
    create_directories
    load_env
    clean_volumes
    build_images
    start_services
    
    if [ "$DETACH" = "-d" ]; then
        sleep 5  # Give services time to start
        wait_for_services
    fi
    
    health_check
    print_summary
}

# Run main function
main

exit 0

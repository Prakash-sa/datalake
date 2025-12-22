#!/bin/bash

# ============================================================================
# DataLake RAG System - Startup Script
# ============================================================================
# Comprehensive startup script with health checks, initialization, and monitoring
# Usage: ./scripts/start.sh [OPTIONS]
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
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="${PROJECT_DIR}/.logs/startup.log"
DOCKER_COMPOSE_FILE="${PROJECT_DIR}/docker-compose.yml"

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
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        error "Docker Compose is not installed"
        exit 1
    fi
    success "Docker Compose found: $(docker-compose --version)"
    
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
        docker-compose -f "$DOCKER_COMPOSE_FILE" down -v || true
        log "Removing old data..."
        rm -rf "$PROJECT_DIR"/volumes/*
        create_directories
        success "Volumes cleaned"
    fi
}

build_images() {
    if [ "$BUILD" = true ]; then
        header "Building Docker Images"
        docker-compose -f "$DOCKER_COMPOSE_FILE" build
        success "Images built"
    fi
}

start_services() {
    header "Starting Services"
    
    cd "$PROJECT_DIR"
    
    if [ "$DETACH" = "-d" ]; then
        log "Starting services in background..."
        docker-compose -f "$DOCKER_COMPOSE_FILE" up $DETACH
        success "Services started in background"
    else
        log "Starting services in foreground..."
        docker-compose -f "$DOCKER_COMPOSE_FILE" up
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
    
    # Wait for RAG Backend
    attempt=1
    log "Waiting for RAG Backend (port 8000)..."
    while [ $attempt -le $max_attempts ]; do
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            success "RAG Backend is ready"
            break
        fi
        echo -n "."
        sleep 2
        ((attempt++))
    done
    
    if [ $attempt -gt $max_attempts ]; then
        warning "RAG Backend not responding after ${max_attempts}0 seconds"
    fi
    
    # Wait for Frontend
    attempt=1
    log "Waiting for Frontend (port 3000)..."
    while [ $attempt -le $max_attempts ]; do
        if curl -s http://localhost:3000 > /dev/null 2>&1; then
            success "Frontend is ready"
            break
        fi
        echo -n "."
        sleep 2
        ((attempt++))
    done
    
    if [ $attempt -gt $max_attempts ]; then
        warning "Frontend not responding after ${max_attempts}0 seconds"
    fi
}

health_check() {
    if [ "$SKIP_CHECKS" = true ]; then
        return
    fi
    
    header "Health Check"
    
    local services=("Airflow" "RAG Backend" "Frontend" "MinIO" "Ollama" "Chroma" "PostgreSQL" "Redis")
    local endpoints=("localhost:9093" "localhost:8000" "localhost:3000" "localhost:9001" "localhost:11434" "localhost:8001" "localhost:5432" "localhost:6379")
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
    echo "  RAG API:         ${BLUE}http://localhost:8000${NC} (Swagger: /docs)"
    echo "  Frontend:        ${BLUE}http://localhost:3000${NC}"
    echo "  MinIO Console:   ${BLUE}http://localhost:9001${NC} (minioadmin/minioadmin)"
    echo "  Ollama:          ${BLUE}http://localhost:11434${NC}"
    echo "  Chroma:          ${BLUE}http://localhost:8001${NC}"
    echo ""
    
    echo -e "${GREEN}Next Steps:${NC}"
    echo "  1. Access Airflow:  http://localhost:9093"
    echo "  2. Trigger DAG:     document_rag_ingestion_pipeline"
    echo "  3. Upload docs:     Upload files to MinIO console"
    echo "  4. Query docs:      http://localhost:3000"
    echo ""
    
    echo -e "${GREEN}Useful Commands:${NC}"
    echo "  View logs:         ./scripts/health-check.sh"
    echo "  Stop services:     ./scripts/stop.sh"
    echo "  Cleanup:           docker-compose down -v"
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

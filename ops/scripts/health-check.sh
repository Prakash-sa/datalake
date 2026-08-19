#!/bin/bash

# ============================================================================
# DataLake RAG System - Health Check Script
# ============================================================================
# Comprehensive health check for all services
# Usage: ./ops/scripts/health-check.sh [OPTIONS]
# Options:
#   --watch      Continuous monitoring (updates every 5s)
#   --verbose    Show detailed logs
# ============================================================================

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
COMPOSE_DIR="${PROJECT_DIR}/compose"

# The Airflow ingestion pipeline and the services it depends on.
compose() {
    docker compose \
        -f "${COMPOSE_DIR}/compose.yml" \
        -f "${COMPOSE_DIR}/compose.airflow.yml" \
        "$@"
}

WATCH=false
VERBOSE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --watch) WATCH=true; shift ;;
        --verbose) VERBOSE=true; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# Service definitions (name, port, endpoint)
declare -a SERVICES=(
    "Airflow Webserver:9093:/health"
    "RAG Backend:8000:/health"
    "Frontend:3000:/"
    "MinIO API:9000:/minio/health/live"
    "MinIO Console:9001:/"
    "Ollama:11434:/api/tags"
    "Chroma:8001:/api/version"
)

check_service() {
    local service_info="$1"
    local name="${service_info%%:*}"
    local port="${service_info%:*}"
    port="${port##*:}"
    local endpoint="${service_info##*:}"
    
    if timeout 3 curl -s "http://localhost:${port}${endpoint}" > /dev/null 2>&1; then
        echo -e "${GREEN}[✓]${NC} $name"
        return 0
    else
        echo -e "${RED}[✗]${NC} $name"
        return 1
    fi
}

check_docker_services() {
    echo -e "${CYAN}Container Status:${NC}\n"
    compose ps
}

check_port_binding() {
    echo -e "\n${CYAN}Port Bindings:${NC}\n"
    compose ps | grep -E "0.0.0.0|PORTS" || true
}

check_disk_usage() {
    echo -e "\n${CYAN}Disk Usage:${NC}\n"
    du -sh "$PROJECT_DIR"/volumes/* 2>/dev/null || echo "No volumes directory"
}

check_logs() {
    if [ "$VERBOSE" = true ]; then
        echo -e "\n${CYAN}Recent Logs:${NC}\n"
        echo -e "${YELLOW}Airflow Scheduler:${NC}"
        compose logs airflow-scheduler --tail=5 2>/dev/null || echo "No logs"
        
        echo -e "\n${YELLOW}RAG Backend:${NC}"
        compose logs airflow-worker --tail=5 2>/dev/null || echo "No logs"
    fi
}

print_header() {
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}DataLake RAG System - Health Check${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}\n"
}

perform_health_check() {
    clear
    print_header
    
    local healthy=0
    local total=${#SERVICES[@]}
    
    echo -e "${CYAN}Service Health:${NC}\n"
    
    for service in "${SERVICES[@]}"; do
        if check_service "$service"; then
            ((healthy++))
        fi
    done
    
    echo -e "\n${CYAN}Summary: ${healthy}/${total} services healthy${NC}\n"
    
    check_docker_services
    check_port_binding
    check_disk_usage
    check_logs
    
    echo ""
}

main() {
    if [ "$WATCH" = true ]; then
        while true; do
            perform_health_check
            sleep 5
        done
    else
        perform_health_check
    fi
}

main

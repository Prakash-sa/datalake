#!/bin/bash

# ============================================================================
# DataLake RAG System - Stop Script
# ============================================================================
# Gracefully stops all services
# Usage: ./ops/scripts/stop.sh [OPTIONS]
# Options:
#   --clean    Remove volumes (data loss!)
#   --force    Force stop without waiting
# ============================================================================

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

CLEAN=false
FORCE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --clean) CLEAN=true; shift ;;
        --force) FORCE="-v"; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}DataLake RAG System - Shutdown${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}\n"

cd "$PROJECT_DIR"

if [ "$CLEAN" = true ]; then
    echo -e "${YELLOW}[!] Stopping and removing volumes...${NC}"
    compose down $FORCE -v
    echo -e "${GREEN}[✓] All services stopped and volumes removed${NC}"
else
    echo -e "${BLUE}[*] Stopping services...${NC}"
    compose down $FORCE
    echo -e "${GREEN}[✓] All services stopped${NC}"
    echo -e "\nData persisted in ./volumes/"
    echo -e "To remove volumes, run: ${YELLOW}./ops/scripts/stop.sh --clean${NC}"
fi

echo ""

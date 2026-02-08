#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== Stopping Kafka Infrastructure ===${NC}"
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Change to script directory
cd "$SCRIPT_DIR"

# Check for --clean flag
CLEAN_FLAG=""
if [ "$1" == "--clean" ]; then
    CLEAN_FLAG="-v"
    echo -e "${YELLOW}Clean mode: Will remove volumes (data will be lost)${NC}"
    echo ""
fi

# Stop services
echo -e "${YELLOW}Stopping Docker Compose services...${NC}"
docker-compose down $CLEAN_FLAG

if [ -n "$CLEAN_FLAG" ]; then
    echo -e "${GREEN}✓ Kafka infrastructure stopped and data volumes removed${NC}"
else
    echo -e "${GREEN}✓ Kafka infrastructure stopped (data preserved)${NC}"
    echo -e "${YELLOW}  To remove data volumes, use: ./kafka-stop.sh --clean${NC}"
fi

echo ""

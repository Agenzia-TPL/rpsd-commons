#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Starting RabbitMQ Infrastructure ===${NC}"
echo ""

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed or not in PATH${NC}"
    echo "Please install Docker first: https://docs.docker.com/get-docker/"
    exit 1
fi

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Change to script directory
cd "$SCRIPT_DIR"

echo -e "${YELLOW}1. Starting Docker Compose services...${NC}"
docker compose up -d

echo ""
echo -e "${YELLOW}2. Waiting for RabbitMQ to be ready...${NC}"

# Wait for RabbitMQ to be healthy
MAX_WAIT=60
WAIT_COUNT=0
while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    HEALTH_STATUS=$(docker inspect --format='{{.State.Health.Status}}' rpsd-rabbitmq 2>/dev/null || echo "unknown")
    if [ "$HEALTH_STATUS" = "healthy" ]; then
        echo -e "${GREEN}✓ RabbitMQ is ready!${NC}"
        break
    fi
    echo -n "."
    sleep 2
    WAIT_COUNT=$((WAIT_COUNT + 2))
done

if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
    echo -e "${RED}✗ RabbitMQ failed to start within ${MAX_WAIT} seconds${NC}"
    echo "Check logs with: docker compose logs rabbitmq"
    exit 1
fi

echo ""
echo -e "${GREEN}=== RabbitMQ Infrastructure Started Successfully ===${NC}"
echo ""
echo -e "${YELLOW}Connection Information:${NC}"
echo -e "  ${GREEN}RabbitMQ Broker (AMQP):${NC}"
echo -e "    From host machine:  ${GREEN}amqp://guest:guest@localhost/${NC}"
echo -e "    From devcontainer:  ${GREEN}amqp://guest:guest@host.docker.internal/${NC}"
echo ""
echo -e "  ${GREEN}Management UI:${NC}  ${GREEN}http://localhost:15672${NC}"
echo -e "    Username: ${GREEN}guest${NC}"
echo -e "    Password: ${GREEN}guest${NC}"
echo ""
echo -e "${YELLOW}Queues:${NC}"
echo -e "  View queues in Management UI: ${GREEN}http://localhost:15672${NC}"
echo -e "  (Queues are auto-created on first publish if using default exchange)"
echo ""
echo -e "${YELLOW}To stop RabbitMQ:${NC} ./stop.sh"
echo ""

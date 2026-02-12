#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Starting Kafka Infrastructure ===${NC}"
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
echo -e "${YELLOW}2. Waiting for Kafka to be ready...${NC}"

# Wait for Kafka to be healthy
MAX_WAIT=60
WAIT_COUNT=0
while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    HEALTH_STATUS=$(docker inspect --format='{{.State.Health.Status}}' rpsd-kafka 2>/dev/null || echo "unknown")
    if [ "$HEALTH_STATUS" = "healthy" ]; then
        echo -e "${GREEN}✓ Kafka is ready!${NC}"
        break
    fi
    echo -n "."
    sleep 2
    WAIT_COUNT=$((WAIT_COUNT + 2))
done

if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
    echo -e "${RED}✗ Kafka failed to start within ${MAX_WAIT} seconds${NC}"
    echo "Check logs with: docker compose logs kafka"
    exit 1
fi

echo ""
echo -e "${YELLOW}3. Creating default topics...${NC}"

# Create enriched-events topic
# Note: Auto-create is enabled, so topics will be created on first use
# This step pre-creates topics with specific configuration
docker exec rpsd-kafka /opt/kafka/bin/kafka-topics.sh \
    --bootstrap-server localhost:9092 \
    --create \
    --if-not-exists \
    --topic enriched-events \
    --partitions 3 \
    --replication-factor 1 \
    --config retention.ms=604800000 2>/dev/null && \
    echo -e "${GREEN}✓ Created topic: enriched-events${NC}" || \
    echo -e "${YELLOW}  Topic will be auto-created on first use${NC}"

echo ""
echo -e "${GREEN}=== Kafka Infrastructure Started Successfully ===${NC}"
echo ""
echo -e "${YELLOW}Connection Information:${NC}"
echo -e "  ${GREEN}Kafka Broker:${NC}"
echo -e "    From host machine:  ${GREEN}localhost:9092${NC}"
echo -e "    From devcontainer:  ${GREEN}host.docker.internal:9092${NC}"
echo ""
echo -e "  ${GREEN}Kafka UI:${NC}         ${GREEN}http://localhost:8080${NC}"
echo -e "  ${GREEN}Schema Registry:${NC}  ${GREEN}http://localhost:8081${NC}"
echo ""
echo -e "${YELLOW}Topics:${NC}"
echo -e "  View topics in Kafka UI: ${GREEN}http://localhost:8080${NC}"
echo -e "  (Topics are auto-created on first publish)"
echo ""
echo -e "${YELLOW}To stop Kafka:${NC} ./stop.sh"
echo ""

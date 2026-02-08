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
docker-compose up -d

echo ""
echo -e "${YELLOW}2. Waiting for Kafka to be ready...${NC}"

# Wait for Kafka to be healthy
MAX_WAIT=60
WAIT_COUNT=0
while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    if docker exec rpsd-kafka kafka-broker-api-versions.sh --bootstrap-server localhost:9092 &> /dev/null; then
        echo -e "${GREEN}✓ Kafka is ready!${NC}"
        break
    fi
    echo -n "."
    sleep 2
    WAIT_COUNT=$((WAIT_COUNT + 2))
done

if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
    echo -e "${RED}✗ Kafka failed to start within ${MAX_WAIT} seconds${NC}"
    echo "Check logs with: docker-compose logs kafka"
    exit 1
fi

echo ""
echo -e "${YELLOW}3. Creating default topics...${NC}"

# Create enriched-events topic
docker exec rpsd-kafka kafka-topics.sh \
    --bootstrap-server localhost:9092 \
    --create \
    --if-not-exists \
    --topic enriched-events \
    --partitions 3 \
    --replication-factor 1 \
    --config retention.ms=604800000 && \
    echo -e "${GREEN}✓ Created topic: enriched-events${NC}" || \
    echo -e "${YELLOW}  Topic enriched-events already exists${NC}"

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
echo -e "${YELLOW}Available Topics:${NC}"
docker exec rpsd-kafka kafka-topics.sh --bootstrap-server localhost:9092 --list | while read -r topic; do
    echo -e "  - $topic"
done
echo ""
echo -e "${YELLOW}To stop Kafka:${NC} ./kafka-stop.sh"
echo ""

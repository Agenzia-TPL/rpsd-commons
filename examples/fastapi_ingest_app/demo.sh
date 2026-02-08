#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}   FastAPI Ingest App - End-to-End Demo${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ] || [ ! -d "src/fastapi_ingest_app" ]; then
    echo -e "${RED}Error: Must be run from examples/fastapi_ingest_app directory${NC}"
    exit 1
fi

# Check if Kafka is running (test connection to host.docker.internal:9092)
echo -e "${YELLOW}Step 1: Checking Kafka availability...${NC}"
if ! python3 -c "import socket; s = socket.socket(); s.settimeout(2); s.connect(('host.docker.internal', 9092)); s.close()" 2>/dev/null; then
    echo -e "${RED}✗ Kafka is not running!${NC}"
    echo ""
    echo -e "${YELLOW}Please start Kafka from the host machine:${NC}"
    echo -e "  cd ../../host-scripts"
    echo -e "  ./kafka-start.sh"
    echo ""
    echo -e "${YELLOW}Or run this demo without Kafka forwarding:${NC}"
    echo -e "  Unset APP__FORWARD__CARRIER in your .env file"
    echo ""
    exit 1
fi
echo -e "${GREEN}✓ Kafka is running${NC}"
echo ""

# Load environment and ensure demo defaults
echo -e "${YELLOW}Step 2: Setting up configuration...${NC}"

# Load existing .env if present
if [ -f ".env" ]; then
    set -a  # automatically export all variables
    source .env
    set +a
    echo -e "${GREEN}✓ Loaded existing .env${NC}"
fi

# Set defaults for required demo variables (if not already set)
export APP__TRANSPORT__API_KEY="${APP__TRANSPORT__API_KEY:-demo-key-12345}"
export APP__STORAGE__PROVIDER="${APP__STORAGE__PROVIDER:-fs}"
export APP__STORAGE__FS__BASE_PATH="${APP__STORAGE__FS__BASE_PATH:-/tmp/rpsd-storage}"
export APP__FORWARD__CARRIER="${APP__FORWARD__CARRIER:-kafka}"
export APP__FORWARD__RECIPIENT="${APP__FORWARD__RECIPIENT:-enriched-events}"
export APP__FORWARD__MODE="${APP__FORWARD__MODE:-fatheavy}"
export APP__FORWARD__KAFKA__BOOTSTRAP_SERVERS="${APP__FORWARD__KAFKA__BOOTSTRAP_SERVERS:-host.docker.internal:9092}"

# Backup existing .env and write complete config for demo
if [ -f ".env" ]; then
    cp .env .env.backup
fi

cat > .env <<EOF
APP__TRANSPORT__API_KEY=${APP__TRANSPORT__API_KEY}
APP__STORAGE__PROVIDER=${APP__STORAGE__PROVIDER}
APP__STORAGE__FS__BASE_PATH=${APP__STORAGE__FS__BASE_PATH}
APP__FORWARD__CARRIER=${APP__FORWARD__CARRIER}
APP__FORWARD__RECIPIENT=${APP__FORWARD__RECIPIENT}
APP__FORWARD__MODE=${APP__FORWARD__MODE}
APP__FORWARD__KAFKA__BOOTSTRAP_SERVERS=${APP__FORWARD__KAFKA__BOOTSTRAP_SERVERS}
EOF

echo -e "${GREEN}✓ Demo configuration ready${NC}"
echo ""

# Start FastAPI app in background
echo -e "${YELLOW}Step 3: Starting FastAPI application...${NC}"
uv run uvicorn fastapi_ingest_app.main:app --host 0.0.0.0 --port 8000 > /tmp/fastapi-ingest-app.log 2>&1 &
FASTAPI_PID=$!
sleep 3

# Check if app started successfully
if ! kill -0 $FASTAPI_PID 2>/dev/null; then
    echo -e "${RED}✗ FastAPI failed to start${NC}"
    cat /tmp/fastapi-ingest-app.log
    exit 1
fi
echo -e "${GREEN}✓ FastAPI running (PID: $FASTAPI_PID)${NC}"
echo ""

# Start Kafka consumer in background
echo -e "${YELLOW}Step 4: Starting Kafka consumer...${NC}"
uv run python -m fastapi_ingest_app.consumer > /tmp/kafka-consumer.log 2>&1 &
CONSUMER_PID=$!
sleep 2

if ! kill -0 $CONSUMER_PID 2>/dev/null; then
    echo -e "${RED}✗ Kafka consumer failed to start${NC}"
    cat /tmp/kafka-consumer.log
    kill $FASTAPI_PID 2>/dev/null || true
    exit 1
fi
echo -e "${GREEN}✓ Kafka consumer running (PID: $CONSUMER_PID)${NC}"
echo ""

# Send test requests
echo -e "${YELLOW}Step 5: Sending test requests...${NC}"
echo ""

# Test 1: Slimfast message
echo -e "${BLUE}Test 1: Slimfast message (content inline)${NC}"
RESPONSE=$(curl -s -X POST "http://localhost:8000/ingest" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${APP__TRANSPORT__API_KEY:-demo-key-12345}" \
  -d '{
    "metadata": {
      "who": "demo-user",
      "what": "test-report",
      "content_type": "text/plain",
      "filename": "test.txt"
    },
    "content": "SGVsbG8sIEthZmthIVRoaXMgaXMgYSB0ZXN0IG1lc3NhZ2Uu"
  }')

echo "$RESPONSE" | python3 -m json.tool
FORWARDED=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('forwarded', False))")
if [ "$FORWARDED" = "True" ]; then
    echo -e "${GREEN}✓ Message forwarded to Kafka${NC}"
else
    echo -e "${YELLOW}⚠ Message not forwarded (forwarding may be disabled)${NC}"
fi
echo ""

sleep 2

# Test 2: Fatheavy message
echo -e "${BLUE}Test 2: Fatheavy message (content by URL reference)${NC}"
RESPONSE=$(curl -s -X POST "http://localhost:8000/ingest" \
  -H "X-RPSD-Who: demo-user" \
  -H "X-RPSD-What: large-file" \
  -H "X-RPSD-Where: https://httpbin.org/base64/SGVsbG8gV29ybGQh" \
  -H "X-RPSD-Content-Type: text/plain" \
  -H "Authorization: Bearer ${APP__TRANSPORT__API_KEY:-demo-key-12345}" \
  -d "This is the request body that will be saved")

echo "$RESPONSE" | python3 -m json.tool
FORWARDED=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('forwarded', False))")
if [ "$FORWARDED" = "True" ]; then
    echo -e "${GREEN}✓ Message forwarded to Kafka${NC}"
else
    echo -e "${YELLOW}⚠ Message not forwarded (forwarding may be disabled)${NC}"
fi
echo ""

sleep 2

# Show results
echo -e "${YELLOW}Step 6: Verification${NC}"
echo ""

echo -e "${BLUE}Storage contents:${NC}"
ls -lah "${APP__STORAGE__FS__BASE_PATH:-/tmp/rpsd-storage}/demo-user/" 2>/dev/null || echo "  (No files created yet)"
echo ""

echo -e "${BLUE}Consumer log (last 10 lines):${NC}"
tail -10 /tmp/kafka-consumer.log 2>/dev/null || echo "  (No consumer log)"
echo ""

# Provide access information
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}   Demo Running - Access Points${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo -e "${GREEN}FastAPI App:${NC}      http://localhost:8000"
echo -e "${GREEN}Health Check:${NC}     http://localhost:8000/health"
echo -e "${GREEN}Kafka UI:${NC}         http://localhost:8080"
echo -e "${GREEN}Schema Registry:${NC}  http://localhost:8081"
echo ""
echo -e "${YELLOW}Logs:${NC}"
echo -e "  FastAPI:  tail -f /tmp/fastapi-ingest-app.log"
echo -e "  Consumer: tail -f /tmp/kafka-consumer.log"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop demo and cleanup...${NC}"
echo ""

# Trap Ctrl+C to cleanup
cleanup() {
    echo ''
    echo -e "${YELLOW}Stopping services...${NC}"
    kill $FASTAPI_PID $CONSUMER_PID 2>/dev/null || true

    # Restore original .env
    if [ -f ".env.backup" ]; then
        mv .env.backup .env
        echo -e "${GREEN}✓ Restored original .env${NC}"
    fi

    echo -e "${GREEN}✓ Demo stopped${NC}"
    exit 0
}

trap cleanup INT

# Wait for user interrupt
wait

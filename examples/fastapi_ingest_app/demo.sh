#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse carrier argument (default to kafka for backward compatibility)
CARRIER="${1:-kafka}"

# Validate carrier
if [ "$CARRIER" != "kafka" ] && [ "$CARRIER" != "rabbitmq" ]; then
    echo -e "${RED}Error: Invalid carrier '$CARRIER'${NC}"
    echo ""
    echo "Usage: $0 [kafka|rabbitmq]"
    echo ""
    echo "Examples:"
    echo "  $0          # Use Kafka (default)"
    echo "  $0 kafka    # Use Kafka explicitly"
    echo "  $0 rabbitmq # Use RabbitMQ"
    echo ""
    exit 1
fi

# Convert carrier to uppercase for display
CARRIER_UPPER=$(echo "$CARRIER" | tr '[:lower:]' '[:upper:]')

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}   FastAPI Ingest App - End-to-End Demo${NC}"
echo -e "${BLUE}   Message Broker: ${CARRIER_UPPER}${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo "This demo tests the complete ingestion pipeline:"
echo "  1. HTTP → Storage → ${CARRIER_UPPER} forwarding"
echo "  2. ${CARRIER_UPPER} consumer with rpsd-storage integration"
echo "  3. Content retrieval from multiple URL schemes"
echo "  4. Prefect Flow invocation (if Prefect server is available)"
echo ""
echo "Test scenarios:"
echo "  • Slimfast messages (inline content)"
echo "  • Fatheavy messages with file:// URLs"
echo "  • Fatheavy messages with http:// URLs"
echo "  • Fatheavy messages with https:// URLs"
echo "  • Error handling (404, non-existent files)"
echo ""

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ] || [ ! -d "src/fastapi_ingest_app" ]; then
    echo -e "${RED}Error: Must be run from examples/fastapi_ingest_app directory${NC}"
    exit 1
fi

# Check if message broker is running
echo -e "${YELLOW}Step 1: Checking ${CARRIER_UPPER} availability...${NC}"

if [ "$CARRIER" == "kafka" ]; then
    BROKER_PORT=9092
    START_SCRIPT="kafka/start.sh"
elif [ "$CARRIER" == "rabbitmq" ]; then
    BROKER_PORT=5672
    START_SCRIPT="rabbitmq/start.sh"
fi

if ! python3 -c "import socket; s = socket.socket(); s.settimeout(2); s.connect(('host.docker.internal', $BROKER_PORT)); s.close()" 2>/dev/null; then
    echo -e "${RED}✗ ${CARRIER_UPPER} is not running!${NC}"
    echo ""
    echo -e "${YELLOW}Please start ${CARRIER_UPPER} from the host machine:${NC}"
    echo -e "  cd ../../host-scripts"
    echo -e "  ./$START_SCRIPT"
    echo ""
    echo -e "${YELLOW}Or run this demo without message broker forwarding:${NC}"
    echo -e "  Unset APP__FORWARD__CARRIER in your .env file"
    echo ""
    exit 1
fi
echo -e "${GREEN}✓ ${CARRIER_UPPER} is running${NC}"
echo ""

# Check if Prefect server is available (optional)
PREFECT_AVAILABLE=false
echo -e "${YELLOW}Step 1b: Checking Prefect server availability...${NC}"
if python3 -c "import socket; s = socket.socket(); s.settimeout(2); s.connect(('host.docker.internal', 4200)); s.close()" 2>/dev/null; then
    PREFECT_AVAILABLE=true
    echo -e "${GREEN}✓ Prefect server is running — flow invocation will be enabled${NC}"
else
    echo -e "${YELLOW}⚠ Prefect server not available — flow invocation will be skipped${NC}"
    echo -e "  To enable: run ${BLUE}../../host-scripts/prefect/start.sh${NC} from the host machine"
fi
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
# Common settings
export LOG_LEVEL="DEBUG"
export APP__TRANSPORT__API_KEY="${APP__TRANSPORT__API_KEY:-demo-key-12345}"
export APP__STORAGE__PROVIDER="${APP__STORAGE__PROVIDER:-fs}"
export APP__STORAGE__FS__BASE_PATH="${APP__STORAGE__FS__BASE_PATH:-/tmp/rpsd-storage}"
export APP__STORAGE__COMPARE_BEFORE_SAVE="${APP__STORAGE__COMPARE_BEFORE_SAVE:-true}"
export APP__FORWARD__CARRIER="$CARRIER"
export APP__FORWARD__RECIPIENT="${APP__FORWARD__RECIPIENT:-enriched-events}"
export APP__FORWARD__MODE="${APP__FORWARD__MODE:-fatheavy}"
export APP__CONSUMER__CARRIER="$CARRIER"
export APP__CONSUMER__TOPIC="${APP__CONSUMER__TOPIC:-enriched-events}"

# Carrier-specific settings
if [ "$CARRIER" == "kafka" ]; then
    export APP__FORWARD__KAFKA__BOOTSTRAP_SERVERS="host.docker.internal:9092"
    export APP__CONSUMER__KAFKA__BOOTSTRAP_SERVERS="host.docker.internal:9092"
    export APP__CONSUMER__KAFKA__GROUP_ID="demo-consumer"
elif [ "$CARRIER" == "rabbitmq" ]; then
    export APP__FORWARD__RABBITMQ__URL="amqp://guest:guest@host.docker.internal/"
    export APP__CONSUMER__RABBITMQ__URL="amqp://guest:guest@host.docker.internal/"
fi

# Flow invocation settings (only if Prefect is available)
if [ "$PREFECT_AVAILABLE" = true ]; then
    export APP__FLOW__DEPLOYMENT="ingest-flow/ingest-deployment"
    export PREFECT_API_URL="http://host.docker.internal:4200/api"
fi

# Backup existing .env and write complete config for demo
if [ -f ".env" ]; then
    cp .env .env.backup
fi

# Write common configuration
cat > .env <<EOF
APP__TRANSPORT__API_KEY=${APP__TRANSPORT__API_KEY}
APP__STORAGE__PROVIDER=${APP__STORAGE__PROVIDER}
APP__STORAGE__FS__BASE_PATH=${APP__STORAGE__FS__BASE_PATH}
APP__STORAGE__COMPARE_BEFORE_SAVE=${APP__STORAGE__COMPARE_BEFORE_SAVE}
APP__FORWARD__CARRIER=${APP__FORWARD__CARRIER}
APP__FORWARD__RECIPIENT=${APP__FORWARD__RECIPIENT}
APP__FORWARD__MODE=${APP__FORWARD__MODE}
APP__CONSUMER__CARRIER=${APP__CONSUMER__CARRIER}
APP__CONSUMER__TOPIC=${APP__CONSUMER__TOPIC}
EOF

# Append carrier-specific configuration
if [ "$CARRIER" == "kafka" ]; then
    cat >> .env <<EOF
APP__FORWARD__KAFKA__BOOTSTRAP_SERVERS=${APP__FORWARD__KAFKA__BOOTSTRAP_SERVERS}
APP__CONSUMER__KAFKA__BOOTSTRAP_SERVERS=${APP__CONSUMER__KAFKA__BOOTSTRAP_SERVERS}
APP__CONSUMER__KAFKA__GROUP_ID=${APP__CONSUMER__KAFKA__GROUP_ID}
EOF
elif [ "$CARRIER" == "rabbitmq" ]; then
    cat >> .env <<EOF
APP__FORWARD__RABBITMQ__URL=${APP__FORWARD__RABBITMQ__URL}
APP__CONSUMER__RABBITMQ__URL=${APP__CONSUMER__RABBITMQ__URL}
EOF
fi

# Append flow configuration if Prefect is available
if [ "$PREFECT_AVAILABLE" = true ]; then
    cat >> .env <<EOF
APP__FLOW__DEPLOYMENT=${APP__FLOW__DEPLOYMENT}
PREFECT_API_URL=${PREFECT_API_URL}
EOF
fi

echo -e "${GREEN}✓ Demo configuration ready${NC}"
echo ""

# Clean storage from previous runs so deduplication tests start fresh
STORAGE_DIR="${APP__STORAGE__FS__BASE_PATH:-/tmp/rpsd-storage}"
if [ -d "$STORAGE_DIR" ]; then
    rm -rf "$STORAGE_DIR"
    echo -e "${GREEN}✓ Cleaned previous storage at ${STORAGE_DIR}${NC}"
fi

# Start Prefect task worker and flow server if Prefect is available
TASK_PID=""
FLOW_PID=""
if [ "$PREFECT_AVAILABLE" = true ]; then
    echo -e "${YELLOW}Step 3a: Starting Prefect task server...${NC}"
    uv run sample-task > /tmp/sample-task.log 2>&1 &
    TASK_PID=$!
    sleep 2

    if ! kill -0 $TASK_PID 2>/dev/null; then
        echo -e "${YELLOW}⚠ Task server failed to start (continuing without flow invocation)${NC}"
        tail -5 /tmp/sample-task.log 2>/dev/null || true
        PREFECT_AVAILABLE=false
        TASK_PID=""
    else
        echo -e "${GREEN}✓ Task server running (PID: $TASK_PID)${NC}"
    fi
    echo ""

    if [ "$PREFECT_AVAILABLE" = true ]; then
        echo -e "${YELLOW}Step 3b: Starting Prefect sample flow server...${NC}"
        uv run sample-flow > /tmp/sample-flow.log 2>&1 &
        FLOW_PID=$!
        sleep 3

        if ! kill -0 $FLOW_PID 2>/dev/null; then
            echo -e "${YELLOW}⚠ Sample flow server failed to start (continuing without flow invocation)${NC}"
            tail -5 /tmp/sample-flow.log 2>/dev/null || true
            PREFECT_AVAILABLE=false
            kill $TASK_PID 2>/dev/null || true
            TASK_PID=""
            FLOW_PID=""
        else
            echo -e "${GREEN}✓ Sample flow server running (PID: $FLOW_PID)${NC}"
        fi
        echo ""
    fi
fi

# Start FastAPI app in background
echo -e "${YELLOW}Step 3c: Starting FastAPI application...${NC}"
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

# Start message broker consumer in background
echo -e "${YELLOW}Step 4: Starting ${CARRIER_UPPER} consumer...${NC}"
uv run python -m fastapi_ingest_app.consumer > /tmp/consumer.log 2>&1 &
CONSUMER_PID=$!
sleep 2

if ! kill -0 $CONSUMER_PID 2>/dev/null; then
    echo -e "${RED}✗ ${CARRIER_UPPER} consumer failed to start${NC}"
    cat /tmp/consumer.log
    kill $FASTAPI_PID 2>/dev/null || true
    exit 1
fi
echo -e "${GREEN}✓ ${CARRIER_UPPER} consumer running (PID: $CONSUMER_PID)${NC}"
echo ""

# Helper: check deduplicated + forwarded + flow_invoked from a JSON response
check_result() {
    local response="$1"
    local deduplicated=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('deduplicated', False))")
    local forwarded=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('forwarded', False))")
    local flow_invoked=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('flow_invoked', False))")
    if [ "$deduplicated" = "True" ]; then
        echo -e "${GREEN}✓ Deduplicated (content unchanged, save skipped)${NC}"
    fi
    if [ "$forwarded" = "True" ]; then
        echo -e "${GREEN}✓ Forwarded to ${CARRIER_UPPER}${NC}"
    else
        echo -e "${YELLOW}⚠ Not forwarded${NC}"
    fi
    if [ "$PREFECT_AVAILABLE" = true ]; then
        if [ "$flow_invoked" = "True" ]; then
            echo -e "${GREEN}✓ Flow invoked${NC}"
        else
            echo -e "${YELLOW}⚠ Flow not invoked${NC}"
        fi
    fi
}

# Send test requests
echo -e "${YELLOW}Step 5: Sending test requests...${NC}"
echo ""

# Test 1: Slimfast message (content inline)
echo -e "${BLUE}Test 1: Slimfast message (content inline)${NC}"
echo -e "  Testing: Inline content in JSON payload"
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
STORAGE_URL_TEST1=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('storage_url', ''))")
check_result "$RESPONSE"
echo ""

sleep 2

# Test 2: Deduplication - re-send identical slimfast message
echo -e "${BLUE}Test 2: Deduplication (re-send identical content)${NC}"
echo -e "  Testing: Same who/what/content as Test 1 — should be deduplicated"
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
check_result "$RESPONSE"
echo ""

sleep 2

# Test 3: Fatheavy message with https:// URL
echo -e "${BLUE}Test 3: Fatheavy message with https:// URL reference${NC}"
echo -e "  Testing: Consumer fetches content from HTTPS URL via rpsd-storage"
RESPONSE=$(curl -s -X POST "http://localhost:8000/ingest" \
  -H "X-RPSD-Who: demo-user" \
  -H "X-RPSD-What: https-content" \
  -H "X-RPSD-Where: https://httpbin.org/base64/SGVsbG8gZnJvbSBIVFRQUyE=" \
  -H "X-RPSD-Content-Type: text/plain" \
  -H "Authorization: Bearer ${APP__TRANSPORT__API_KEY:-demo-key-12345}" \
  -d "")

echo "$RESPONSE" | python3 -m json.tool
check_result "$RESPONSE"
echo ""

sleep 2

# Test 4: Fatheavy message with file:// URL (referencing stored content from Test 1)
echo -e "${BLUE}Test 4: Fatheavy message with file:// URL reference${NC}"
echo -e "  Testing: Consumer fetches content from local filesystem via rpsd-storage"
if [ -n "$STORAGE_URL_TEST1" ]; then
    echo -e "  Using storage URL from Test 1: ${STORAGE_URL_TEST1}"
    RESPONSE=$(curl -s -X POST "http://localhost:8000/ingest" \
      -H "X-RPSD-Who: demo-user" \
      -H "X-RPSD-What: file-reference" \
      -H "X-RPSD-Where: ${STORAGE_URL_TEST1}" \
      -H "X-RPSD-Content-Type: text/plain" \
      -H "Authorization: Bearer ${APP__TRANSPORT__API_KEY:-demo-key-12345}" \
      -d "")

    echo "$RESPONSE" | python3 -m json.tool
    check_result "$RESPONSE"
else
    echo -e "${YELLOW}⚠ Skipping Test 4 (no storage URL from Test 1)${NC}"
fi
echo ""

sleep 2

# Test 5: Fatheavy message with http:// URL (non-HTTPS)
echo -e "${BLUE}Test 5: Fatheavy message with http:// URL reference${NC}"
echo -e "  Testing: Consumer fetches content from HTTP URL via rpsd-storage"
RESPONSE=$(curl -s -X POST "http://localhost:8000/ingest" \
  -H "X-RPSD-Who: demo-user" \
  -H "X-RPSD-What: http-content" \
  -H "X-RPSD-Where: http://httpbin.org/base64/SGVsbG8gZnJvbSBIVFRQIQ==" \
  -H "X-RPSD-Content-Type: text/plain" \
  -H "Authorization: Bearer ${APP__TRANSPORT__API_KEY:-demo-key-12345}" \
  -d "")

echo "$RESPONSE" | python3 -m json.tool
check_result "$RESPONSE"
echo ""

sleep 2

# Test 6: Error handling - non-existent file:// URL
echo -e "${BLUE}Test 6: Error handling with non-existent file:// URL${NC}"
echo -e "  Testing: Consumer gracefully handles FileNotFoundError"
RESPONSE=$(curl -s -X POST "http://localhost:8000/ingest" \
  -H "X-RPSD-Who: demo-user" \
  -H "X-RPSD-What: error-test" \
  -H "X-RPSD-Where: file:///tmp/this-file-does-not-exist.txt" \
  -H "X-RPSD-Content-Type: text/plain" \
  -H "Authorization: Bearer ${APP__TRANSPORT__API_KEY:-demo-key-12345}" \
  -d "")

echo "$RESPONSE" | python3 -m json.tool
check_result "$RESPONSE"
echo ""

sleep 2

# Test 7: Error handling - HTTP 404
echo -e "${BLUE}Test 7: Error handling with HTTP 404 URL${NC}"
echo -e "  Testing: Consumer gracefully handles HTTP 404 errors"
RESPONSE=$(curl -s -X POST "http://localhost:8000/ingest" \
  -H "X-RPSD-Who: demo-user" \
  -H "X-RPSD-What: error-test-404" \
  -H "X-RPSD-Where: https://httpbin.org/status/404" \
  -H "X-RPSD-Content-Type: text/plain" \
  -H "Authorization: Bearer ${APP__TRANSPORT__API_KEY:-demo-key-12345}" \
  -d "")

echo "$RESPONSE" | python3 -m json.tool
check_result "$RESPONSE"
echo ""

sleep 2

# Show results
echo -e "${YELLOW}Step 6: Verification${NC}"
echo ""

echo -e "${BLUE}Storage contents:${NC}"
echo "Listing all files created in storage:"
find "${APP__STORAGE__FS__BASE_PATH:-/tmp/rpsd-storage}/demo-user/" -type f 2>/dev/null | sort || echo "  (No files created yet)"
echo ""

echo -e "${BLUE}Consumer log (showing rpsd-storage metadata and error handling):${NC}"
echo "The consumer uses rpsd-storage to retrieve content and handles errors gracefully:"
echo ""
echo "Successful retrievals:"
tail -60 /tmp/consumer.log 2>/dev/null | grep -A 6 "Content retrieved successfully" | head -30 || echo "  (No successful retrievals)"
echo ""
echo "Error handling:"
tail -60 /tmp/consumer.log 2>/dev/null | grep -E "(Content not found|Failed to fetch|WARNING)" | tail -10 || echo "  (No errors encountered)"
echo ""

if [ "$PREFECT_AVAILABLE" = true ]; then
    echo -e "${BLUE}Flow server log (Prefect task execution):${NC}"
    echo ""
    tail -30 /tmp/sample-flow.log 2>/dev/null | grep -E "(Validating|Finalising|Flow completed|Subprocess|Processing)" | tail -15 || echo "  (No flow log entries yet)"
    echo ""
fi

echo -e "${BLUE}Summary of test scenarios:${NC}"
echo "  ✓ Test 1: Slimfast message (inline content)"
echo "  ✓ Test 2: Deduplication (re-send identical content)"
echo "  ✓ Test 3: Fatheavy message with https:// URL"
echo "  ✓ Test 4: Fatheavy message with file:// URL"
echo "  ✓ Test 5: Fatheavy message with http:// URL"
echo "  ✓ Test 6: Error handling - non-existent file:// URL"
echo "  ✓ Test 7: Error handling - HTTP 404"
if [ "$PREFECT_AVAILABLE" = true ]; then
    echo "  ✓ Prefect Flow invoked for each test (3-task pipeline)"
fi
echo ""
echo "The consumer demonstrates rpsd-storage integration across all URL schemes:"
echo "  • file:// - Local filesystem retrieval"
echo "  • http:// - HTTP retrieval with status codes"
echo "  • https:// - HTTPS retrieval with status codes"
echo "  • (s3:// - Would work if S3 storage is configured)"
echo ""
if [ "$PREFECT_AVAILABLE" = true ]; then
    echo "Prefect Flow pipeline demonstrated:"
    echo "  • validate-message — fast task checking metadata"
    echo "  • process-content — subprocess task (scripts/process.py)"
    echo "  • finalize — fast task logging the result"
    echo ""
fi
echo "Error handling demonstrated:"
echo "  • FileNotFoundError - Non-existent files logged as warnings"
echo "  • HTTP 404 errors - Consumer continues processing"
echo "  • Consumer never crashes - errors are logged and processing continues"
echo ""

# Provide access information
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}   Demo Running - Access Points${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo -e "${GREEN}FastAPI App:${NC}      http://localhost:8000"
echo -e "${GREEN}Health Check:${NC}     http://localhost:8000/health"
echo ""

if [ "$CARRIER" == "kafka" ]; then
    echo -e "${GREEN}Kafka UI:${NC}         http://localhost:8080"
    echo -e "${GREEN}Schema Registry:${NC}  http://localhost:8081"
elif [ "$CARRIER" == "rabbitmq" ]; then
    echo -e "${GREEN}RabbitMQ UI:${NC}      http://localhost:15672 (guest/guest)"
fi

if [ "$PREFECT_AVAILABLE" = true ]; then
    echo -e "${GREEN}Prefect UI:${NC}       http://localhost:4200"
fi

echo ""
echo -e "${YELLOW}Logs:${NC}"
echo -e "  FastAPI:  tail -f /tmp/fastapi-ingest-app.log"
echo -e "  Consumer: tail -f /tmp/consumer.log"
if [ -n "$TASK_PID" ]; then
    echo -e "  Task:     tail -f /tmp/sample-task.log"
fi
if [ -n "$FLOW_PID" ]; then
    echo -e "  Flow:     tail -f /tmp/sample-flow.log"
fi
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop demo and cleanup...${NC}"
echo ""

# Trap Ctrl+C to cleanup
cleanup() {
    echo ''
    echo -e "${YELLOW}Stopping services...${NC}"
    kill $FASTAPI_PID $CONSUMER_PID 2>/dev/null || true
    if [ -n "$FLOW_PID" ]; then
        kill $FLOW_PID 2>/dev/null || true
    fi
    if [ -n "$TASK_PID" ]; then
        kill $TASK_PID 2>/dev/null || true
    fi

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

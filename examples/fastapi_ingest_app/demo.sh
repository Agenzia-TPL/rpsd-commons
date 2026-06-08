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
echo "  • Deduplication (what=daily-report → compare_before_save=True)"
echo "  • Force-save audit log (what=audit-log → compare_before_save=False)"
echo "  • Fatheavy messages with file:// URLs"
echo "  • Fatheavy messages with http:// URLs"
echo "  • Fatheavy messages with https:// URLs"
echo "  • Error handling (404, non-existent files)"
echo "  • Fire-and-forget flow result retrieval (GET /flow/{id})"
echo "  • Composite flow with a subflow (validate-flow inside parent, flat response)"
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
    # Keep the default fire-and-forget timeout (APP__FLOW__TIMEOUT=0) so we
    # can demonstrate retrieving the result later via GET /flow/{id}. The
    # simulated processing time is tunable (seconds); a few seconds keeps the
    # demo snappy while still making the pending → completed transition
    # observable when we poll.
    export RPSD_PROCESS_SLEEP="${RPSD_PROCESS_SLEEP:-5}"
    # Where process.py records its streaming-read summary. The task server
    # inherits this env, so the process-content subprocess writes here; the
    # final report tails it to show open_content actually ran. Deployment
    # subprocess logs don't reach the served-flow log, hence this side channel.
    export RPSD_STREAM_LOG="${RPSD_STREAM_LOG:-/tmp/rpsd-stream.log}"
    : > "$RPSD_STREAM_LOG"
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
VALIDATE_PID=""
INGEST_PID=""
COMPOSITE_AVAILABLE=false
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

    # Composite (subflow) demo: serve the validator and the parent on SEPARATE
    # processes / work pools. A blocking parent (timeout=None on the subflow)
    # holds a concurrency slot for the child's whole duration, so sharing one
    # pool risks slot-starvation/deadlock — separate servers keep their
    # concurrency budgets independent.
    if [ "$PREFECT_AVAILABLE" = true ]; then
        echo -e "${YELLOW}Step 3b2: Starting composite flow servers (separate pools)...${NC}"
        uv run serve-validate > /tmp/serve-validate.log 2>&1 &
        VALIDATE_PID=$!
        uv run serve-ingest > /tmp/serve-ingest.log 2>&1 &
        INGEST_PID=$!
        sleep 3

        if kill -0 $VALIDATE_PID 2>/dev/null && kill -0 $INGEST_PID 2>/dev/null; then
            COMPOSITE_AVAILABLE=true
            echo -e "${GREEN}✓ Validator flow server running (PID: $VALIDATE_PID)${NC}"
            echo -e "${GREEN}✓ Composite flow server running (PID: $INGEST_PID)${NC}"
        else
            echo -e "${YELLOW}⚠ Composite flow servers failed to start (skipping composite test)${NC}"
            tail -5 /tmp/serve-validate.log 2>/dev/null || true
            tail -5 /tmp/serve-ingest.log 2>/dev/null || true
            kill $VALIDATE_PID $INGEST_PID 2>/dev/null || true
            VALIDATE_PID=""
            INGEST_PID=""
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

# Test 1: Slimfast message — what=daily-report → compare_before_save=True
echo -e "${BLUE}Test 1: Slimfast message (what=daily-report → dedup enabled)${NC}"
echo -e "  Testing: Inline content; server maps 'daily-report' to compare_before_save=True"
RESPONSE=$(curl -s -X POST "http://localhost:8000/ingest" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${APP__TRANSPORT__API_KEY:-demo-key-12345}" \
  -d '{
    "metadata": {
      "who": "demo-user",
      "what": "daily-report",
      "content_type": "text/plain",
      "filename": "report.txt"
    },
    "content": "SGVsbG8sIEthZmthIVRoaXMgaXMgYSB0ZXN0IG1lc3NhZ2Uu"
  }')

echo "$RESPONSE" | python3 -m json.tool
STORAGE_URL_TEST1=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('storage', {}).get('url', ''))")
check_result "$RESPONSE"
echo ""

sleep 2

# Test 2: Deduplication — re-send identical daily-report, expect dedup
echo -e "${BLUE}Test 2: Deduplication (re-send identical daily-report)${NC}"
echo -e "  Testing: Same who/what/content as Test 1 — server enforces dedup (True)"
RESPONSE=$(curl -s -X POST "http://localhost:8000/ingest" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${APP__TRANSPORT__API_KEY:-demo-key-12345}" \
  -d '{
    "metadata": {
      "who": "demo-user",
      "what": "daily-report",
      "content_type": "text/plain",
      "filename": "report.txt"
    },
    "content": "SGVsbG8sIEthZmthIVRoaXMgaXMgYSB0ZXN0IG1lc3NhZ2Uu"
  }')

echo "$RESPONSE" | python3 -m json.tool
check_result "$RESPONSE"
echo ""

sleep 2

# Test 2b: Audit log — what=audit-log → compare_before_save=False (always write)
echo -e "${BLUE}Test 2b: Audit log — same content, always written (what=audit-log → dedup=False)${NC}"
echo -e "  Testing: Server maps 'audit-log' to compare_before_save=False — no dedup ever"
for i in 1 2; do
  RESPONSE=$(curl -s -X POST "http://localhost:8000/ingest" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${APP__TRANSPORT__API_KEY:-demo-key-12345}" \
    -d '{
      "metadata": {
        "who": "demo-user",
        "what": "audit-log",
        "content_type": "text/plain",
        "filename": "audit.txt"
      },
      "content": "SGVsbG8sIEthZmthIVRoaXMgaXMgYSB0ZXN0IG1lc3NhZ2Uu"
    }')
  echo "  Send $i:"
  echo "$RESPONSE" | python3 -m json.tool
  check_result "$RESPONSE"
  sleep 1
done
echo ""

sleep 1

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

# Test 8: Fire-and-forget flow result retrieval via GET /flow/{id}
if [ "$PREFECT_AVAILABLE" = true ]; then
    echo -e "${BLUE}Test 8: Fire-and-forget flow result retrieval (GET /flow/{id})${NC}"
    echo -e "  With APP__FLOW__TIMEOUT=0 (default), POST /ingest returns before the"
    echo -e "  flow runs. We capture flow_run_id, then poll GET /flow/{id} until it"
    echo -e "  reaches a terminal state and reports per-Task results."
    echo ""

    RESPONSE=$(curl -s -X POST "http://localhost:8000/ingest" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer ${APP__TRANSPORT__API_KEY:-demo-key-12345}" \
      -d '{
        "metadata": {
          "who": "demo-user",
          "what": "flow-retrieval-demo",
          "content_type": "text/plain",
          "filename": "retrieval.txt"
        },
        "content": "RmlyZS1hbmQtZm9yZ2V0IHJldHJpZXZhbCBkZW1vLg=="
      }')
    echo "$RESPONSE" | python3 -m json.tool
    FLOW_RUN_ID=$(echo "$RESPONSE" | python3 -c "import sys, json; f=(json.load(sys.stdin).get('flow') or {}); print(f.get('flow_run_id') or '')")

    if [ -z "$FLOW_RUN_ID" ]; then
        echo -e "${YELLOW}⚠ No flow_run_id returned (flow not invoked); skipping retrieval${NC}"
    else
        echo ""
        echo -e "  Captured flow_run_id: ${FLOW_RUN_ID}"
        echo -e "${BLUE}  Immediate GET /flow/{id} (expect pending — success: null):${NC}"
        curl -s "http://localhost:8000/flow/${FLOW_RUN_ID}" | python3 -m json.tool

        echo -e "${BLUE}  Polling GET /flow/{id} until terminal...${NC}"
        for attempt in $(seq 1 15); do
            sleep 2
            FRESP=$(curl -s "http://localhost:8000/flow/${FLOW_RUN_ID}")
            STATUS=$(echo "$FRESP" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', ''))")
            SUCCESS=$(echo "$FRESP" | python3 -c "import sys, json; v=json.load(sys.stdin).get('success'); print('null' if v is None else v)")
            echo -e "  attempt ${attempt}: status=${STATUS} success=${SUCCESS}"
            if [ "$SUCCESS" != "null" ]; then
                echo -e "${GREEN}  ✓ Flow run terminal — final FlowResponse:${NC}"
                echo "$FRESP" | python3 -m json.tool
                break
            fi
        done
    fi
    echo ""
    sleep 1
fi

# Test 9: Composite Flow (subflow) — fire-and-forget + flat FlowResponse
if [ "$COMPOSITE_AVAILABLE" = true ]; then
    echo -e "${BLUE}Test 9: Composite Flow with a subflow${NC}"
    echo -e "  ingest-with-validation-flow saves the file, then invokes validate-flow"
    echo -e "  as a SUBFLOW (timeout=None → waits), folds the child outcome into a"
    echo -e "  single FLAT FlowResponse, publishes it as a Prefect artifact, and branches."
    echo -e "  We trigger the PARENT fire-and-forget (timeout=0) and poll until terminal."
    echo -e "  get_flow_response reads the published artifact back (no result persistence),"
    echo -e "  so the caller sees one flat task list with a 'validate-flow' row and never"
    echo -e "  the subflow. A failing message would show a RED run still carrying the detail."
    echo ""

    uv run python - <<'PY' || true
import time

from rpsd_flow import get_flow_response, run_flow
from rpsd_transport.models import MessageMetadata, TransportMessage

message = TransportMessage(
    metadata=MessageMetadata(
        who="demo-user",
        what="composite-demo",
        content_type="text/plain",
        filename="composite.txt",
    ),
    content=b"Composite flow demo.",
)

deployment = "ingest-with-validation-flow/ingest-deployment"
pending = run_flow(deployment, message)  # timeout=0 → fire-and-forget
run_id = pending.flow_run_id
print(f"  triggered {deployment} (run id={run_id}, status={pending.status})")

final = None
for attempt in range(1, 16):
    time.sleep(2)
    resp = get_flow_response(run_id)
    print(f"  attempt {attempt}: status={resp.status} success={resp.success}")
    if resp.success is not None:
        final = resp
        break

if final is None:
    print("  (composite flow did not reach a terminal state in time)")
else:
    print(f"  FLAT FlowResponse: flow_name={final.flow_name} success={final.success}")
    print("  task_results (the subflow appears as ONE row, no nesting):")
    for tr in final.task_results:
        print(f"    - {tr.task_name}: success={tr.success} duration={tr.duration}")
    print("  Complete final FlowResponse:")
    print(final.model_dump_json(indent=2))
PY
    echo ""
    sleep 1
fi

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
    echo -e "${BLUE}Flow server log (Prefect orchestration):${NC}"
    echo ""
    tail -30 /tmp/sample-flow.log 2>/dev/null | grep -E "Flow run '.*' (- Beginning|- Finished|- View)" | tail -10 || echo "  (No flow log entries yet)"
    echo ""
    echo -e "${BLUE}Streaming read (process-content subprocess, via open_content):${NC}"
    echo ""
    tail -10 "${RPSD_STREAM_LOG:-/tmp/rpsd-stream.log}" 2>/dev/null | sed 's/^/  /' \
        || echo "  (No streaming reads recorded)"
    if [ ! -s "${RPSD_STREAM_LOG:-/tmp/rpsd-stream.log}" ]; then
        echo "  (No streaming reads recorded — only fat/heavy messages stream)"
    fi
    echo ""
fi

if [ "$COMPOSITE_AVAILABLE" = true ]; then
    echo -e "${BLUE}Composite flow logs (parent + validator subflow):${NC}"
    echo ""
    echo "Validator subflow (serve-validate):"
    tail -30 /tmp/serve-validate.log 2>/dev/null | grep -E "(Metadata OK|validate-flow)" | tail -8 || echo "  (No validator log entries yet)"
    echo ""
    echo "Parent flow (serve-ingest):"
    tail -30 /tmp/serve-ingest.log 2>/dev/null | grep -E "(Saving file|Validation succeeded|Validation failed|Flow response)" | tail -8 || echo "  (No parent log entries yet)"
    echo ""
fi

echo -e "${BLUE}Summary of test scenarios:${NC}"
echo "  ✓ Test 1:  Slimfast message (what=daily-report → compare_before_save=True)"
echo "  ✓ Test 2:  Deduplication — identical daily-report skipped (True)"
echo "  ✓ Test 2b: Audit log — identical content always written (what=audit-log → False)"
echo "  ✓ Test 3:  Fatheavy with https:// URL (what=https-content → None/default)"
echo "  ✓ Test 4:  Fatheavy with file:// URL  (what=file-reference → None/default)"
echo "  ✓ Test 5:  Fatheavy with http:// URL  (what=http-content → None/default)"
echo "  ✓ Test 6:  Error handling - non-existent file:// URL"
echo "  ✓ Test 7:  Error handling - HTTP 404"
if [ "$PREFECT_AVAILABLE" = true ]; then
    echo "  ✓ Test 8:  Fire-and-forget flow result retrieval (GET /flow/{id})"
    echo "  ✓ Prefect Flow invoked for each test (3-task pipeline)"
fi
if [ "$COMPOSITE_AVAILABLE" = true ]; then
    echo "  ✓ Test 9:  Composite flow — validate-flow invoked as a subflow, flat response"
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
    echo "  • process-content — subprocess task (scripts/process.py,"
    echo "    sleep tunable via RPSD_PROCESS_SLEEP=${RPSD_PROCESS_SLEEP:-5}s)"
    echo "  • finalize — fast task logging the result"
    echo "  • GET /flow/{id} — retrieve a fire-and-forget run's FlowResponse later"
    echo ""
fi
if [ "$COMPOSITE_AVAILABLE" = true ]; then
    echo "Composite (subflow) Flow demonstrated:"
    echo "  • validate-flow — lower-level Flow, served on its OWN pool (serve-validate)"
    echo "  • ingest-with-validation-flow — parent, served on its OWN pool (serve-ingest);"
    echo "    invokes validate-flow as a subflow (timeout=None), folds the child into a"
    echo "    FLAT FlowResponse via add_subflow, then branches on child.success"
    echo "  • Each flow publishes a Markdown artifact; get_flow_response reads it back"
    echo "    (no result persistence), and a failed run is RED but keeps its detail"
    echo "  • External trigger is fire-and-forget (timeout=0); the wait happens inside"
    echo "    the parent worker, not the caller"
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
echo -e "${GREEN}Flow result:${NC}      http://localhost:8000/flow/{flow_run_id}"
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
if [ -n "$VALIDATE_PID" ]; then
    echo -e "  Validate: tail -f /tmp/serve-validate.log"
fi
if [ -n "$INGEST_PID" ]; then
    echo -e "  Ingest:   tail -f /tmp/serve-ingest.log"
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
    if [ -n "$INGEST_PID" ]; then
        kill $INGEST_PID 2>/dev/null || true
    fi
    if [ -n "$VALIDATE_PID" ]; then
        kill $VALIDATE_PID 2>/dev/null || true
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

#!/bin/bash
#
# Test requests for FastAPI Ingest Example
#
# Usage: ./test-requests.sh
#
# Prerequisites:
# 1. Start the application: uv run python examples/fastapi-ingest-app/main.py
# 2. Configure environment variables (see .env.example)

set -e

# Configuration
BASE_URL="${BASE_URL:-http://localhost:8000}"
API_KEY="${API_KEY:-your-secret-key}"

echo "======================================"
echo "FastAPI Ingest Example - Test Requests"
echo "======================================"
echo ""
echo "Base URL: $BASE_URL"
echo "API Key: $API_KEY"
echo ""
echo "Deduplication is resolved server-side from the 'what' field:"
echo "  daily-report, config-snapshot, test-report → compare_before_save=True"
echo "  audit-log, transaction-record             → compare_before_save=False"
echo "  anything else                              → None (instance default)"
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper function
run_test() {
    local name=$1
    shift
    echo -e "${BLUE}Test: $name${NC}"
    echo "Command: curl $@"
    echo ""
    curl -s "$@" | python3 -m json.tool || echo "Response not JSON"
    echo ""
    echo -e "${GREEN}---${NC}"
    echo ""
}

# Test 1: Health check (no auth required)
run_test "Health Check" \
    -X GET "$BASE_URL/health"

# Test 2: Deduplication enabled — what=daily-report → compare_before_save=True
# Send twice with identical content; second call should be deduplicated.
REPORT_B64=$(echo -n '{"period": "2024-01-01", "value": 42}' | base64)
run_test "Dedup ON — first daily-report (what=daily-report → True)" \
    -X POST "$BASE_URL/ingest" \
    -H "Authorization: Bearer $API_KEY" \
    -H "Content-Type: application/json" \
    -d "{
        \"metadata\": {
            \"who\": \"alice\",
            \"what\": \"daily-report\",
            \"content_type\": \"application/json\",
            \"filename\": \"report.json\"
        },
        \"content\": \"$REPORT_B64\"
    }"

run_test "Dedup ON — identical daily-report re-sent (expect deduplicated=true)" \
    -X POST "$BASE_URL/ingest" \
    -H "Authorization: Bearer $API_KEY" \
    -H "Content-Type: application/json" \
    -d "{
        \"metadata\": {
            \"who\": \"alice\",
            \"what\": \"daily-report\",
            \"content_type\": \"application/json\",
            \"filename\": \"report.json\"
        },
        \"content\": \"$REPORT_B64\"
    }"

# Test 3: Deduplication disabled — what=audit-log → compare_before_save=False
# Send twice with identical content; both calls must always be written.
AUDIT_B64=$(echo -n 'user=alice action=login result=ok' | base64)
run_test "Dedup OFF — first audit-log (what=audit-log → False)" \
    -X POST "$BASE_URL/ingest" \
    -H "Authorization: Bearer $API_KEY" \
    -H "Content-Type: application/json" \
    -d "{
        \"metadata\": {
            \"who\": \"alice\",
            \"what\": \"audit-log\",
            \"content_type\": \"text/plain\",
            \"filename\": \"audit.txt\"
        },
        \"content\": \"$AUDIT_B64\"
    }"

run_test "Dedup OFF — identical audit-log re-sent (expect deduplicated=false)" \
    -X POST "$BASE_URL/ingest" \
    -H "Authorization: Bearer $API_KEY" \
    -H "Content-Type: application/json" \
    -d "{
        \"metadata\": {
            \"who\": \"alice\",
            \"what\": \"audit-log\",
            \"content_type\": \"text/plain\",
            \"filename\": \"audit.txt\"
        },
        \"content\": \"$AUDIT_B64\"
    }"

# Test 4: Instance default — what=sensor-reading → compare_before_save=None
# Dedup behaviour falls back to APP__STORAGE__COMPARE_BEFORE_SAVE in .env.
run_test "Instance default — outline format (what=sensor-reading → None)" \
    -X POST "$BASE_URL/ingest" \
    -H "Authorization: Bearer $API_KEY" \
    -H "X-RPSD-WHO: bob" \
    -H "X-RPSD-WHAT: sensor-reading" \
    -H "Content-Type: application/json" \
    -d '{"sensor": "temp-01", "value": 21.5}'

# Test 5: Outline format with query parameters (what=text-data → None)
run_test "Instance default — query params (what=text-data → None)" \
    -X POST "$BASE_URL/ingest?who=bob&what=text-data" \
    -H "Authorization: Bearer $API_KEY" \
    -H "Content-Type: text/plain" \
    -d "This is plain text content for testing"

# Test 6: Inline format with JSON (what=inline-test → None)
CONTENT_B64=$(echo -n '{"nested": "json", "value": 42}' | base64)
run_test "Instance default — inline format (what=inline-test → None)" \
    -X POST "$BASE_URL/ingest" \
    -H "Authorization: Bearer $API_KEY" \
    -H "Content-Type: application/json" \
    -d "{
        \"metadata\": {
            \"who\": \"charlie\",
            \"what\": \"inline-test\",
            \"content_type\": \"application/json\",
            \"filename\": \"test.json\"
        },
        \"content\": \"$CONTENT_B64\"
    }"

# Test 7: Legacy headers (backward compatibility) — what=legacy-data → None
run_test "Legacy Format - X-RAPS-INGEST headers (what=legacy-data → None)" \
    -X POST "$BASE_URL/ingest" \
    -H "Authorization: Bearer $API_KEY" \
    -H "X-RAPS-INGEST_WHO: legacy-user" \
    -H "X-RAPS-INGEST_WHAT: legacy-data" \
    -H "Content-Type: application/xml" \
    -d '<?xml version="1.0"?><test>Legacy XML</test>'

# Test 8: Token authentication — what=token-test → None
run_test "Token Authentication (what=token-test → None)" \
    -X POST "$BASE_URL/ingest" \
    -H "Authorization: Token $API_KEY" \
    -H "X-RPSD-WHO: alice" \
    -H "X-RPSD-WHAT: token-test" \
    -H "Content-Type: text/plain" \
    -d "Testing Token auth"

# Test 9: config-snapshot → compare_before_save=True (another dedup category)
SNAP_B64=$(echo -n '{"version": "1.2.3", "feature_flags": {"x": true}}' | base64)
run_test "Dedup ON — config-snapshot (what=config-snapshot → True)" \
    -X POST "$BASE_URL/ingest" \
    -H "Authorization: Bearer $API_KEY" \
    -H "Content-Type: application/json" \
    -d "{
        \"metadata\": {
            \"who\": \"system\",
            \"what\": \"config-snapshot\",
            \"content_type\": \"application/json\",
            \"filename\": \"config.json\"
        },
        \"content\": \"$SNAP_B64\"
    }"

# Test 10: transaction-record → compare_before_save=False (always write)
TXN_B64=$(echo -n 'txn-id=abc123 amount=99.95 status=ok' | base64)
run_test "Dedup OFF — transaction-record (what=transaction-record → False)" \
    -X POST "$BASE_URL/ingest" \
    -H "Authorization: Bearer $API_KEY" \
    -H "Content-Type: application/json" \
    -d "{
        \"metadata\": {
            \"who\": \"payments\",
            \"what\": \"transaction-record\",
            \"content_type\": \"text/plain\",
            \"filename\": \"txn.txt\"
        },
        \"content\": \"$TXN_B64\"
    }"

# Test 11: Binary content (base64 in inline format) — what=binary-test → None
BINARY_B64=$(echo -n "Binary content with special chars: \x00\x01\x02" | base64)
run_test "Instance default — binary content (what=binary-test → None)" \
    -X POST "$BASE_URL/ingest" \
    -H "Authorization: Bearer $API_KEY" \
    -H "Content-Type: application/json" \
    -d "{
        \"metadata\": {
            \"who\": \"alice\",
            \"what\": \"binary-test\",
            \"content_type\": \"application/octet-stream\",
            \"filename\": \"data.bin\"
        },
        \"content\": \"$BINARY_B64\"
    }"

echo ""
echo "======================================"
echo "Error Cases"
echo "======================================"
echo ""

# Error Test 1: Missing API key
run_test "ERROR: Missing API Key (expect 401)" \
    -X POST "$BASE_URL/ingest" \
    -H "X-RPSD-WHO: alice" \
    -H "X-RPSD-WHAT: test-data" \
    -d '{"test": "data"}'

# Error Test 2: Invalid API key
run_test "ERROR: Invalid API Key (expect 401)" \
    -X POST "$BASE_URL/ingest" \
    -H "Authorization: Bearer wrong-key" \
    -H "X-RPSD-WHO: alice" \
    -H "X-RPSD-WHAT: test-data" \
    -d '{"test": "data"}'

# Error Test 3: Missing 'who' metadata
run_test "ERROR: Missing 'who' metadata (expect 400)" \
    -X POST "$BASE_URL/ingest" \
    -H "Authorization: Bearer $API_KEY" \
    -H "X-RPSD-WHAT: test-data" \
    -d '{"test": "data"}'

# Error Test 4: Missing 'what' metadata
run_test "ERROR: Missing 'what' metadata (expect 400)" \
    -X POST "$BASE_URL/ingest" \
    -H "Authorization: Bearer $API_KEY" \
    -H "X-RPSD-WHO: alice" \
    -d '{"test": "data"}'

# Error Test 5: Invalid metadata characters
run_test "ERROR: Invalid 'who' characters (expect 400)" \
    -X POST "$BASE_URL/ingest" \
    -H "Authorization: Bearer $API_KEY" \
    -H "X-RPSD-WHO: alice@example.com" \
    -H "X-RPSD-WHAT: test-data" \
    -d '{"test": "data"}'

echo ""
echo "======================================"
echo "Kafka Forwarding Tests"
echo "======================================"
echo ""
echo "Note: These tests require Kafka to be running."
echo "      Start Kafka: cd ../../host-scripts && ./kafka-start.sh"
echo ""

# Test 9: Verify forwarding enabled (check response contains 'forwarded' field)
RESPONSE=$(curl -s -X POST "$BASE_URL/ingest" \
    -H "Authorization: Bearer $API_KEY" \
    -H "X-RPSD-WHO: forward-test" \
    -H "X-RPSD-WHAT: test-forwarding" \
    -H "Content-Type: text/plain" \
    -d "Test message for Kafka forwarding")

echo -e "${BLUE}Test: Kafka Forwarding - Response Check${NC}"
echo "$RESPONSE" | python3 -m json.tool

FORWARDED=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('forwarded', False))")
if [ "$FORWARDED" = "True" ]; then
    echo -e "${GREEN}✓ Forwarding enabled (forwarded: true)${NC}"
else
    echo -e "${BLUE}ℹ Forwarding disabled or Kafka not available (forwarded: false)${NC}"
fi
echo ""

# Test 10: Verify fatheavy forwarding (message should contain storage URL)
echo -e "${BLUE}Test: Fatheavy Forwarding - Check Kafka Message Format${NC}"
echo "After running this test, check Kafka UI at http://localhost:8080"
echo "Expected in Kafka message:"
echo "  - 'where' field should contain storage URL"
echo "  - 'content' field should be null or absent"
echo ""
echo "Manual verification:"
echo "  1. Open http://localhost:8080"
echo "  2. Navigate to Topics → enriched-events"
echo "  3. View the latest message"
echo "  4. Verify it contains 'where' field with storage URL"
echo ""
echo -e "${GREEN}---${NC}"
echo ""

# Test 11: Slimfast forwarding (if mode is set to slimfast)
echo -e "${BLUE}Test: Slimfast Forwarding - Inline Content${NC}"
echo "If APP__FORWARD__MODE=slimfast, Kafka message should contain:"
echo "  - 'content' field with actual content"
echo "  - No 'where' field"
echo ""
echo -e "${GREEN}---${NC}"
echo ""

echo ""
echo "======================================"
echo "All tests completed!"
echo "======================================"
echo ""
echo "Check storage directory for saved files:"
echo "  ls -la /tmp/rpsd-storage/alice/daily-report/   # 1 file (dedup)"
echo "  ls -la /tmp/rpsd-storage/alice/audit-log/      # 2 files (force-save)"
echo "  ls -la /tmp/rpsd-storage/alice/config-snapshot/ # 1 file (dedup)"
echo "  ls -la /tmp/rpsd-storage/payments/transaction-record/ # 1 file (force-save)"
echo "  ls -la /tmp/rpsd-storage/bob/"
echo "  ls -la /tmp/rpsd-storage/charlie/"
echo ""
echo "Check Kafka for forwarded messages:"
echo "  Kafka UI: http://localhost:8080"
echo "  Topic: enriched-events"
echo ""

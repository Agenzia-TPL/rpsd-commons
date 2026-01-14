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

# Test 2: Outline format with headers
run_test "Outline Format - Headers (JSON content)" \
    -X POST "$BASE_URL/ingest" \
    -H "Authorization: Bearer $API_KEY" \
    -H "X-RPSD-WHO: alice" \
    -H "X-RPSD-WHAT: test-data" \
    -H "Content-Type: application/json" \
    -d '{"example": "data", "timestamp": "2024-01-01T00:00:00Z"}'

# Test 3: Outline format with query parameters
run_test "Outline Format - Query Params (plain text)" \
    -X POST "$BASE_URL/ingest?who=bob&what=text-data" \
    -H "Authorization: Bearer $API_KEY" \
    -H "Content-Type: text/plain" \
    -d "This is plain text content for testing"

# Test 4: Inline format with JSON
# Note: Content must be base64-encoded
CONTENT_B64=$(echo -n '{"nested": "json", "value": 42}' | base64)
run_test "Inline Format - JSON with embedded metadata" \
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

# Test 5: Legacy headers (backward compatibility)
run_test "Legacy Format - X-RAPS-INGEST headers" \
    -X POST "$BASE_URL/ingest" \
    -H "Authorization: Bearer $API_KEY" \
    -H "X-RAPS-INGEST_WHO: legacy-user" \
    -H "X-RAPS-INGEST_WHAT: legacy-data" \
    -H "Content-Type: application/xml" \
    -d '<?xml version="1.0"?><test>Legacy XML</test>'

# Test 6: Token authentication instead of Bearer
run_test "Token Authentication" \
    -X POST "$BASE_URL/ingest" \
    -H "Authorization: Token $API_KEY" \
    -H "X-RPSD-WHO: alice" \
    -H "X-RPSD-WHAT: token-test" \
    -H "Content-Type: text/plain" \
    -d "Testing Token auth"

# Test 7: X-API-Key header authentication
run_test "X-API-Key Authentication" \
    -X POST "$BASE_URL/ingest" \
    -H "X-API-Key: $API_KEY" \
    -H "X-RPSD-WHO: alice" \
    -H "X-RPSD-WHAT: apikey-test" \
    -H "Content-Type: text/plain" \
    -d "Testing X-API-Key auth"

# Test 8: Binary content (base64 in inline format)
BINARY_B64=$(echo -n "Binary content with special chars: \x00\x01\x02" | base64)
run_test "Inline Format - Binary content" \
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
echo "All tests completed!"
echo "======================================"
echo ""
echo "Check storage directory for saved files:"
echo "  ls -la /tmp/rpsd-storage/alice/"
echo "  ls -la /tmp/rpsd-storage/bob/"
echo "  ls -la /tmp/rpsd-storage/charlie/"
echo ""

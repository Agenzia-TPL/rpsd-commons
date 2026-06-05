# FastAPI Ingest Example

A comprehensive FastAPI application demonstrating HTTP ingestion with optional message broker forwarding (Kafka or RabbitMQ) and optional Prefect Flow invocation using `rpsd-transport`, `rpsd-storage`, and `rpsd-flow`.

## Features

- **HTTP Ingestion**: Uses `HTTPCarrier.receive()` for automatic message parsing
- **IngestProcessor Integration**: Demonstrates the processor pattern for message processing
- **Optional Message Broker Forwarding**: Forward processed messages to Kafka or RabbitMQ after storage
- **Storage Abstraction**: Supports both filesystem and S3 storage via configuration
- **Dual Metadata Formats**: Handles both inline (JSON) and outline (headers/query) metadata
- **API Key Authentication**: Bearer/Token authentication with configurable keys
- **Optional Prefect Flow Invocation**: Trigger a Prefect Flow deployment after storage via `rpsd-flow`
- **Async Lifecycle Management**: Proper startup/shutdown handling for broker connections
- **Carrier Abstraction**: Single codebase works with multiple message brokers via factory pattern
- **Modality Support**: Demonstrates HTTP→Storage, HTTP→Storage→Broker, and HTTP→Storage→Flow pipelines

## Architecture

### Modality #1: HTTP → Storage (Forward Disabled)

```
External System
    ↓ HTTP POST /ingest
FastAPI App (HTTPCarrier)
    ↓ IngestProcessor.process()
Storage (S3/Filesystem)
    ↓ HTTP 201 Response
External System
```

### Modality #3: HTTP → Storage → Message Broker (Forward Enabled)

```
External System
    ↓ HTTP POST /ingest
FastAPI App (HTTPCarrier)
    ↓ IngestProcessor.process()
    ├─→ Storage (S3/Filesystem)
    │     [Content saved]
    │
    └─→ Message Broker (Kafka or RabbitMQ)
          Topic/Queue: enriched-events
          [Notification with storage URL]
          ↓
    Downstream Consumer
          [Fetches from storage URL]
```

**Forward Modes:**
- **fatheavy** (default): Forwards storage URL reference - efficient, recommended
- **slimfast**: Forwards content inline - self-contained, larger messages

### Modality #3: HTTP → Storage → Prefect Flow (Flow Enabled)

```
External System
    ↓ HTTP POST /ingest
FastAPI App (HTTPCarrier)
    ↓ IngestProcessor.process()
    ├─→ Storage (S3/Filesystem)
    │     [Content saved]
    │
    └─→ Prefect Flow Deployment
          [Triggered with TransportMessage]
          [message.where = storage URL]
          ↓
    Flow Tasks (validate → process → finalize)
```

**Note**: Forwarding and flow invocation are independent features.
Both can be enabled simultaneously.

## Installation

From the workspace root:

```bash
uv sync
```

This installs all workspace dependencies including `rpsd-transport[kafka,rabbitmq]`, `rpsd-storage`, `rpsd-flow`, and FastAPI.

**Note**: The `[kafka,rabbitmq]` extras include `aiokafka` and `aio-pika` for message broker support. These are true optional dependencies - you only need them if you want to enable forwarding.

## Configuration

### Option 1: Using .env File (Recommended)

Copy the example file and configure your settings:

```bash
cd examples/fastapi_ingest_app
cp .env.example .env
```

Edit `.env` with your settings:

```bash
# Required: API key for authentication
APP__TRANSPORT__API_KEY=your-secret-key-here

# Required: Storage configuration
APP__STORAGE__PROVIDER=fs
APP__STORAGE__FS__BASE_PATH=/tmp/rpsd-storage

# Optional: Message broker forwarding (FastAPI app publishes)
# For Kafka:
# APP__FORWARD__CARRIER=kafka
# APP__FORWARD__RECIPIENT=enriched-events
# APP__FORWARD__MODE=fatheavy
# APP__FORWARD__KAFKA__BOOTSTRAP_SERVERS=host.docker.internal:9092
# APP__FORWARD__KAFKA__CLIENT_ID=fastapi-forwarder
#
# For RabbitMQ:
# APP__FORWARD__CARRIER=rabbitmq
# APP__FORWARD__RECIPIENT=enriched-events
# APP__FORWARD__MODE=fatheavy
# APP__FORWARD__RABBITMQ__URL=amqp://guest:guest@host.docker.internal/

# Optional: Prefect Flow invocation (triggers a flow after storage)
# APP__FLOW__DEPLOYMENT=ingest-flow/ingest-deployment
# APP__FLOW__TIMEOUT=60.0
# PREFECT_API_URL=http://host.docker.internal:4200/api

# Optional: Message broker consumption (consumer.py script)
# Separate settings demonstrate separation of concerns: publishing vs consuming
# For Kafka:
# APP__CONSUMER__CARRIER=kafka
# APP__CONSUMER__TOPIC=enriched-events
# APP__CONSUMER__KAFKA__BOOTSTRAP_SERVERS=host.docker.internal:9092
# APP__CONSUMER__KAFKA__GROUP_ID=demo-consumer
#
# For RabbitMQ:
# APP__CONSUMER__CARRIER=rabbitmq
# APP__CONSUMER__TOPIC=enriched-events
# APP__CONSUMER__RABBITMQ__URL=amqp://guest:guest@host.docker.internal/
```

**Important**: The `.env` file must be in your current working directory when running the app.

### Configuration Structure: Forward vs Consumer

This example demonstrates **separation of concerns** between publishing and consuming:

- **`APP__FORWARD__*`** - Used by the FastAPI application (`main.py`) for **publishing** messages after storage
- **`APP__CONSUMER__*`** - Used by the consumer script (`consumer.py`) for **consuming** messages

This separation is educational and shows best practices:
- Real applications are typically either publishers OR consumers, not both
- Each has different configuration needs (e.g., Kafka consumers require `group_id`, publishers don't)
- Keeping settings separate makes the code clearer and easier to maintain

### Option 2: Environment Variables

Export variables directly:

```bash
export APP__TRANSPORT__API_KEY=your-secret-key
export APP__STORAGE__PROVIDER=fs
export APP__STORAGE__FS__BASE_PATH=/tmp/rpsd-storage
```

### Connection Strings

**Kafka:**

From devcontainer (inside Docker):
```bash
APP__FORWARD__KAFKA__BOOTSTRAP_SERVERS=host.docker.internal:9092
```

From host machine (outside Docker):
```bash
APP__FORWARD__KAFKA__BOOTSTRAP_SERVERS=localhost:9092
```

**RabbitMQ:**

From devcontainer (inside Docker):
```bash
APP__FORWARD__RABBITMQ__URL=amqp://guest:guest@host.docker.internal/
```

From host machine (outside Docker):
```bash
APP__FORWARD__RABBITMQ__URL=amqp://guest:guest@localhost/
```

## Infrastructure Setup (Optional)

Choose the infrastructure you need based on which features you want to enable.

### Kafka Setup

To use Kafka forwarding, you must start Kafka infrastructure on your host machine.

### Start Kafka

From your **host machine** (not from inside devcontainer):

```bash
cd host-scripts
./kafka/start.sh
```

This starts:
- Kafka broker (KRaft mode, no Zookeeper) on port 9092
- Kafka UI on port 8080
- Schema Registry on port 8081
- Creates default topic: `enriched-events`

### Stop Kafka

```bash
cd host-scripts
./kafka/stop.sh
```

To stop and remove all data:

```bash
./kafka/stop.sh --clean
```

### Access Kafka UI

Open http://localhost:8080 in your browser to:
- Browse topics and messages
- View consumer groups
- Monitor broker health
- Create/delete topics

### RabbitMQ Setup

From your **host machine** (not from inside devcontainer):

```bash
cd host-scripts
./rabbitmq/start.sh
```

This starts:
- RabbitMQ broker (AMQP 0.9.1) on port 5672
- Management UI on port 15672 (guest/guest)
- Creates queues automatically on first publish

### Stop RabbitMQ

```bash
cd host-scripts
./rabbitmq/stop.sh
```

To stop and remove all data:

```bash
./rabbitmq/stop.sh --clean
```

### Access RabbitMQ Management UI

Open http://localhost:15672 in your browser:
- Username: `guest`
- Password: `guest`
- Browse queues, exchanges, and bindings
- View message rates and statistics
- Manage users and permissions

### Prefect Server Setup

To use Prefect Flow invocation, you must start Prefect server infrastructure on your host machine.

### Start Prefect

From your **host machine** (not from inside devcontainer):

```bash
cd host-scripts
./prefect/start.sh
```

This starts:
- PostgreSQL (Prefect metadata store)
- Redis (Prefect cache)
- Prefect server on port 4200

### Stop Prefect

```bash
cd host-scripts
./prefect/stop.sh
```

To stop and remove all data:

```bash
./prefect/stop.sh --clean
```

### Access Prefect UI

Open http://localhost:4200 in your browser to:
- View flow runs and their status
- Browse deployments
- Monitor task execution
- View logs and artifacts

## Choosing a Message Broker

**Use Kafka when:**
- You need high-throughput event streaming
- Message replay is required
- Multiple consumers need the same messages
- You want log-based messaging

**Use RabbitMQ when:**
- You need task queues and job processing
- You want request-reply patterns (RPC)
- You need flexible routing via exchanges
- You prefer simpler operational requirements

## Running the Application

### Standard Run

```bash
cd examples/fastapi_ingest_app
uv run fastapi-ingest-app
```

The app will start on http://localhost:8000

### Development Mode (with auto-reload)

```bash
uv run uvicorn fastapi_ingest_app.main:app --reload --host 0.0.0.0 --port 8000
```

### From Workspace Root

```bash
uv run --directory examples/fastapi_ingest_app fastapi-ingest-app
```

## Running the Consumer

To demonstrate receiving forwarded messages from either Kafka or RabbitMQ:

```bash
cd examples/fastapi_ingest_app

# Configure the carrier (set in .env or export)
export APP__FORWARD__CARRIER=kafka  # or rabbitmq
export APP__FORWARD__RECIPIENT=enriched-events

# For Kafka
export APP__FORWARD__KAFKA__BOOTSTRAP_SERVERS=host.docker.internal:9092

# For RabbitMQ
export APP__FORWARD__RABBITMQ__URL=amqp://guest:guest@host.docker.internal/

# Run consumer (works with both carriers)
uv run consumer
```

This consumer will:
- Connect to the configured message broker (Kafka or RabbitMQ)
- Subscribe to the specified topic/queue
- Display received messages with metadata
- Fetch content from storage URLs (for fatheavy messages)
- Show rich metadata from storage providers

## Running the Sample Flow

To demonstrate Prefect Flow invocation after ingest:

### 1. Start Prefect Server

From your **host machine** (not from inside devcontainer):

```bash
cd host-scripts
./prefect/start.sh
```

### 2. Serve the Sample Flow

```bash
cd examples/fastapi_ingest_app
uv run sample-flow
```

This starts serving the `ingest-flow/ingest-deployment`
deployment, listening for triggered flow runs.

The sample flow demonstrates a three-task pipeline:
1. **validate-message** — fast task that checks metadata
2. **process-content** — subprocess task calling `scripts/process.py`
3. **finalize** — fast task that logs the processing result

`scripts/process.py` simulates heavy processing with a sleep whose duration is
tunable via the `RPSD_PROCESS_SLEEP` environment variable (seconds, default
`3.0`). Set it in the environment of the task server, e.g.
`RPSD_PROCESS_SLEEP=10 uv run sample-task`, to make the fire-and-forget →
poll-later flow easy to observe, or `RPSD_PROCESS_SLEEP=0` to make runs
instant. (`demo.sh` sets it to `5` by default.)

### 3. Configure Flow Invocation

Add to your `.env`:

```bash
APP__FLOW__DEPLOYMENT=ingest-flow/ingest-deployment
PREFECT_API_URL=http://host.docker.internal:4200/api
```

### 4. Start the FastAPI App

```bash
uv run fastapi-ingest-app
```

### 5. Send a Request

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Authorization: Bearer your-secret-key" \
  -H "X-RPSD-Who: alice" \
  -H "X-RPSD-What: report" \
  -H "Content-Type: application/json" \
  -d '{"data": "example"}'
```

The response will include `"flow_invoked": true` and a `"flow"` block
projecting the `FlowResponse` (status, success, per-Task results); the
flow execution will be visible in the Prefect UI at http://localhost:4200.
See [POST /ingest → Response](#response) for the `flow` block details and
how `APP__FLOW__TIMEOUT` shapes it.

## Quick Demo

Run the automated end-to-end demo with your choice of message broker:

```bash
cd examples/fastapi_ingest_app

# Use Kafka (default)
./demo.sh
# or explicitly:
./demo.sh kafka

# Use RabbitMQ
./demo.sh rabbitmq
```

The demo script accepts an optional carrier argument (`kafka` or `rabbitmq`) and automatically:
1. Checks if the specified message broker is running
2. Configures environment variables for the selected carrier
3. Starts FastAPI application
4. Starts message broker consumer
5. Sends test requests (slimfast and fatheavy)
6. Verifies results in storage and the message broker
7. Shows carrier-specific access URLs and logs

**Before running the demo:**
- For Kafka: Run `../../host-scripts/kafka/start.sh` from your host machine
- For RabbitMQ: Run `../../host-scripts/rabbitmq/start.sh` from your host machine

Press Ctrl+C to stop the demo. Your original `.env` file will be automatically restored.

## API Endpoints

### POST /ingest

Receive and store data with optional Kafka forwarding.

#### Outline Format (Headers)

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Authorization: Bearer your-api-key" \
  -H "X-RPSD-Who: alice" \
  -H "X-RPSD-What: report" \
  -H "Content-Type: application/json" \
  -d '{"data": "example"}'
```

#### Outline Format (Query Parameters)

```bash
curl -X POST "http://localhost:8000/ingest?who=alice&what=report" \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: text/plain" \
  -d "Plain text content"
```

#### Inline Format (JSON)

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "metadata": {
      "who": "alice",
      "what": "report",
      "content_type": "application/json",
      "filename": "data.json"
    },
    "content": "eyJkYXRhIjogImV4YW1wbGUifQ=="
  }'
```

Note: Content must be base64-encoded in inline format.

#### Fatheavy Format (URL Reference)

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Authorization: Bearer your-api-key" \
  -H "X-RPSD-Who: alice" \
  -H "X-RPSD-What: large-file" \
  -H "X-RPSD-Where: https://example.com/content.pdf" \
  -H "X-RPSD-Content-Type: application/pdf" \
  -d ""
```

#### Response

```json
{
  "success": true,
  "message": "Content received and stored",
  "deduplicated": false,
  "forwarded": true,
  "flow_invoked": true,
  "flow": {
    "deployment": "ingest-flow/ingest-deployment",
    "flow_run_id": "0190a1b2-c3d4-7e5f-8a9b-0c1d2e3f4a5b",
    "status": "COMPLETED",
    "success": true,
    "started_at": "2026-01-15T10:30:00+00:00",
    "finished_at": "2026-01-15T10:30:04+00:00",
    "task_results": [
      {"task_name": "validate-message", "success": true, "duration": 0.01, "error": null},
      {"task_name": "process-content", "success": true, "duration": 3.42, "error": null},
      {"task_name": "finalize", "success": true, "duration": 0.01, "error": null}
    ]
  },
  "metadata": {
    "who": "alice",
    "what": "report",
    "content_type": "application/json"
  },
  "storage": {
    "provider": "fs",
    "url": "file:///tmp/rpsd-storage/alice/report/abc123.json",
    "content_type": "application/json",
    "content_length": 1024,
    "hash": "d41d8cd98f00b204e9800998ecf8427e",
    "who": "alice",
    "what": "report",
    "original_filename": "data.json",
    "object_id": "abc123",
    "save_stamp": "2026-01-15T10:30:00Z",
    "schema_version": 1,
    "source_url": "",
    "custom_metadata": {}
  }
}
```

The `flow` block is a projection of the `FlowResponse` that
`run_flow_async` now always returns. Its contents depend on
`APP__FLOW__TIMEOUT`:

- **`0` (fire-and-forget, default)** — the call returns before the flow
  runs, so `status` is `"SCHEDULED"`, `success` is `null`, and
  `task_results` is empty. Watch the run finish in the Prefect UI.
- **`null` or a positive number (waits)** — `run_flow_async` waits for the
  run and surfaces the flow's own `FlowResponse` verbatim: `success` is
  `true`/`false` and `task_results` carries the per-Task outcome
  (`success`, `duration`, and `error` on failure) built inside
  `ingest_flow`. On a partial failure, the failing Task's `error` is set
  and the downstream Task is skipped (so it won't appear).

To see the populated `task_results`, either set `APP__FLOW__TIMEOUT=60` (and
run the task server, `uv run sample-task`, so the subprocess Task can
execute), **or** keep the default fire-and-forget and fetch the outcome later
with [`GET /flow/{flow_run_id}`](#get-flowflow_run_id).

### GET /flow/{flow_run_id}

Retrieve the `FlowResponse` for a previously triggered run — the
fire-and-forget → poll-later loop. Take the `flow_run_id` from a
`POST /ingest` response's `flow` block and request it later:

```bash
curl http://localhost:8000/flow/096855da-862a-47ef-87bc-7501b0a98115
```

```json
{
  "deployment": null,
  "flow_run_id": "096855da-862a-47ef-87bc-7501b0a98115",
  "status": "COMPLETED",
  "success": true,
  "started_at": "2026-01-15T10:30:00+00:00",
  "finished_at": "2026-01-15T10:30:04+00:00",
  "task_results": [
    {"task_name": "validate-message", "success": true, "duration": 0.01, "error": null},
    {"task_name": "process-content", "success": true, "duration": 3.42, "error": null},
    {"task_name": "finalize", "success": true, "duration": 0.01, "error": null}
  ]
}
```

While the run is still scheduled/running, `success` is `null` and
`task_results` is empty — poll again until it goes terminal. This is backed by
rpsd-flow's `get_flow_response_async`, which reconstructs the original message
from the run's stored parameters, so the app keeps no per-run state.

### GET /health

Health check endpoint.

```bash
curl http://localhost:8000/health
```

Response:

```json
{
  "status": "healthy",
  "storage_provider": "fs",
  "forward_carrier": "kafka",
  "forward_recipient": "enriched-events",
  "flow_deployment": "ingest-flow/ingest-deployment"
}
```

## Testing

### Run All Tests

```bash
cd examples/fastapi_ingest_app
./test-requests.sh
```

This runs comprehensive tests including:
- Health check
- Outline format (headers and query params)
- Inline format (JSON)
- Legacy headers (backward compatibility)
- Different authentication methods
- Binary content
- Kafka forwarding verification
- Error cases (invalid auth, missing metadata)

### Manual Testing

Start the app and use curl or Postman to send requests to http://localhost:8000/ingest.

### Verify Storage

Check saved files:

```bash
ls -la /tmp/rpsd-storage/alice/
cat /tmp/rpsd-storage/alice/report/*.json
cat /tmp/rpsd-storage/alice/report/*.json.meta
```

### Verify Kafka Forwarding

1. Open Kafka UI: http://localhost:8000
2. Navigate to Topics → enriched-events
3. View messages
4. Verify fatheavy messages contain `where` field with storage URL
5. Verify slimfast messages contain inline `content`

## Configuration Options

### Storage Providers

#### Filesystem Storage

```bash
APP__STORAGE__PROVIDER=fs
APP__STORAGE__FS__BASE_PATH=/tmp/rpsd-storage
```

Structure: `{base_path}/{who}/{what}/{uuid}.{ext}`

#### S3 Storage

```bash
APP__STORAGE__PROVIDER=s3
APP__STORAGE__S3__BUCKET_NAME=my-bucket
```

Requires AWS credentials (env vars, credentials file, or IAM role).

### Forwarding Configuration

#### Disable Forwarding

Comment out or remove `APP__FORWARD__CARRIER`:

```bash
# APP__FORWARD__CARRIER=kafka
```

System works as HTTP → Storage only.

#### Enable Kafka Forwarding

```bash
APP__FORWARD__CARRIER=kafka
APP__FORWARD__RECIPIENT=enriched-events
APP__FORWARD__MODE=fatheavy
APP__FORWARD__KAFKA__BOOTSTRAP_SERVERS=host.docker.internal:9092
```

System works as HTTP → Storage → Kafka.

### Flow Invocation Configuration

#### Disable Flow Invocation (default)

Comment out or remove `APP__FLOW__DEPLOYMENT`:

```bash
# APP__FLOW__DEPLOYMENT=ingest-flow/ingest-deployment
```

#### Enable Flow Invocation

```bash
APP__FLOW__DEPLOYMENT=ingest-flow/ingest-deployment
PREFECT_API_URL=http://host.docker.internal:4200/api

# Optional: wait for flow completion (default: fire-and-forget)
# APP__FLOW__TIMEOUT=60.0
```

Requires:
1. A running Prefect server (`host-scripts/prefect/start.sh`)
2. The sample flow served (`uv run sample-flow`)
3. `PREFECT_API_URL` set to the Prefect API endpoint

#### Forward Modes

**Fatheavy** (recommended):
```bash
APP__FORWARD__MODE=fatheavy
```
- Forwards storage URL reference
- Efficient for large content
- Kafka message size stays small
- Consumers fetch content from storage

**Slimfast**:
```bash
APP__FORWARD__MODE=slimfast
```
- Forwards content inline
- Self-contained messages
- Larger Kafka messages
- No external fetch required

## Troubleshooting

### "Kafka is not running" Error

**Problem**: Demo or app fails with Kafka connection error.

**Solution**: Start Kafka from host machine:

```bash
cd host-scripts
./kafka/start.sh
```

### "Connection refused" to host.docker.internal:9092

**Problem**: Can't connect to Kafka from devcontainer.

**Solution**:
1. Verify Kafka is running on host: `docker ps | grep kafka`
2. Test connectivity: `nc -zv host.docker.internal 9092`
3. Check if Docker networking is configured correctly

### "Module 'aiokafka' not found"

**Problem**: Kafka optional dependency not installed.

**Solution**: Install with kafka extras:

```bash
cd examples/fastapi_ingest_app
uv sync
```

Or if you modified pyproject.toml:

```bash
uv sync --reinstall
```

### FastAPI App Won't Start

**Problem**: Port 8000 already in use.

**Solution**: Kill existing process or use different port:

```bash
lsof -ti:8000 | xargs kill -9  # Kill process on port 8000
# OR
uv run uvicorn fastapi_ingest_app.main:app --port 8001  # Use different port
```

### Storage Permission Denied

**Problem**: Can't write to storage path.

**Solution**: Check permissions on base path:

```bash
mkdir -p /tmp/rpsd-storage
chmod 777 /tmp/rpsd-storage
```

### Flow Invocation Not Working

**Problem**: `flow_invoked` is always `false` in the response.

**Possible causes:**
1. Prefect server not running
2. Flow deployment not served
3. Wrong `PREFECT_API_URL`
4. Deployment name mismatch

**Debug steps:**

```bash
# Check Prefect server is reachable
curl http://localhost:4200/api/health

# List deployments
prefect deployment ls

# Check app logs for "Failed to invoke flow" errors
```

### Kafka Consumer Not Receiving Messages

**Possible causes:**
1. Consumer group already consumed messages - use different group_id
2. Topic doesn't exist - check Kafka UI
3. Wrong bootstrap servers - verify connection string
4. Forwarding disabled - check `APP__FORWARD__CARRIER` setting

**Debug steps:**

```bash
# List topics
docker exec rpsd-kafka kafka-topics.sh --bootstrap-server localhost:9092 --list

# Consume from beginning
docker exec rpsd-kafka kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic enriched-events \
  --from-beginning
```

## File Structure

```
examples/fastapi_ingest_app/
├── src/
│   └── fastapi_ingest_app/
│       ├── __init__.py
│       ├── main.py          # FastAPI app with forwarding + flow support
│       ├── settings.py      # Configuration with Forward/Flow settings
│       ├── auth.py          # API key validation
│       ├── consumer.py      # Kafka/RabbitMQ consumer demo
│       └── sample_flow.py   # Sample Prefect Flow + serve entry point
├── scripts/
│   └── process.py           # Subprocess script for the sample flow
├── .env                     # Local configuration (git-ignored)
├── .env.example             # Configuration template
├── pyproject.toml           # Dependencies
├── README.md                # This file
├── demo.sh                  # End-to-end demo script
└── test-requests.sh         # Test script
```

## Related Documentation

- [rpsd-transport documentation](../../packages/rpsd-transport/README.md)
- [rpsd-storage documentation](../../packages/rpsd-storage/README.md)
- [rpsd-flow documentation](../../packages/rpsd-flow/README.md)
- [Kafka host scripts](../../host-scripts/README.md)
- [IngestProcessor API](../../packages/rpsd-transport/src/rpsd_transport/processors/README.md)

## Next Steps

1. **Explore Kafka UI**: Browse topics and messages at http://localhost:8080
2. **Customize forwarding**: Try both fatheavy and slimfast modes
3. **Add consumer logic**: Extend consumer.py with your processing logic
4. **Customize flow routing**: Extend `resolve_flow_deployment()` in main.py to route based on who/what
5. **Add flow tasks**: Extend sample_flow.py with your processing logic
6. **Production deployment**: Replace filesystem storage with S3, use managed Kafka
7. **Add transformations**: Implement custom processing in IngestProcessor
8. **Monitor**: Set up Kafka consumer lag monitoring and alerting

## License

This example is part of the rpsd-commons project.

# FastAPI Ingest Example

A comprehensive FastAPI application demonstrating HTTP ingestion with optional message broker forwarding (Kafka or RabbitMQ) using `rpsd-transport` and `rpsd-storage`.

## Features

- **HTTP Ingestion**: Uses `HTTPCarrier.receive()` for automatic message parsing
- **IngestProcessor Integration**: Demonstrates the processor pattern for message processing
- **Optional Message Broker Forwarding**: Forward processed messages to Kafka or RabbitMQ after storage
- **Storage Abstraction**: Supports both filesystem and S3 storage via configuration
- **Dual Metadata Formats**: Handles both inline (JSON) and outline (headers/query) metadata
- **API Key Authentication**: Bearer/Token authentication with configurable keys
- **Async Lifecycle Management**: Proper startup/shutdown handling for broker connections
- **Carrier Abstraction**: Single codebase works with multiple message brokers via factory pattern
- **Modality Support**: Demonstrates HTTP→Storage and HTTP→Storage→Broker pipelines

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

## Installation

From the workspace root:

```bash
uv sync
```

This installs all workspace dependencies including `rpsd-transport[kafka,rabbitmq]`, `rpsd-storage`, and FastAPI.

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

## Message Broker Setup (Optional)

Choose either Kafka or RabbitMQ (or run both for experimentation).

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
  "storage_url": "file:///tmp/rpsd-storage/alice/report/abc123.json",
  "forwarded": true,
  "metadata": {
    "who": "alice",
    "what": "report",
    "content_type": "application/json",
    "object_id": "abc123",
    "content_length": 1024
  }
}
```

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
  "forward_recipient": "enriched-events"
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
│       ├── main.py          # FastAPI application with forwarding support
│       ├── settings.py      # Configuration with ForwardSettings
│       ├── auth.py          # API key validation
│       └── consumer.py      # Kafka consumer demo
├── .env                     # Local configuration (git-ignored)
├── .env.example             # Configuration template
├── pyproject.toml           # Dependencies (includes kafka extras)
├── README.md                # This file
├── demo.sh                  # End-to-end demo script
└── test-requests.sh         # Test script with Kafka tests
```

## Related Documentation

- [rpsd-transport documentation](../../packages/rpsd-transport/README.md)
- [rpsd-storage documentation](../../packages/rpsd-storage/README.md)
- [Kafka host scripts](../../host-scripts/README.md)
- [IngestProcessor API](../../packages/rpsd-transport/src/rpsd_transport/processors/README.md)

## Next Steps

1. **Explore Kafka UI**: Browse topics and messages at http://localhost:8080
2. **Customize forwarding**: Try both fatheavy and slimfast modes
3. **Add consumer logic**: Extend consumer.py with your processing logic
4. **Production deployment**: Replace filesystem storage with S3, use managed Kafka
5. **Add transformations**: Implement custom processing in IngestProcessor
6. **Monitor**: Set up Kafka consumer lag monitoring and alerting

## License

This example is part of the rpsd-commons project.

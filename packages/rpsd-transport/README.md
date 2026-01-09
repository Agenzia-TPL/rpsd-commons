# rpsd-transport

> **Note**: This package is being renamed from `rpsd-messaging` to `rpsd-transport` to better reflect its purpose of transporting data rather than just messaging.

A library for transporting data between services using various transport methods (carriers), with support for both inline and referenced data transfer.

## Overview

`rpsd-transport` provides a unified interface for sending and receiving data across different transport mechanisms, with built-in support for handling both small (fast/slim) and large (heavy/fat) data payloads.

### Key Concepts

#### Transport Methods (Carriers)

Transport is accomplished through **carriers** - pluggable implementations for different transport mechanisms:

- **HTTPCarrier**: HTTP-based transport for external systems (REST APIs)
- **DaprServiceCarrier**: Dapr service-to-service invocation (internal only)
- **DaprPubSubCarrier**: Dapr pub/sub messaging (internal only)

#### Message Modes

Data can be transported in two modes:

- **Fast (Slim)**: Small data embedded directly in the message payload
  - Fast to access (no additional fetch required)
  - Larger message size
  - Best for: < 1MB of data

- **Heavy (Fat)**: Large data stored externally and referenced by URL
  - Requires additional fetch to retrieve data
  - Smaller message size
  - Best for: > 1MB of data

Both term pairs (`fast`/`heavy` and `slim`/`fat`) can be used interchangeably in code and documentation.

#### Internal vs External Transport

- **Internal**: Systems sharing storage access (s3://, file:// URLs)
  - Can reference data directly in shared storage
  - More efficient for heavy data

- **External**: Systems without shared storage access
  - Must use HTTP URLs for heavy data
  - Sender exposes data via temporary HTTP endpoint

## Architecture

### Message Structure

Messages use Pydantic models for validation:

```python
from rpsd_transport.models import FastMessage, HeavyMessage

# Fast message (data inlined)
fast_msg = FastMessage(
    mode="fast",
    who="user123",
    what="document",
    data=b"small payload",
    content_type="application/json",
    filename="data.json"
)

# Heavy message (data referenced)
heavy_msg = HeavyMessage(
    mode="heavy",
    who="user123",
    what="document",
    where="s3://bucket/path/to/data",
    content_type="application/json",
    filename="large-data.json"
)
```

### HTTPCarrier API

```python
from rpsd_transport.carriers import HTTPCarrier

# Initialize carrier
carrier = HTTPCarrier(
    storage_provider=storage,  # rpsd-storage provider
    base_url="https://your-service.com"  # For generating temp URLs
)

# Send fast message (data inlined)
carrier.send_fast(
    recipient="https://external-system.com/webhook",
    data=small_payload,
    who="user123",
    what="document"
)

# Send heavy message (data by reference)
carrier.send_heavy(
    recipient="https://external-system.com/webhook",
    storage_url="s3://bucket/path/to/data",
    expose_ttl=3600,  # Data available for 1 hour
    who="user123",
    what="document"
)

# Receive messages (handles both fast and heavy)
response = await carrier.handle_receive(request)
```

### Error Handling

The library uses standard HTTP status codes for error responses:

- **200 OK**: Successfully received and processed
- **400 Bad Request**: Malformed message (invalid JSON, missing fields)
- **422 Unprocessable Entity**: Valid format but cannot process
  - Unreachable `where` URL
  - Invalid business logic
- **500 Internal Server Error**: Internal processing failure

Error responses include structured information:

```json
{
  "status": "failed",
  "error_code": "data_unreachable",
  "message": "Cannot fetch data from the provided URL",
  "details": {
    "where": "https://external.com/data"
  }
}
```

### Storage Integration

Heavy messages integrate with `rpsd-storage` for data persistence:

- **Receiving**: Automatically saves external data to internal storage
- **Sending**: Storage URL exposure depends on transport type:
  - **External transports** (HTTP): Must use HTTP URLs
    - S3: Generates presigned URLs (built-in TTL)
    - FS: Creates temporary FastAPI endpoints (manual TTL cleanup)
  - **Internal transports** (Dapr): Can use direct storage URLs
    - S3: Exposes `s3://` URLs directly (if shared access)
    - FS: Exposes `file://` URLs directly (if shared filesystem)

### FastAPI Integration

Two integration patterns available:

#### Option 1: Automatic Router

```python
from fastapi import FastAPI
from rpsd_transport.carriers import HTTPCarrier
from rpsd_transport.fastapi import create_transport_router

app = FastAPI()
carrier = HTTPCarrier()

# Mount automatic router
app.include_router(
    create_transport_router(carrier),
    prefix="/transport"
)
```

#### Option 2: Manual Integration

```python
from fastapi import FastAPI, Request
from rpsd_transport.carriers import HTTPCarrier

app = FastAPI()
carrier = HTTPCarrier()

@app.post("/custom/receive")
async def receive_data(request: Request):
    return await carrier.handle_receive(request)

@app.get("/custom/data/{temp_id}")
async def fetch_temp_data(temp_id: str):
    return await carrier.handle_temp_fetch(temp_id)
```

## Implementation Status

### Phase 1: Core Foundation  (In Progress)
- [x] Message models (Pydantic)
- [x] `BaseCarrier` abstract class
- [ ] `HTTPCarrier` - fast mode (send/receive)

### Phase 2: Heavy Data Support (TODO)
- [ ] Storage integration
- [ ] `HTTPCarrier.send_heavy()` with URL exposure
- [ ] `HTTPCarrier.handle_receive()` with auto-save
- [ ] Temporary route management + TTL cleanup

### Phase 3: FastAPI Integration (TODO)
- [ ] `create_transport_router()` helper
- [ ] Manual integration helpers
- [ ] Example application

### Phase 4: Dapr Carriers (TODO)
- [ ] `DaprServiceCarrier` implementation
- [ ] `DaprPubSubCarrier` implementation

## Configuration

Uses `rpsd-commons` config system for storage provider settings:

```python
# Example configuration (TODO: specific format TBD)
config = {
    "storage": {
        "type": "s3",  # or "fs"
        "bucket_name": "my-bucket",  # for S3
        # "base_path": "/storage"  # for FS
    }
}
```

## Development

This package follows the rpsd-commons development standards:

- Python 3.11+
- Package manager: `uv`
- Testing: `pytest`
- Linting/Formatting: `ruff`

### Common Commands

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest packages/rpsd-transport/tests/

# Format code
uv run ruff format packages/rpsd-transport/

# Lint code
uv run ruff check packages/rpsd-transport/
```

## Design Decisions

### Why "Carrier" Instead of "Transport"?

To avoid namespace collision with the package name (`rpsd-transport`), we use "carrier" as the code term for transport implementations while "transport method" remains the documentation term.

### Why Synchronous Send?

Initial implementation uses synchronous sends (wait for receiver response) for simplicity and immediate error feedback. Asynchronous/callback support may be added in future phases if needed.

### Why Always Save on Receive?

When receiving heavy data from external systems, the carrier always saves it to internal storage to:
- Ensure data persistence
- Remove dependency on external URL availability
- Enable sharing with other internal systems
- Maintain consistency with internal transport patterns

### Why 422 for Unreachable URLs?

Using `422 Unprocessable Entity` instead of `502 Bad Gateway` for unreachable `where` URLs prevents confusion with infrastructure failures (load balancers, proxies) while clearly indicating a client-side error.

## License

[License information to be added]

## Related Packages

- **rpsd-storage**: Storage abstraction layer for S3, filesystem, and HTTP
- **rpsd-commons**: Common utilities and configuration

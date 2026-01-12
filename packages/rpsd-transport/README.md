# rpsd-transport

A library for transporting data between services using various transport methods (carriers), with support for both inline and referenced data transfer.

## Overview

`rpsd-transport` provides a unified interface for sending and receiving data across different transport mechanisms, with built-in support for handling both small (slim/fast) and large (fat/heavy) data payloads.

### Key Concepts

#### Transport Methods (Carriers)

Transport is accomplished through **carriers** - pluggable implementations for different transport mechanisms:

- **HTTPCarrier**: HTTP-based transport for external systems (REST APIs)
- **DaprServiceCarrier**: Dapr service-to-service invocation (internal only) - TODO
- **DaprPubSubCarrier**: Dapr pub/sub messaging (internal only) - TODO

#### Message Modes

Data can be transported in two modes, determined by the presence of the `where` field:

- **Fast (Slim)**: Small data embedded directly in the message payload
  - No `where` field in metadata
  - Fast to access (no additional fetch required)
  - Larger message size
  - Best for: < 1MB of data

- **Heavy (Fat)**: Large data stored externally and referenced by URL
  - Has `where` field in metadata pointing to content URL
  - Requires additional fetch to retrieve data
  - Smaller message size
  - Best for: > 1MB of data

Both terms can be used interchangeably:
- `fast` aka `slim`
- `heavy` aka `fat`

#### Metadata Organization

Messages can organize metadata in two ways:

- **Inline**: Metadata embedded in JSON body with nested structure
- **Outline**: Metadata in HTTP headers or query parameters, content in body

#### Internal vs External Transport Scopes

- **Internal**: Systems sharing storage access (s3://, file:// URLs)
  - Can reference data directly in shared storage
  - More efficient for fat/heavy data

- **External**: Systems without shared storage access
  - Must use HTTP URLs for fat/heavy data
  - Sender exposes data via temporary HTTP endpoint

## Architecture

### Message Models

The new model structure uses `MessageMetadata` and `TransportMessage`:

```python
from rpsd_transport import MessageMetadata, TransportMessage

# Slim/Fast message (no 'where' = slim/fast mode)
metadata = MessageMetadata(
    who="user123",
    what="document",
    content_type="application/json",
    filename="data.json"
)
message = TransportMessage(metadata=metadata, content=b"small payload")
print(message.is_slimfast)  # True

# Fat/Heavy message (has 'where' = fat/heavy mode)
metadata = MessageMetadata(
    who="user123",
    what="document",
    where="s3://bucket/path/to/data",
    content_type="application/json"
)
message = TransportMessage(metadata=metadata)
print(message.is_fatheavy)  # True
```

### Inline Metadata Format

For inline metadata, use JSON with nested structure:

```json
{
  "metadata": {
    "who": "user123",
    "what": "document",
    "content_type": "application/xml"
  },
  "content": "SGVsbG8gV29ybGQh"
}
```

The `content` field should contain base64-encoded binary data for slim/fast messages.

For heavy messages, include `where` in metadata and omit `content`:

```json
{
  "metadata": {
    "who": "user123",
    "what": "document",
    "where": "https://storage.example.com/file.xml"
  }
}
```

### Outline Metadata Format

For outline metadata, use HTTP headers or query parameters:

| Metadata | Query Parameter | HTTP Header (Current) | HTTP Header (Legacy) |
|----------|-----------------|----------------------|---------------------|
| who      | `who`           | `X-RPSD-WHO`         | `X-RAPS-INGEST_WHO` |
| what     | `what`          | `X-RPSD-WHAT`        | `X-RAPS-INGEST_WHAT`|
| where    | `where`         | `X-RPSD-WHERE`       | `X-RAPS-INGEST_WHERE`|

**Important**: Each metadata value can be specified by EITHER header OR query parameter, not both. Specifying the same value in both is an error.

Content can be provided as:
- Raw request body
- Multipart/form-data attachment

### HTTPCarrier API

```python
from rpsd_transport.carriers import HTTPCarrier

# Initialize carrier
carrier = HTTPCarrier(
    base_url="https://your-service.com"  # For generating temp URLs
)

# Send fast message (inline metadata format)
carrier.send_slimfast(
    recipient="https://external-system.com/webhook",
    data=small_payload,
    who="user123",
    what="document"
)

# Send heavy message (data by reference)
carrier.send_fatheavy(
    recipient="https://external-system.com/webhook",
    storage_url="s3://bucket/path/to/data",
    expose_ttl=3600,  # Data available for 1 hour
    who="user123",
    what="document"
)

# Receive messages (handles both inline and outline metadata)
response = await carrier.handle_receive(request)
```

### Compression Support

Content can be compressed with GZIP or ZIP. Compression is auto-detected:
- GZIP: Magic bytes `\x1f\x8b` or `.gz` filename extension
- ZIP: `.zip` filename extension (extracts first file)

```python
from rpsd_transport import decompress_content
import gzip

compressed = gzip.compress(b"Hello, World!")
decompressed = decompress_content(compressed)  # Auto-detects GZIP
```

### Error Handling

The library uses standard HTTP status codes for error responses:

- **200 OK**: Successfully received and processed
- **400 Bad Request**: Malformed message (invalid JSON, missing fields, duplicate metadata)
- **422 Unprocessable Entity**: Valid format but cannot process
  - Unreachable `where` URL
  - Invalid business logic
- **500 Internal Server Error**: Internal processing failure
- **501 Not Implemented**: Heavy mode storage (Phase 2)

Error responses include structured information:

```json
{
  "status": "failed",
  "error_code": "duplicate_metadata",
  "message": "Cannot specify 'who' in both query parameter and header"
}

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

### Phase 1: Core Foundation (Complete)
- [x] Message models (Pydantic) - `MessageMetadata`, `TransportMessage`
- [x] `BaseCarrier` abstract class
- [x] `HTTPCarrier` - slim/fast mode (send/receive)
- [x] Inline metadata organization support
- [x] Outline metadata organization support
- [x] Compression support (GZIP/ZIP)
- [x] Legacy header support (`X-RAPS-INGEST_*`)

### Phase 2: Fat/Heavy Data Support (TODO)
- [ ] Storage integration (rpsd-storage)
- [ ] `HTTPCarrier.send_fatheavy()` with URL exposure
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

Uses pydantic-settings for configuration:

```python
from rpsd_transport import TransportSettings

settings = TransportSettings()
# Environment variables: TRANSPORT__API_KEY
```

## Development

This package follows the rpsd-commons development standards:

- Python 3.13+
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

### Why No Explicit Mode Field?

The message mode (slim/fast vs fat/heavy) is determined by the presence of the `where` field:
- If `where` is present → Fat/Heavy message
- If `where` is absent → Slim/Fast message

This eliminates redundancy and potential inconsistency.

### Why Nested Metadata Structure?

The inline JSON format uses `{"metadata": {...}, "content": "..."}` because:
1. Clear separation of transport concerns (metadata) from payload (content)
2. Better alignment with CloudEvents which wraps data similarly
3. More extensible - adding metadata fields won't conflict with content

### Why "Carrier" Instead of "Transport"?

To avoid namespace collision with the package name (`rpsd-transport`), we use "carrier" as the code term for transport implementations.

### Why Always Save on Receive?

When receiving fat/heavy data from external systems, the carrier will save it to internal storage to:
- Ensure data persistence
- Remove dependency on external URL availability
- Enable sharing with other internal systems

### Why 422 for Unreachable URLs?

Using `422 Unprocessable Entity` instead of `502 Bad Gateway` for unreachable `where` URLs prevents confusion with infrastructure failures (load balancers, proxies) while clearly indicating a client-side error.

## License

[License information to be added]

## Related Packages

- **rpsd-storage**: Storage abstraction layer for S3, filesystem, and HTTP

# FastAPI Ingest Example

A modern FastAPI application demonstrating the use of HTTPCarrier from `rpsd-transport` and storage providers from `rpsd-storage`.

## Features

- **HTTPCarrier Integration**: Uses `HTTPCarrier.receive()` for automatic message parsing
- **Storage Abstraction**: Supports both filesystem and S3 storage via configuration
- **Dual Metadata Formats**: Handles both inline (JSON) and outline (headers/query) metadata
- **API Key Authentication**: Bearer/Token authentication with configurable keys
- **Hook-Based Architecture**: Uses `received()` hook for clean storage integration

## Installation

From the workspace root:

```bash
uv sync
```

This will install all workspace dependencies including `rpsd-transport`, `rpsd-storage`, and FastAPI.

## Configuration

### Option 1: Using .env File (Recommended)

Copy the example file and configure your settings:

```bash
cd examples/fastapi_ingest_app
cp .env.example .env
```

Edit `.env` with your settings:

```bash
APP__TRANSPORT__API_KEY=your-secret-key-here
APP__STORAGE__PROVIDER=fs
APP__STORAGE__FS__BASE_PATH=/tmp/rpsd-storage
```

**Important**: The `.env` file must be in your current working directory when
running the app. Always run the app from the example directory:

```bash
cd examples/fastapi_ingest_app
uv run fastapi-ingest-app
```

Alternatively, use `uv run --directory` from the workspace root:

```bash
# From workspace root
uv run --directory examples/fastapi_ingest_app fastapi-ingest-app
```

### Option 2: Environment Variables

Export variables directly in your shell:

```bash
# Required: API key for authentication
export APP__TRANSPORT__API_KEY=your-secret-key

# Required: Storage provider (fs or s3)
export APP__STORAGE__PROVIDER=fs

# For filesystem storage
export APP__STORAGE__FS__BASE_PATH=/tmp/rpsd-storage

# For S3 storage
export APP__STORAGE__PROVIDER=s3
export APP__STORAGE__S3__BUCKET_NAME=my-bucket
```

See [.env.example](.env.example) for all available configuration options.

## Running the Application

**Important**: Always run from the example directory to ensure `.env` file is
loaded correctly.

### Recommended: From the Example Directory

```bash
cd examples/fastapi_ingest_app
uv run fastapi-ingest-app
```

### Alternative: From Workspace Root

If you need to run from the workspace root, use `--directory`:

```bash
uv run --directory examples/fastapi_ingest_app fastapi-ingest-app
```

This ensures the working directory is set correctly for `.env` file loading.

### Other Run Options

```bash
# Using the module directly
cd examples/fastapi_ingest_app
uv run python -m fastapi_ingest_app.main

# With custom uvicorn options (development mode with auto-reload)
cd examples/fastapi_ingest_app
uv run uvicorn fastapi_ingest_app.main:app --host 0.0.0.0 --port 8000 --reload
```

The application will start on `http://localhost:8000`.

## API Endpoints

### POST /ingest

Receives and stores data with metadata.

**Authentication**: Required via `Authorization: Bearer <token>` or `X-API-Key: <token>`

**Metadata Formats Supported**:

#### 1. Outline Format (Headers)

Send metadata in headers, content in body:

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Authorization: Bearer your-secret-key" \
  -H "X-RPSD-WHO: alice" \
  -H "X-RPSD-WHAT: test-data" \
  -H "Content-Type: application/json" \
  -d '{"example": "data"}'
```

#### 2. Outline Format (Query Parameters)

Send metadata in query params, content in body:

```bash
curl -X POST "http://localhost:8000/ingest?who=alice&what=test-data" \
  -H "Authorization: Bearer your-secret-key" \
  -H "Content-Type: application/json" \
  -d '{"example": "data"}'
```

#### 3. Inline Format (JSON)

Send metadata and content together in JSON body:

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Authorization: Bearer your-secret-key" \
  -H "Content-Type: application/json" \
  -d '{
    "metadata": {
      "who": "alice",
      "what": "test-data",
      "content_type": "application/json"
    },
    "content": "eyJleGFtcGxlIjogImRhdGEifQ=="
  }'
```

Note: `content` field should be base64-encoded.

#### 4. Heavy Message (URL Reference)

For large files, reference external URL:

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Authorization: Bearer your-secret-key" \
  -H "X-RPSD-WHO: alice" \
  -H "X-RPSD-WHAT: large-file" \
  -H "X-RPSD-WHERE: https://example.com/large-file.zip"
```

The carrier will fetch the content from the URL and store it.

**Response**:

```json
{
  "success": true,
  "message": "Content received and stored",
  "storage_url": "file:///tmp/rpsd-storage/alice/test-data/uuid.json",
  "metadata": {
    "who": "alice",
    "what": "test-data",
    "object_id": "uuid.json",
    "content_type": "application/json",
    "content_length": 123
  }
}
```

### GET /health

Health check endpoint:

```bash
curl http://localhost:8000/health
```

Response:

```json
{
  "status": "healthy",
  "storage_provider": "fs"
}
```

## Metadata Parameters

### Required

- **who**: Entity identifier (alphanumeric, dash, underscore only)
- **what**: Content type/category (alphanumeric, dash, underscore only)

### Optional

- **where**: URL for heavy messages (carrier fetches content)
- **content_type**: MIME type (default: `application/octet-stream`)
- **filename**: Original filename

## Storage

### Filesystem Storage

Content is stored at:
```
{base_path}/{who}/{what}/{uuid}.{extension}
```

Metadata is stored in a sidecar file:
```
{base_path}/{who}/{what}/{uuid}.{extension}.meta
```

Example:
```
/tmp/rpsd-storage/alice/test-data/550e8400-e29b-41d4-a716-446655440000.json
/tmp/rpsd-storage/alice/test-data/550e8400-e29b-41d4-a716-446655440000.json.meta
```

### S3 Storage

Content is stored at:
```
s3://{bucket}/{who}/{what}/{uuid}.{extension}
```

Metadata is stored in S3 object metadata.

Example:
```
s3://my-bucket/alice/test-data/550e8400-e29b-41d4-a716-446655440000.json
```

## Testing

See [test-requests.sh](test-requests.sh) for comprehensive test examples.

## Architecture

This example demonstrates the carrier pattern from `rpsd-transport`:

1. **HTTPCarrier.receive()**: Automatically parses incoming requests
   - Detects metadata format (inline vs outline)
   - Validates metadata (who, what)
   - Decompresses content if needed
   - Returns TransportMessage object

2. **StorageHTTPCarrier.received()**: Hook for storage integration
   - Fetches heavy content from URLs if needed
   - Saves content using configured storage provider
   - Stores URL and metadata for response

3. **Storage Providers**: Abstracted storage interface
   - FSStorageProvider for filesystem
   - S3StorageProvider for AWS S3
   - Configurable via settings

## Error Handling

- **401 Unauthorized**: Invalid or missing API key
- **400 Bad Request**: Missing or invalid metadata
- **500 Internal Server Error**: Storage or fetch failures

## Development

Format and lint code:

```bash
uv run ruff format examples/fastapi_ingest_app/src/
uv run ruff check --fix examples/fastapi_ingest_app/src/
```

Run the app in development mode with auto-reload:

```bash
cd examples/fastapi_ingest_app
uv run uvicorn fastapi_ingest_app.main:app --reload
```

## Related

- Legacy implementation: [packages/rpsd-transport/src/legacy/ingest-fastapi.py](../../packages/rpsd-transport/src/legacy/ingest-fastapi.py)
- HTTPCarrier: `packages/rpsd-transport/src/rpsd_transport/carriers/http.py`
- Storage providers: `packages/rpsd-storage/src/rpsd_storage/`

# rpsd-storage

Storage utilities for the rpsd-commons workspace. Provides pluggable storage
providers for S3, local filesystem, and HTTP.

## Configuration

Storage is configured through `StorageSettings`, which reads environment variables
prefixed with `STORAGE__` (double-underscore as delimiter).

| Variable | Default | Description |
|---|---|---|
| `STORAGE__PROVIDER` | `fs` | Active provider: `s3`, `fs`, or `http` |
| `STORAGE__COMPARE_BEFORE_SAVE` | `false` | Skip save when content is unchanged |
| `STORAGE__S3__BUCKET_NAME` | — | S3 bucket (required when provider is `s3`) |
| `STORAGE__S3__AWS_ACCESS_KEY_ID` | — | AWS key ID (optional; falls back to boto3 chain) |
| `STORAGE__S3__AWS_SECRET_ACCESS_KEY` | — | AWS secret (optional) |
| `STORAGE__S3__AWS_SESSION_TOKEN` | — | AWS session token (optional, for temporary creds) |
| `STORAGE__S3__REGION_NAME` | — | AWS region (optional) |
| `STORAGE__S3__ENDPOINT_URL` | — | Custom endpoint for LocalStack/MinIO (optional) |
| `STORAGE__FS__BASE_PATH` | `/tmp/ingested` | Root directory for filesystem provider |
| `STORAGE__HTTP__TIMEOUT` | `30.0` | Request timeout in seconds for HTTP provider |

Copy `.env.example` to `.env` and fill in the values you need.

`StorageSettings` reads only actual environment variables — it does **not** auto-load any
`.env` file. Load the file via the parent settings class or set the variables in the shell
before constructing `StorageSettings`:

```python
from rpsd_storage.settings import StorageSettings

# rely on environment variables already in the shell
settings = StorageSettings()
```

When `StorageSettings` is embedded inside a parent settings class (e.g. `AppSettings`),
the parent is responsible for loading the `.env` file and passing down the nested values.

## Running tests

### Mocked tests (default)

All tests run against mocked infrastructure by default — no AWS account or
running services needed.

```bash
uv run pytest packages/rpsd-storage/
```

### Live S3 tests

A separate suite (`-m live_s3`) runs the same logic against a real S3-compatible
endpoint to verify behaviour on actual infrastructure. These tests are **skipped
automatically** unless `STORAGE__S3__BUCKET_NAME` is set, so they never run in
normal CI.

The target bucket must already exist. Test objects are cleaned up on teardown;
the bucket itself is never created or deleted.

**Against real AWS** — copy `tests/.env.example` to `packages/rpsd-storage/tests/.env`
and fill in your values. Do **not** set `STORAGE__S3__ENDPOINT_URL`; boto3 will connect
to the real AWS endpoint automatically.

```
# packages/rpsd-storage/tests/.env
STORAGE__S3__BUCKET_NAME=my-existing-bucket
STORAGE__S3__AWS_ACCESS_KEY_ID=AKIA...
STORAGE__S3__AWS_SECRET_ACCESS_KEY=...
STORAGE__S3__REGION_NAME=eu-west-1
```

If you omit the credential variables, boto3 falls back to the standard AWS
chain (IAM role, `~/.aws/credentials`, environment variables, etc.).

```bash
uv run pytest packages/rpsd-storage/ -m live_s3 -v
```

**Against LocalStack or MinIO** — same variables, but also set `ENDPOINT_URL`:

```bash
STORAGE__S3__ENDPOINT_URL=http://localhost:4566 \
STORAGE__S3__BUCKET_NAME=my-test-bucket \
STORAGE__S3__AWS_ACCESS_KEY_ID=test \
STORAGE__S3__AWS_SECRET_ACCESS_KEY=test \
STORAGE__S3__REGION_NAME=us-east-1 \
  uv run pytest packages/rpsd-storage/ -m live_s3 -v
```

To run both mocked and live tests together:

```bash
uv run pytest packages/rpsd-storage/ -v
```

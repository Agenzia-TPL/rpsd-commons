# rpsd-storage

Storage utilities for the rpsd-commons workspace. Provides pluggable storage
providers for S3, local filesystem, and HTTP.

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

**Against real AWS** — set `BUCKET_NAME` and any credentials you want to use
explicitly. Do **not** set `STORAGE__S3__ENDPOINT_URL`; boto3 will connect to
the real AWS endpoint automatically.

```
# .env
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

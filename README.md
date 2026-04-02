# rpsd-commons

Common libraries for the Rapsodia project, organized as a uv workspace with multiple packages.

## Packages

- **[rpsd-storage](packages/rpsd-storage/)** - Storage providers (S3, Filesystem, HTTP)
- **[rpsd-transport](packages/rpsd-transport/)** - Data transport utilities
- **[rpsd-flow](packages/rpsd-flow/)** - Prefect Flow and Task utilities

## Installation

This is a workspace project. Install all packages:

```bash
uv sync
```

Or install specific packages in your application:

```bash
uv add rpsd-storage
uv add rpsd-transport
uv add rpsd-flow      # optional, for Prefect-based workflows
```

## Configuration

All packages use **pydantic-settings** for type-safe configuration.

### Environment Variables

Settings use double underscore (`__`) as the nested delimiter:

```bash
# Storage settings
STORAGE__PROVIDER=fs                    # or "s3" or "http"
STORAGE__FS__BASE_PATH=/tmp/storage
STORAGE__S3__BUCKET_NAME=my-bucket      # required when STORAGE__PROVIDER=s3
STORAGE__HTTP__TIMEOUT=30.0

# Transport settings
TRANSPORT__API_KEY=your-secret-key
```

### .env File

Copy `.env.example` to `.env` and customize:

```bash
cp .env.example .env
```

### Usage Options

#### Option 1: Use Individual Package Settings (Recommended)

```python
from rpsd_storage.settings import StorageSettings
from rpsd_storage import get_storage_provider

# Settings load from environment automatically
settings = StorageSettings()
provider = get_storage_provider(settings)
```

#### Option 2: Custom Application Settings

```python
from rpsd_storage.settings import StorageSettings
from pydantic_settings import BaseSettings
from pydantic import Field

class MyAppSettings(BaseSettings):
    storage: StorageSettings = Field(default_factory=StorageSettings)
    app_name: str = "MyApp"
    debug: bool = False

settings = MyAppSettings()
provider = get_storage_provider(settings.storage)
```

## Development

### Setup

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Format code
uv run ruff format

# Lint code
uv run ruff check --fix
```

### Project Structure

```
rpsd-commons/
├── packages/               # Workspace packages
│   ├── rpsd-storage/
│   ├── rpsd-transport/
│   ├── rpsd-flow/
├── src/rpsd_commons/       # Workspace root
├── pyproject.toml          # Workspace configuration
└── .env.example            # Environment variable template
```

### Testing

Run all tests:
```bash
uv run pytest
```

Run tests for a specific package:
```bash
uv run pytest packages/rpsd-storage/tests/
```

Run tests with markers:
```bash
uv run pytest -m "not s3"     # Skip S3 tests
uv run pytest -m integration   # Only integration tests
```

## Versioning

All packages in this workspace share the same version number (**lock-step versioning**). When you bump the version, update the `version` field in every `pyproject.toml` (root + all `packages/*/pyproject.toml`).

On merge to `main`, CI automatically creates a git tag `vX.Y.Z` matching the version. The tag is what consuming repositories reference.

**Release workflow:**

1. Create a branch: `git checkout -b release/vX.Y.Z`
2. Bump `version` in all `pyproject.toml` files
3. Commit, push, open a PR to `main`
4. Merge — CI creates the tag automatically

## Using in other repositories

Consuming repositories reference individual packages via `[tool.uv.sources]` with local paths pointing to a sibling clone:

```toml
# pyproject.toml of the consuming repo
[project]
dependencies = [
    "rpsd-transport[kafka,rabbitmq]",
    "rpsd-storage",
    "rpsd-flow",
]

[tool.uv.sources]
rpsd-transport = { path = "../rpsd-commons/packages/rpsd-transport", editable = true }
rpsd-storage = { path = "../rpsd-commons/packages/rpsd-storage", editable = true }
rpsd-flow = { path = "../rpsd-commons/packages/rpsd-flow", editable = true }
```

In CI, check out rpsd-commons alongside your repository — the relative paths resolve identically:

```yaml
steps:
  - name: Check out my-service
    uses: actions/checkout@v4
    with:
      path: my-service

  - name: Check out rpsd-commons
    uses: actions/checkout@v4
    with:
      repository: Agenzia-TPL/rpsd-commons
      path: rpsd-commons
```

## Package Details

### rpsd-storage

Storage providers for saving/loading data:
- **S3Provider**: AWS S3 storage
- **FSProvider**: Local filesystem storage
- **HTTPProvider**: HTTP URL-based storage (read-only)

See [rpsd-storage README](packages/rpsd-storage/README.md) for details.

### rpsd-transport

Data transport utilities for receiving/sending data through:
- HTTP APIs (FastAPI-based)
- PubSub

See [rpsd-transport README](packages/rpsd-transport/README.md) for details.

### rpsd-flow

**Optional** Prefect integration package providing decorator factories and utilities
to define, serve, and execute Prefect flows and tasks within the rpsd-commons ecosystem.

- Flow and task decorator factories with rpsd-transport integration
- `serve_flows()` / `serve_tasks()` for long-running workers
- `run_flow()` / `run_flow_async()` for one-shot execution
- `subprocess_task` decorator for wrapping CLI commands as Prefect tasks

See [rpsd-flow README](packages/rpsd-flow/README.md) for details.

## Examples

This project includes two types of examples:

### Package Examples (`packages/*/examples/`)

Simple, educational Python scripts demonstrating individual package features:

- **[rpsd-storage examples](packages/rpsd-storage/examples/)** - Storage provider usage, metadata handling, and advanced features
  - `01_getting_started.py` - Basic storage operations
  - `02_basic_usage.py` - Common usage patterns
  - `03_metadata_and_types.py` - Working with metadata
  - And more...

Run package examples:
```bash
uv run python packages/rpsd-storage/examples/01_getting_started.py
```

### Integration Examples (`examples/`)

Full applications demonstrating multi-package integration and real-world usage:

- **[FastAPI Ingest App](examples/fastapi_ingest_app/)** - Complete FastAPI application using rpsd-transport, rpsd-storage and rpsd-flow
  - HTTP carrier integration
  - Storage abstraction (filesystem and S3)
  - Authentication and configuration
  - Dual metadata formats (inline and outline)

Run integration examples:
```bash
uv run fastapi-ingest-app
```

Each example includes its own README with detailed documentation.

## Migration from config.py

The old dictionary-based `config.py` has been replaced with pydantic-settings:

**Old:**
```python
from rpsd_commons.config import config
provider_type = config["storage"]["provider"]
```

**New:**
```python
from rpsd_storage.settings import StorageSettings
settings = StorageSettings()
provider_type = settings.provider
```

Benefits:
- Type safety with Pydantic validation
- IDE autocomplete support
- Better error messages
- Composable settings per package
- No global state

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `uv run pytest`
5. Format code: `uv run ruff format`
6. Submit a pull request

## License

This project is licensed under the **BSD 3-Clause License** (SPDX: `BSD-3-Clause`).

Copyright (c) 2026, AGENZIA TPL BACINO CITTA' METROPOLITANA MILANO,
MONZA E BRIANZA, LODI, PAVIA

See the [LICENSE](LICENSE) file for the full license text.

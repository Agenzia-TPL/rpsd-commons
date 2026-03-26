# rpsd-commons

Common libraries for the Rapsodia project, organized as a uv workspace with multiple packages.

## Packages

- **[rpsd-storage](packages/rpsd-storage/)** - Storage providers (S3, Filesystem, HTTP)
- **[rpsd-transport](packages/rpsd-transport/)** - Data transport utilities
- **[rpsd-settings](packages/rpsd-settings/)** - Composable settings system (optional convenience package)

## Installation

This is a workspace project. Install all packages:

```bash
uv sync
```

Or install specific packages in your application:

```bash
uv add rpsd-storage
uv add rpsd-transport
uv add rpsd-settings  # optional
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

#### Option 2: Use RpsdSettings (All Packages)

```python
from rpsd_settings import RpsdSettings
from rpsd_storage import get_storage_provider

settings = RpsdSettings()
provider = get_storage_provider(settings.storage)
```

#### Option 3: Custom Application Settings

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
│   └── rpsd-settings/
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

### rpsd-settings

**Optional** convenience package that composes settings from all packages. Applications can use this for quick setup or compose their own settings directly from individual packages.

See [rpsd-settings README](packages/rpsd-settings/README.md) for details.

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

- **[FastAPI Ingest App](examples/fastapi_ingest_app/)** - Complete FastAPI application using rpsd-transport and rpsd-storage
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

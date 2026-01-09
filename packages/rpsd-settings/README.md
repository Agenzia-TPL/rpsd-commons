# rpsd-settings

**OPTIONAL** convenience package for composing settings from all rpsd-commons packages.

## Overview

This package provides `RpsdSettings`, a class that composes settings from all rpsd-commons packages (`rpsd-storage`, `rpsd-transport`, etc.) for convenience.

**Important:** You don't have to use this package! Each rpsd package defines its own settings class, and applications can compose only the settings they need directly.

## Installation

```bash
uv add rpsd-settings
```

This will automatically install rpsd-storage and rpsd-transport as dependencies.

## Usage

### Option 1: Use RpsdSettings (All Packages)

```python
from rpsd_settings import RpsdSettings
from rpsd_storage import get_storage_provider

settings = RpsdSettings()
provider = get_storage_provider(settings.storage)
```

### Option 2: Compose Only What You Need (Recommended)

```python
from rpsd_storage.settings import StorageSettings
from rpsd_storage import get_storage_provider
from pydantic_settings import BaseSettings
from pydantic import Field

class MyAppSettings(BaseSettings):
    storage: StorageSettings = Field(default_factory=StorageSettings)
    my_custom_field: str = "value"

settings = MyAppSettings()
provider = get_storage_provider(settings.storage)
```

### Option 3: Inherit from RpsdSettings

```python
from rpsd_settings import RpsdSettings

class MyAppSettings(RpsdSettings):
    my_custom_field: str = "value"
    debug_mode: bool = False

settings = MyAppSettings()
# Access rpsd settings
provider = get_storage_provider(settings.storage)
# Access your custom fields
if settings.debug_mode:
    print("Debug mode enabled")
```

## Environment Variables

Settings use double underscore (`__`) as the nested delimiter:

```bash
# Storage settings
STORAGE__PROVIDER=s3                    # or "fs" or "http"
STORAGE__S3__BUCKET_NAME=my-bucket
STORAGE__FS__BASE_PATH=/tmp/storage
STORAGE__HTTP__TIMEOUT=30.0

# Transport settings
TRANSPORT__API_KEY=your-secret-key
```

## .env File Support

Create a `.env` file in your project root:

```bash
# .env
STORAGE__PROVIDER=fs
STORAGE__FS__BASE_PATH=/app/storage
TRANSPORT__API_KEY=dev-key-12345
```

Settings will automatically load from this file.

## Validation

Settings include validation rules:

- When `STORAGE__PROVIDER=s3`, `STORAGE__S3__BUCKET_NAME` is required
- Invalid provider types are rejected
- Type checking ensures correct data types

```python
from rpsd_settings import RpsdSettings

# This will raise ValidationError - S3 requires bucket_name
import os
os.environ["STORAGE__PROVIDER"] = "s3"
# os.environ["STORAGE__S3__BUCKET_NAME"] not set
settings = RpsdSettings()  # ValidationError!
```

## Package Settings

Each rpsd package defines its own settings class:

### StorageSettings (from rpsd-storage)

```python
from rpsd_storage.settings import StorageSettings

settings = StorageSettings()
# Env vars: STORAGE__PROVIDER, STORAGE__S3__BUCKET_NAME, etc.
```

### TransportSettings (from rpsd-transport)

```python
from rpsd_transport.settings import TransportSettings

settings = TransportSettings()
# Env vars: TRANSPORT__API_KEY
```

## Why is this package optional?

- **Lightweight apps**: If you only need storage, just use `rpsd-storage` directly
- **Custom composition**: You might want different settings organization
- **Flexibility**: Applications can choose their own architecture
- **No lock-in**: Each package works independently

## Architecture

```
rpsd-storage (defines StorageSettings)
    ↓
rpsd-transport (defines TransportSettings, uses rpsd-storage)
    ↓
rpsd-settings (composes Storage + Transport settings) ← OPTIONAL
    ↓
Your Application (use RpsdSettings OR compose your own)
```

## Examples

### Example 1: Minimal Storage-Only App

```python
# No need for rpsd-settings!
from rpsd_storage.settings import StorageSettings
from rpsd_storage import get_storage_provider

settings = StorageSettings()
provider = get_storage_provider(settings)
```

### Example 2: Full-Featured App with Custom Settings

```python
from rpsd_settings import RpsdSettings
from pydantic_settings import BaseSettings

class MyAppSettings(RpsdSettings):
    app_name: str = "MyApp"
    debug: bool = False
    max_retries: int = 3

settings = MyAppSettings()
# Use rpsd settings
storage = get_storage_provider(settings.storage)
# Use custom settings
print(f"Running {settings.app_name} (debug={settings.debug})")
```

### Example 3: Custom Composition

```python
from rpsd_storage.settings import StorageSettings
from pydantic_settings import BaseSettings
from pydantic import Field

# Only include storage, skip transport
class MyAppSettings(BaseSettings):
    storage: StorageSettings = Field(default_factory=StorageSettings)
    database_url: str = "postgresql://localhost/mydb"

settings = MyAppSettings()
```

## See Also

- [rpsd-storage](../rpsd-storage/README.md) - Storage providers (S3, FS, HTTP)
- [rpsd-transport](../rpsd-transport/README.md) - Data transport utilities

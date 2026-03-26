# SPDX-License-Identifier: BSD-3-Clause
# Copyright (C) 2026 AGENZIA TPL BACINO CITTA' METROPOLITANA MILANO,
# MONZA E BRIANZA, LODI, PAVIA
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from rpsd_storage.settings import StorageSettings
from rpsd_transport.settings import TransportSettings


class RpsdSettings(BaseSettings):
    """
    **OPTIONAL** convenience class for composing all rpsd-commons package settings.

    Each package defines its own settings class (StorageSettings, TransportSettings,
    etc.). This class simply composes them together for convenience and serves as
    documentation.

    **You don't have to use this class!** Applications can directly compose only the
    package settings they need.

    Usage Examples:
    ===============

    Option 1 - Use RpsdSettings (all packages):
        from rpsd_settings import RpsdSettings
        from rpsd_storage import get_storage_provider

        settings = RpsdSettings()
        provider = get_storage_provider(settings.storage)

    Option 2 - Compose only what you need (recommended for lightweight apps):
        from rpsd_storage.settings import StorageSettings
        from rpsd_storage import get_storage_provider
        from pydantic_settings import BaseSettings
        from pydantic import Field

        class MyAppSettings(BaseSettings):
            storage: StorageSettings = Field(default_factory=StorageSettings)
            my_field: str = "value"

        settings = MyAppSettings()
        provider = get_storage_provider(settings.storage)

    Option 3 - Inherit from RpsdSettings:
        from rpsd_settings import RpsdSettings

        class MyAppSettings(RpsdSettings):
            my_field: str = "value"

        settings = MyAppSettings()
        provider = get_storage_provider(settings.storage)

    Environment Variables:
    ======================
    Uses double underscore delimiter:
    - STORAGE__PROVIDER=s3
    - STORAGE__S3__BUCKET_NAME=my-bucket
    - STORAGE__FS__BASE_PATH=/tmp/storage
    - STORAGE__HTTP__TIMEOUT=30.0
    - TRANSPORT__API_KEY=secret-key
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Import settings from each package
    # Direct imports work fine - no circular dependencies since these are settings
    storage: StorageSettings = Field(default_factory=StorageSettings)
    transport: TransportSettings = Field(default_factory=TransportSettings)

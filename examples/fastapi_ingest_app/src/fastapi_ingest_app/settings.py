"""
Unified application settings combining transport and storage configuration.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict

from rpsd_storage.settings import StorageSettings
from rpsd_transport.settings import TransportSettings


class AppSettings(BaseSettings):
    """
    Unified application settings.

    Configuration via environment variables:
        APP__TRANSPORT__API_KEY=secret123
        APP__STORAGE__PROVIDER=fs
        APP__STORAGE__FS__BASE_PATH=/tmp/storage
        APP__STORAGE__S3__BUCKET_NAME=my-bucket
    """

    model_config = SettingsConfigDict(
        env_prefix="APP__",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    transport: TransportSettings = TransportSettings()
    storage: StorageSettings = StorageSettings()

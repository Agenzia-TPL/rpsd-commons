from rpsd_storage.providers.base import StorageProvider
from rpsd_storage.providers.fs import FSStorageProvider
from rpsd_storage.providers.http import HTTPStorageProvider
from rpsd_storage.providers.s3 import S3StorageProvider
from rpsd_storage.settings import StorageSettings
from rpsd_storage.utils import flip_uuid as flip_uuid
from rpsd_storage.utils import generate_object_id as generate_object_id


def get_storage_provider(settings: StorageSettings | None = None):
    """
    Returns a storage provider based on settings.

    Args:
        settings: StorageSettings instance. If None, creates default settings
            from environment variables.

    Returns:
        StorageProvider instance (S3, FS, or HTTP)

    Raises:
        ValueError: If provider type is unknown
    """
    if settings is None:
        settings = StorageSettings()

    cbs = settings.compare_before_save
    if settings.provider == "s3":
        return S3StorageProvider(
            settings.s3.bucket_name,
            compare_before_save=cbs,
        )
    elif settings.provider == "fs":
        return FSStorageProvider(
            settings.fs.base_path,
            compare_before_save=cbs,
        )
    elif settings.provider == "http":
        return HTTPStorageProvider(settings.http.timeout)
    else:
        raise ValueError(f"Unknown storage provider: {settings.provider}")


# Module-level singleton for backward compatibility
# Applications should use get_storage_provider() with explicit settings instead
storage_provider = get_storage_provider()

# Export static methods for convenience
load_from_url = StorageProvider.load_from_url
load_from_parts = StorageProvider.load_from_parts

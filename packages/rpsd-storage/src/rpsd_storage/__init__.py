from rpsd_commons.config import config

from rpsd_storage.fs import FSStorageProvider
from rpsd_storage.provider import StorageProvider
from rpsd_storage.s3 import S3StorageProvider


def get_storage_provider():
    """
    Returns the configured storage provider.
    """
    provider = config["storage"]["provider"]
    if provider == "s3":
        return S3StorageProvider(config["storage"]["s3"]["bucket_name"])
    elif provider == "fs":
        return FSStorageProvider(config["storage"]["fs"]["base_path"])
    else:
        raise Exception(f"Unknown storage provider: {provider}")


storage_provider = get_storage_provider()

# Export static methods for convenience
load_from_url = StorageProvider.load_from_url
load_from_parts = StorageProvider.load_from_parts

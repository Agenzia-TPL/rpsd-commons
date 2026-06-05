# SPDX-License-Identifier: BSD-3-Clause
# SPDX-FileCopyrightText: 2026 AGENZIA TPL BACINO CITTA' METROPOLITANA MILANO,
# MONZA E BRIANZA, LODI, PAVIA
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
            aws_access_key_id=settings.s3.aws_access_key_id,
            aws_secret_access_key=settings.s3.aws_secret_access_key,
            aws_session_token=settings.s3.aws_session_token,
            region_name=settings.s3.region_name,
            endpoint_url=settings.s3.endpoint_url,
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


# Export static methods for convenience
load_from_url = StorageProvider.load_from_url

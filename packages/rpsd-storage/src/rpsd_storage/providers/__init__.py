# SPDX-License-Identifier: BSD-3-Clause
# SPDX-FileCopyrightText: 2026 AGENZIA TPL BACINO CITTA' METROPOLITANA MILANO,
# MONZA E BRIANZA, LODI, PAVIA
"""Storage providers for rpsd-storage."""

from rpsd_storage.providers.base import StorageProvider
from rpsd_storage.providers.fs import FSStorageProvider
from rpsd_storage.providers.http import HTTPStorageProvider
from rpsd_storage.providers.s3 import S3StorageProvider

__all__ = [
    "StorageProvider",
    "FSStorageProvider",
    "S3StorageProvider",
    "HTTPStorageProvider",
]

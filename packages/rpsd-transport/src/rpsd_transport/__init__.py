"""
rpsd-transport: Transport library for sending and receiving content.

Supports both inline and outline metadata organization:
- Inline: JSON body with {"metadata": {...}, "content": "..."}
- Outline: Metadata in headers/query params, content in body or multipart
"""

from rpsd_transport.compression import decompress_content, is_compressed
from rpsd_transport.exceptions import (
    CompressionError,
    ContentFetchError,
    DuplicateMetadataError,
    InvalidJsonError,
    InvalidMetadataError,
    MissingMetadataError,
    StorageError,
    TransportError,
)

# Legacy models (deprecated)
from rpsd_transport.models import (
    ERROR_CODES,
    BaseMessage,
    ErrorResponse,
    FastMessage,
    FatMessage,
    HeavyMessage,
    InlineMessagePayload,
    MessageMetadata,
    SlimMessage,
    SuccessResponse,
    TransportMessage,
)
from rpsd_transport.settings import TransportSettings

__all__ = [
    # Settings
    "TransportSettings",
    # Core models
    "MessageMetadata",
    "TransportMessage",
    "InlineMessagePayload",
    # Response models
    "SuccessResponse",
    "ErrorResponse",
    "ERROR_CODES",
    # Compression
    "decompress_content",
    "is_compressed",
    # Exceptions
    "TransportError",
    "DuplicateMetadataError",
    "MissingMetadataError",
    "InvalidJsonError",
    "InvalidMetadataError",
    "CompressionError",
    "ContentFetchError",
    "StorageError",
    # Legacy models (deprecated)
    "BaseMessage",
    "FastMessage",
    "SlimMessage",
    "HeavyMessage",
    "FatMessage",
]

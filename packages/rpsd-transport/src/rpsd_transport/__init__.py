"""
rpsd-transport: Transport library for sending and receiving content.

Supports both inline and outline metadata organization:
- Inline: JSON body with {"metadata": {...}, "content": "..."}
- Outline: Metadata in headers/query params, content in body or multipart
"""

from rpsd_transport.carriers.base import BaseCarrier, CarrierOptions
from rpsd_transport.compression import (
    decompress_content,
    is_compressed,
)
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
from rpsd_transport.processors.ingest import IngestProcessor, IngestResult
from rpsd_transport.resolve import (
    reconcile_metadata,
    resolve_content,
    resolve_content_async,
)
from rpsd_transport.settings import (
    ForwardSettings,
    IngestSettings,
    KafkaSettings,
    TransportSettings,
)


def get_carrier(
    settings: TransportSettings | None = None,
) -> BaseCarrier:
    """Create a carrier based on settings.

    Mirrors rpsd-storage's get_storage_provider() pattern.

    Args:
        settings: Transport settings. If None, loads from
            environment variables.

    Returns:
        BaseCarrier: Configured carrier instance

    Raises:
        ValueError: If carrier type is unknown
        ImportError: If broker dependencies are missing
    """
    if settings is None:
        settings = TransportSettings()

    if settings.carrier == "http":
        from rpsd_transport.carriers.http import HTTPCarrier

        return HTTPCarrier()

    if settings.carrier == "kafka":
        from rpsd_transport.carriers.pubsub.kafka import (
            KafkaPubSubCarrier,
        )

        return KafkaPubSubCarrier(
            bootstrap_servers=settings.kafka.bootstrap_servers,
            group_id=settings.kafka.group_id,
            client_id=settings.kafka.client_id,
        )

    raise ValueError(f"Unknown carrier type: {settings.carrier}")


__all__ = [
    # Factory
    "get_carrier",
    # Base classes
    "BaseCarrier",
    "CarrierOptions",
    # Processors
    "IngestProcessor",
    "IngestResult",
    # Resolve utilities
    "resolve_content",
    "resolve_content_async",
    "reconcile_metadata",
    # Settings
    "TransportSettings",
    "KafkaSettings",
    "IngestSettings",
    "ForwardSettings",
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

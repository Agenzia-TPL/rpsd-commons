"""
Utility functions for resolving transport message content.

Provides standalone functions for resolving fat/heavy message
content and reconciling metadata, without requiring
IngestProcessor. Useful for client code that works directly
with carriers.

Example:
    ```python
    from rpsd_transport.resolve import (
        resolve_content,
        reconcile_metadata,
    )

    message = await carrier.receive(request)
    content, fetch_meta = resolve_content(message)
    message = reconcile_metadata(message, fetch_meta)
    ```
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from rpsd_transport.exceptions import ContentFetchError
from rpsd_transport.models import TransportMessage

if TYPE_CHECKING:
    from rpsd_storage.metadata import StorageMetadata

logger = logging.getLogger(__name__)


def resolve_content(
    message: TransportMessage,
) -> tuple[bytes, StorageMetadata | None]:
    """Resolve message content.

    For slim/fast messages, returns message.content directly.
    For fat/heavy messages, fetches content and metadata from
    the where URL using rpsd-storage's StorageProvider
    (supports file://, http://, https://, s3://).

    Args:
        message: TransportMessage to resolve.

    Returns:
        Tuple of (content_bytes, fetch_metadata).
        fetch_metadata is None for slim/fast messages.

    Raises:
        ContentFetchError: If heavy content fetch fails.
        ValueError: If slim message has no content.
    """
    if message.is_slimfast:
        if message.content is None:
            raise ValueError("Slim/fast message has no content")
        return message.content, None

    if message.where is None:
        raise ValueError("Fat/heavy message missing 'where' URL")

    logger.info("Fetching heavy content from: %s", message.where)
    try:
        from rpsd_storage.providers.base import StorageProvider

        content, fetch_metadata = StorageProvider.load_from_url(message.where)
        return content, fetch_metadata
    except ContentFetchError:
        raise
    except Exception as e:
        raise ContentFetchError(
            f"Failed to fetch content from {message.where}: {e}"
        ) from e


async def resolve_content_async(
    message: TransportMessage,
) -> tuple[bytes, StorageMetadata | None]:
    """Resolve message content (async version).

    Runs resolve_content in a thread pool via
    asyncio.to_thread().

    Args:
        message: TransportMessage to resolve.

    Returns:
        Tuple of (content_bytes, fetch_metadata).
        fetch_metadata is None for slim/fast messages.

    Raises:
        ContentFetchError: If heavy content fetch fails.
        ValueError: If slim message has no content.
    """
    return await asyncio.to_thread(resolve_content, message)


def reconcile_metadata(
    message: TransportMessage,
    fetch_metadata: StorageMetadata | None,
) -> TransportMessage:
    """Reconcile message metadata with fetched content metadata.

    After resolving fat/heavy content, updates the message's
    metadata with authoritative fields from the fetched
    StorageMetadata. For slim/fast messages (fetch_metadata is
    None), returns the original message unchanged.

    Fields updated from fetched content:
    - content_type: always replaced with actual MIME type
    - filename: replaced only if original is None and the
      fetch provides a meaningful filename

    Fields preserved from original message:
    - who, what, where, custom_metadata

    Args:
        message: Original TransportMessage.
        fetch_metadata: StorageMetadata from content fetch,
            or None for slim/fast messages.

    Returns:
        New TransportMessage with reconciled metadata, or
        original message if fetch_metadata is None.
    """
    if fetch_metadata is None:
        return message

    updates: dict = {
        "content_type": fetch_metadata.content_type,
    }

    if (
        message.metadata.filename is None
        and fetch_metadata.original_filename != "unknown"
    ):
        updates["filename"] = fetch_metadata.original_filename

    return message.model_copy(
        update={"metadata": message.metadata.model_copy(update=updates)}
    )

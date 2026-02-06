"""
Custom HTTPCarrier with storage integration via received() hook.
"""

import logging

import httpx

from rpsd_storage.metadata import StorageMetadata
from rpsd_storage.providers.base import StorageProvider
from rpsd_transport.carriers.http import HTTPCarrier
from rpsd_transport.models import TransportMessage


class StorageHTTPCarrier(HTTPCarrier):
    """
    HTTPCarrier extension that saves received content to storage.

    Uses the received() hook to automatically save content after
    successful message parsing. Supports both fast (inline content)
    and heavy (URL reference) messages.
    """

    def __init__(self, storage_provider: StorageProvider, **kwargs):
        """
        Initialize carrier with storage provider.

        Args:
            storage_provider: Storage provider (FS, S3, etc.)
            **kwargs: Additional arguments for HTTPCarrier
        """
        super().__init__(**kwargs)
        self.storage_provider = storage_provider
        self.logger = logging.getLogger(__name__)

        # Store last saved info for response building
        self.last_saved_url: str | None = None
        self.last_saved_metadata: StorageMetadata | None = None

    def received(self, message: TransportMessage) -> None:
        """
        Hook called after successfully receiving and parsing a message.

        Saves content to storage using configured provider. For heavy
        messages, fetches content from the where URL first.

        Args:
            message: Successfully parsed TransportMessage

        Raises:
            Exception: If storage save fails or heavy content fetch fails
        """
        # Handle heavy messages - fetch content from where URL
        if message.is_fatheavy:
            if message.where is None:
                raise ValueError("Heavy message missing 'where' URL")
            self.logger.info(f"Fetching heavy content from: {message.where}")
            content = self._fetch_heavy_content(message.where)
        else:
            content = message.content

        # Save to storage
        self.logger.info(
            f"Saving content to storage (who={message.who}, what={message.what})"
        )

        url, metadata = self.storage_provider.save(
            content=content,
            filename=message.metadata.filename or "data.bin",
            who=message.who,
            what=message.what,
            content_type=message.metadata.content_type,
            source_url=message.where if message.is_fatheavy else None,
        )

        # Store for response
        self.last_saved_url = url
        self.last_saved_metadata = metadata

        self.logger.info(f"Content saved successfully: {url}")

    def _fetch_heavy_content(self, url: str) -> bytes:
        """
        Fetch content from URL for heavy messages.

        Args:
            url: URL to fetch content from

        Returns:
            Content bytes

        Raises:
            Exception: If fetch fails
        """
        try:
            response = self._http_client.get(url, follow_redirects=True)
            response.raise_for_status()
            return response.content
        except httpx.HTTPError as e:
            self.logger.error(f"Failed to fetch heavy content from {url}: {e}")
            raise Exception(f"Failed to fetch content from {url}: {e}") from e

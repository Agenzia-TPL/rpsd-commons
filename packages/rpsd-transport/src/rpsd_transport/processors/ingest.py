"""
Ingest processor for rpsd-transport.

Handles the common receive -> resolve -> save -> forward pipeline,
working with any carrier type via composition.
"""

import logging
from typing import Literal

from pydantic import BaseModel, Field

from rpsd_storage.metadata import StorageMetadata
from rpsd_storage.providers.base import StorageProvider
from rpsd_transport.carriers.base import BaseCarrier, CarrierOptions
from rpsd_transport.exceptions import (
    ContentFetchError,
    StorageError,
    TransportError,
)
from rpsd_transport.models import TransportMessage

logger = logging.getLogger(__name__)


class IngestResult(BaseModel):
    """Result of processing an ingested message.

    Contains the original message, resolved content, and
    outcomes of optional save and forward steps.

    Attributes:
        message: Original parsed TransportMessage.
        content: Resolved content bytes (fetched from where URL
            for fat/heavy messages, or original content for
            slim/fast messages).
        storage_url: URL from storage save, if storage was
            configured and save succeeded. None otherwise.
        storage_metadata: Metadata from storage save. None if
            storage was not configured or save did not occur.
        forwarded: True if message was successfully forwarded
            to a second carrier. False otherwise.
    """

    message: TransportMessage
    content: bytes | None = None
    storage_url: str | None = None
    storage_metadata: StorageMetadata | None = Field(default=None, exclude=True)
    forwarded: bool = False


class IngestProcessor:
    """Processes received transport messages: resolve, save, forward.

    Works with any carrier type -- not a carrier subclass.
    Provides both sync (process) and async (process_async) APIs.

    The processing pipeline:
    1. Resolve content (fetch from where URL for fat/heavy messages)
    2. Optionally save to a StorageProvider
    3. Optionally forward to a second BaseCarrier

    All steps are optional except content resolution, which always
    runs. Storage and forward are only performed when their
    respective dependencies are provided.

    Example -- receive and save:
        ```python
        processor = IngestProcessor(storage=storage_provider)
        message = await carrier.receive(request)
        result = processor.process(message)
        print(result.storage_url)
        ```

    Example -- receive, save, and forward:
        ```python
        processor = IngestProcessor(
            storage=storage_provider,
            forward_carrier=kafka_carrier,
            forward_recipient="output-topic",
        )
        message = await carrier.receive(request)
        result = processor.process(message)
        ```

    Args:
        storage: Optional StorageProvider for saving content.
        forward_carrier: Optional BaseCarrier for forwarding.
        forward_recipient: Target for forwarding (URL or topic).
            Required if forward_carrier is provided.
        forward_options: Optional CarrierOptions for forwarding.
        forward_mode: How to forward after save. "fatheavy"
            (default) sends with where=storage_url. "slimfast"
            re-embeds resolved content inline.
    """

    def __init__(
        self,
        storage: StorageProvider | None = None,
        forward_carrier: BaseCarrier | None = None,
        forward_recipient: str | None = None,
        forward_options: CarrierOptions | None = None,
        forward_mode: Literal["fatheavy", "slimfast"] = "fatheavy",
    ):
        """Initialize the ingest processor.

        Args:
            storage: Optional StorageProvider for saving content.
            forward_carrier: Optional BaseCarrier for forwarding
                messages after processing.
            forward_recipient: Target for forwarding (URL for
                HTTP, topic for PubSub). Required when
                forward_carrier is provided.
            forward_options: Optional CarrierOptions passed to
                the forward carrier's send methods.
            forward_mode: Forward strategy after storage save.
                "fatheavy" sends with where=storage_url.
                "slimfast" sends with content inline.

        Raises:
            ValueError: If forward_carrier is provided without
                forward_recipient.
        """
        if forward_carrier is not None and forward_recipient is None:
            raise ValueError(
                "forward_recipient is required when forward_carrier is provided"
            )

        self.storage = storage
        self.forward_carrier = forward_carrier
        self.forward_recipient = forward_recipient
        self.forward_options = forward_options
        self.forward_mode = forward_mode

    def process(self, message: TransportMessage) -> IngestResult:
        """Process a received message (sync version).

        Uses httpx.Client for heavy content resolution.
        Uses sync send methods on forward carrier.

        Args:
            message: Parsed TransportMessage from any carrier.

        Returns:
            IngestResult with outcomes of each pipeline step.

        Raises:
            ContentFetchError: If heavy content cannot be fetched.
            StorageError: If storage save fails.
        """
        # 1. Resolve content
        content = self._resolve_content(message)

        # 2. Optionally save to storage
        storage_url = None
        storage_metadata = None
        if self.storage is not None:
            storage_url, storage_metadata = self._save_to_storage(message, content)

        # 3. Optionally forward
        forwarded = False
        if self.forward_carrier is not None:
            forwarded = self._forward_message(message, content, storage_url)

        return IngestResult(
            message=message,
            content=content,
            storage_url=storage_url,
            storage_metadata=storage_metadata,
            forwarded=forwarded,
        )

    async def process_async(self, message: TransportMessage) -> IngestResult:
        """Process a received message (async version).

        Uses httpx.AsyncClient for heavy content resolution.
        Uses async send methods on forward carrier when available,
        falling back to sync send methods otherwise.

        Args:
            message: Parsed TransportMessage from any carrier.

        Returns:
            IngestResult with outcomes of each pipeline step.

        Raises:
            ContentFetchError: If heavy content cannot be fetched.
            StorageError: If storage save fails.
        """
        # 1. Resolve content
        content = await self._resolve_content_async(message)

        # 2. Optionally save to storage (sync — StorageProvider is sync)
        storage_url = None
        storage_metadata = None
        if self.storage is not None:
            storage_url, storage_metadata = self._save_to_storage(message, content)

        # 3. Optionally forward
        forwarded = False
        if self.forward_carrier is not None:
            forwarded = await self._forward_message_async(message, content, storage_url)

        return IngestResult(
            message=message,
            content=content,
            storage_url=storage_url,
            storage_metadata=storage_metadata,
            forwarded=forwarded,
        )

    def _resolve_content(self, message: TransportMessage) -> bytes:
        """Resolve message content synchronously.

        For slim/fast messages, returns message.content directly.
        For fat/heavy messages, fetches content from the where URL
        using rpsd-storage's StorageProvider (supports file://, http://, https://, s3://).

        Args:
            message: TransportMessage to resolve.

        Returns:
            Resolved content bytes.

        Raises:
            ContentFetchError: If heavy content fetch fails.
            ValueError: If slim message has no content.
        """
        if message.is_slimfast:
            if message.content is None:
                raise ValueError("Slim/fast message has no content")
            return message.content

        if message.where is None:
            raise ValueError("Fat/heavy message missing 'where' URL")

        logger.info("Fetching heavy content from: %s", message.where)
        try:
            content = StorageProvider.load_content_from_url(message.where)
            return content
        except Exception as e:
            raise ContentFetchError(
                f"Failed to fetch content from {message.where}: {e}"
            ) from e

    async def _resolve_content_async(self, message: TransportMessage) -> bytes:
        """Resolve message content asynchronously.

        For slim/fast messages, returns message.content directly.
        For fat/heavy messages, fetches content from the where URL
        using rpsd-storage's StorageProvider (supports file://, http://, https://, s3://).

        Note: StorageProvider.load_content_from_url() is synchronous, so we run it
        in an async context. For truly async operations, consider using
        asyncio.to_thread() or implement async storage providers in the future.

        Args:
            message: TransportMessage to resolve.

        Returns:
            Resolved content bytes.

        Raises:
            ContentFetchError: If heavy content fetch fails.
            ValueError: If slim message has no content.
        """
        if message.is_slimfast:
            if message.content is None:
                raise ValueError("Slim/fast message has no content")
            return message.content

        if message.where is None:
            raise ValueError("Fat/heavy message missing 'where' URL")

        logger.info("Fetching heavy content from: %s", message.where)
        try:
            # Note: StorageProvider methods are currently synchronous
            # This is acceptable for now as I/O is typically fast
            content = StorageProvider.load_content_from_url(message.where)
            return content
        except Exception as e:
            raise ContentFetchError(
                f"Failed to fetch content from {message.where}: {e}"
            ) from e

    def _save_to_storage(
        self,
        message: TransportMessage,
        content: bytes,
    ) -> tuple[str, StorageMetadata]:
        """Save resolved content to storage provider.

        Args:
            message: Original TransportMessage (for metadata).
            content: Resolved content bytes to save.

        Returns:
            Tuple of (storage_url, storage_metadata).

        Raises:
            StorageError: If storage save fails.
        """
        assert self.storage is not None, "Storage provider must be configured"
        logger.info(
            "Saving content to storage: who=%s, what=%s",
            message.who,
            message.what,
        )
        try:
            url, metadata = self.storage.save(
                content=content,
                filename=(message.metadata.filename or "data.bin"),
                who=message.who,
                what=message.what,
                content_type=message.metadata.content_type,
                source_url=(message.where if message.is_fatheavy else None),
                custom_metadata=message.metadata.custom_metadata,
            )
            logger.info("Content saved successfully: %s", url)
            return url, metadata
        except Exception as e:
            raise StorageError(f"Failed to save content to storage: {e}") from e

    def _forward_message(
        self,
        message: TransportMessage,
        content: bytes | None,
        storage_url: str | None,
    ) -> bool:
        """Forward message to second carrier (sync).

        Strategy depends on forward_mode and whether storage
        was used:
        - forward_mode="fatheavy" + storage_url: send_fatheavy
          with where=storage_url
        - forward_mode="slimfast" + content: send_slimfast with
          resolved content inline
        - No storage + slimfast message: send_slimfast with
          original content
        - No storage + fatheavy message: send_fatheavy with
          original where URL

        Args:
            message: Original TransportMessage.
            content: Resolved content bytes (may be None).
            storage_url: URL from storage save (may be None).

        Returns:
            True if forwarding succeeded, False if it failed.
        """
        try:
            self._do_forward(message, content, storage_url)
            logger.info(
                "Message forwarded to %s",
                self.forward_recipient,
            )
            return True
        except Exception as e:
            logger.error(
                "Failed to forward message to %s: %s",
                self.forward_recipient,
                e,
            )
            return False

    async def _forward_message_async(
        self,
        message: TransportMessage,
        content: bytes | None,
        storage_url: str | None,
    ) -> bool:
        """Forward message to second carrier (async).

        Same forward_mode strategy as _forward_message. Uses
        *_async send methods when available on the carrier
        (e.g., KafkaPubSubCarrier), falls back to sync send
        methods otherwise.

        Args:
            message: Original TransportMessage.
            content: Resolved content bytes (may be None).
            storage_url: URL from storage save (may be None).

        Returns:
            True if forwarding succeeded, False if it failed.
        """
        try:
            await self._do_forward_async(message, content, storage_url)
            logger.info(
                "Message forwarded to %s",
                self.forward_recipient,
            )
            return True
        except Exception as e:
            logger.error(
                "Failed to forward message to %s: %s",
                self.forward_recipient,
                e,
            )
            return False

    def _do_forward(
        self,
        message: TransportMessage,
        content: bytes | None,
        storage_url: str | None,
    ) -> None:
        """Execute the forward send (sync).

        Raises:
            TransportError: If forwarding fails.
        """
        assert self.forward_carrier is not None, "Forward carrier required"
        assert self.forward_recipient is not None, "Forward recipient required"
        send_as_fatheavy = self._should_send_fatheavy(message, storage_url)

        if send_as_fatheavy:
            where = storage_url or message.where
            self.forward_carrier.send_fatheavy(
                recipient=self.forward_recipient,
                who=message.who,
                what=message.what,
                content=None,
                content_type=message.metadata.content_type,
                filename=message.metadata.filename,
                options=self.forward_options,
                where=where,
            )
        else:
            if content is None:
                raise TransportError("Cannot forward as slimfast: no content available")
            self.forward_carrier.send_slimfast(
                recipient=self.forward_recipient,
                who=message.who,
                what=message.what,
                content=content,
                content_type=message.metadata.content_type,
                filename=message.metadata.filename,
                options=self.forward_options,
            )

    async def _do_forward_async(
        self,
        message: TransportMessage,
        content: bytes | None,
        storage_url: str | None,
    ) -> None:
        """Execute the forward send (async).

        Uses async send methods. All carriers support async via
        BaseCarrier's default implementation (thread pool). Carriers
        with native async (e.g., KafkaPubSubCarrier) override for
        better performance.

        Raises:
            TransportError: If forwarding fails.
        """
        assert self.forward_carrier is not None, "Forward carrier required"
        assert self.forward_recipient is not None, "Forward recipient required"
        send_as_fatheavy = self._should_send_fatheavy(message, storage_url)

        if send_as_fatheavy:
            where = storage_url or message.where
            await self.forward_carrier.send_fatheavy_async(
                recipient=self.forward_recipient,
                who=message.who,
                what=message.what,
                content=None,
                content_type=message.metadata.content_type,
                filename=message.metadata.filename,
                options=self.forward_options,
                where=where,
            )
        else:
            if content is None:
                raise TransportError("Cannot forward as slimfast: no content available")
            await self.forward_carrier.send_slimfast_async(
                recipient=self.forward_recipient,
                who=message.who,
                what=message.what,
                content=content,
                content_type=message.metadata.content_type,
                filename=message.metadata.filename,
                options=self.forward_options,
            )

    def _should_send_fatheavy(
        self,
        message: TransportMessage,
        storage_url: str | None,
    ) -> bool:
        """Determine whether to forward as fatheavy or slimfast.

        Decision logic:
        - If storage was used and forward_mode is "fatheavy":
          send as fatheavy with storage_url
        - If storage was used and forward_mode is "slimfast":
          send as slimfast with resolved content
        - If no storage, preserve original message mode:
          slimfast stays slimfast, fatheavy stays fatheavy

        Args:
            message: Original TransportMessage.
            storage_url: URL from storage save (may be None).

        Returns:
            True to send as fatheavy, False for slimfast.
        """
        if storage_url is not None:
            return self.forward_mode == "fatheavy"
        return message.is_fatheavy

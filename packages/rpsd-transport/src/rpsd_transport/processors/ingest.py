# SPDX-License-Identifier: BSD-3-Clause
# SPDX-FileCopyrightText: 2026 AGENZIA TPL BACINO CITTA' METROPOLITANA MILANO,
# MONZA E BRIANZA, LODI, PAVIA
"""
Ingest processor for rpsd-transport.

Handles the common receive -> resolve -> save -> forward pipeline,
working with any carrier type via composition.
"""

import asyncio
import logging
from collections.abc import Awaitable
from typing import Literal

from pydantic import BaseModel, Field

from rpsd_storage.metadata import StorageMetadata
from rpsd_storage.providers.base import StorageProvider
from rpsd_transport.carriers.base import BaseCarrier, CarrierOptions
from rpsd_transport.exceptions import (
    StorageError,
    TransformError,
    TransportError,
)
from rpsd_transport.models import TransportMessage
from rpsd_transport.resolve import (
    reconcile_metadata,
    resolve_content,
    resolve_content_async,
)
from rpsd_transport.transformers import (
    AsyncMessageTransformer,
    AsyncMessageTransformFn,
    MessageTransformer,
    MessageTransformFn,
)

logger = logging.getLogger(__name__)


class IngestResult(BaseModel):
    """Result of processing an ingested message.

    Contains the reconciled message, resolved content, and
    outcomes of optional save and forward steps.

    Attributes:
        message: Reconciled TransportMessage. For fat/heavy
            messages, metadata fields (e.g. content_type) are
            updated from the fetched content. For slim/fast
            messages, this is the original message unchanged.
        content: Resolved content bytes (fetched from where URL
            for fat/heavy messages, or original content for
            slim/fast messages).
        storage_url: URL from storage save, if storage was
            configured and save succeeded. None otherwise.
        storage_metadata: Metadata from storage save. None if
            storage was not configured or save did not occur.
        fetch_metadata: Metadata from fetching the fat/heavy
            content URL. None for slim/fast messages or if no
            fetch occurred. Excluded from serialization.
        deduplicated: True if storage had compare-before-save
            enabled and the content was already stored (not
            newer). False otherwise. Excluded from
            serialization.
        forwarded: True if message was successfully forwarded
            to a second carrier. False if forwarding was not
            configured or was skipped (e.g. due to
            deduplication).
    """

    message: TransportMessage
    content: bytes | None = None
    storage_url: str | None = None
    storage_metadata: StorageMetadata | None = Field(default=None, exclude=True)
    fetch_metadata: StorageMetadata | None = Field(default=None, exclude=True)
    deduplicated: bool = Field(default=False, exclude=True)
    forwarded: bool = False


class IngestProcessor:
    """Processes received transport messages: resolve, save, forward.

    Works with any carrier type -- not a carrier subclass.
    Provides both sync (process) and async (process_async) APIs.

    The processing pipeline:
    1. Resolve content (fetch from where URL for fat/heavy messages)
    2. Reconcile metadata (update content_type, filename from fetch)
    3. Apply pre_save_transform (if configured)
    4. Optionally save to a StorageProvider
    5. Apply pre_forward_transform and forward to a second BaseCarrier
       (if configured and not deduplicated)

    All steps are optional except content resolution and metadata
    reconciliation, which always run. For fat/heavy messages, the
    reconciliation step updates the message's content_type (and
    optionally filename) from the fetched content's actual metadata.
    Storage and forward are only performed when their respective
    dependencies are provided. Transformers allow modifying messages
    before storage and/or forwarding.

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

    Example -- with metadata enrichment:
        ```python
        from rpsd_transport.transformers import with_custom_metadata

        def enrich(meta: dict, content: bytes) -> dict:
            return {**meta, "timestamp": "...", "hash": "..."}

        processor = IngestProcessor(
            storage=storage_provider,
            pre_save_transform=with_custom_metadata(enrich),
        )
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
        pre_save_transform: Optional transformer applied before save.
        pre_forward_transform: Optional transformer applied before forward.
    """

    def __init__(
        self,
        storage: StorageProvider | None = None,
        forward_carrier: BaseCarrier | None = None,
        forward_recipient: str | None = None,
        forward_options: CarrierOptions | None = None,
        forward_mode: Literal["fatheavy", "slimfast"] = "fatheavy",
        pre_save_transform: (
            MessageTransformer
            | AsyncMessageTransformer
            | MessageTransformFn
            | AsyncMessageTransformFn
            | None
        ) = None,
        pre_forward_transform: (
            MessageTransformer
            | AsyncMessageTransformer
            | MessageTransformFn
            | AsyncMessageTransformFn
            | None
        ) = None,
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
            pre_save_transform: Optional transformer applied after
                content resolution, before saving to storage. Receives
                the original message and resolved content. Returns a
                NEW TransportMessage (immutable).
            pre_forward_transform: Optional transformer applied after
                storage save (if configured), before forwarding.
                Receives the message (possibly already transformed
                by pre_save_transform) and resolved content. Returns
                a NEW TransportMessage (immutable).

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
        self.pre_save_transform = pre_save_transform
        self.pre_forward_transform = pre_forward_transform

    def _apply_transform(
        self,
        message: TransportMessage,
        content: bytes,
        transformer: (
            MessageTransformer
            | AsyncMessageTransformer
            | MessageTransformFn
            | AsyncMessageTransformFn
            | None
        ),
    ) -> TransportMessage:
        """Apply a transformer synchronously.

        Args:
            message: TransportMessage to transform.
            content: Resolved content bytes.
            transformer: Transformer to apply (can be None).

        Returns:
            Transformed TransportMessage, or original if no transformer.

        Raises:
            TransformError: If transformation fails.
        """
        if transformer is None:
            return message

        try:
            # Check if it's a callable function
            if callable(transformer) and not hasattr(transformer, "transform"):
                # Simple function transformer
                result = transformer(message, content)
            else:
                # Protocol-based transformer
                result = transformer.transform(message, content)

            # Narrow out Awaitable for sync path
            if isinstance(result, Awaitable):
                raise TypeError(
                    "Async transformer used in sync context. "
                    "Use process_async() for async transformers."
                )
            return result
        except (TypeError, TransformError):
            raise
        except Exception as e:
            raise TransformError(f"Message transformation failed: {e}") from e

    async def _apply_transform_async(
        self,
        message: TransportMessage,
        content: bytes,
        transformer: (
            MessageTransformer
            | AsyncMessageTransformer
            | MessageTransformFn
            | AsyncMessageTransformFn
            | None
        ),
    ) -> TransportMessage:
        """Apply a transformer asynchronously.

        Supports both sync and async transformers. Sync transformers
        are run in a thread pool using asyncio.to_thread().

        Args:
            message: TransportMessage to transform.
            content: Resolved content bytes.
            transformer: Transformer to apply (can be None).

        Returns:
            Transformed TransportMessage, or original if no transformer.

        Raises:
            TransformError: If transformation fails.
        """
        if transformer is None:
            return message

        try:
            # Check if it's a callable function
            if callable(transformer) and not hasattr(transformer, "transform"):
                # Simple callable transformer
                if asyncio.iscoroutinefunction(transformer):
                    # Async function
                    return await transformer(message, content)
                else:
                    # Sync function, run in thread pool
                    result = await asyncio.to_thread(transformer, message, content)
                    if isinstance(result, Awaitable):
                        return await result
                    return result
            else:
                # Protocol-based transformer
                transform_method = transformer.transform
                if asyncio.iscoroutinefunction(transform_method):
                    # Async transform method
                    return await transform_method(message, content)
                else:
                    # Sync transform method, run in thread pool
                    result = await asyncio.to_thread(transform_method, message, content)
                    if isinstance(result, Awaitable):
                        return await result
                    return result
        except Exception as e:
            raise TransformError(f"Message transformation failed: {e}") from e

    def process(
        self,
        message: TransportMessage,
        compare_before_save: bool | None = None,
    ) -> IngestResult:
        """Process a received message (sync version).

        Uses httpx.Client for heavy content resolution.
        Uses sync send methods on forward carrier.

        Pipeline:
        1. Resolve content (fetch if fat/heavy)
        2. Reconcile metadata from fetched content
        3. Apply pre_save_transform (if configured)
        4. Save to storage (if configured) - uses transformed message
        5. Apply pre_forward_transform and forward (if configured and
           not deduplicated)

        Args:
            message: Parsed TransportMessage from any carrier.
            compare_before_save: Per-call override for deduplication passed
                to storage.save(). None means use the storage provider's
                instance-level setting.

        Returns:
            IngestResult with outcomes of each pipeline step.

        Raises:
            ContentFetchError: If heavy content cannot be fetched.
            StorageError: If storage save fails.
            TransformError: If transformation fails.
        """
        # 1. Resolve content
        content, fetch_metadata = self._resolve_content(message)

        # 2. Reconcile metadata from fetched content
        reconciled = self._reconcile_metadata(message, fetch_metadata)

        # 3. Apply pre_save_transform
        message_for_save = self._apply_transform(
            reconciled, content, self.pre_save_transform
        )

        # 4. Optionally save to storage
        storage_url = None
        storage_metadata = None
        deduplicated = False
        if self.storage is not None:
            storage_url, storage_metadata = self._save_to_storage(
                message_for_save, content, compare_before_save
            )
            deduplicated = storage_metadata.deduplicated

        # 5+6. Optionally forward (skip if deduplicated)
        forwarded = False
        if self.forward_carrier is not None and not deduplicated:
            message_for_forward = self._apply_transform(
                message_for_save, content, self.pre_forward_transform
            )
            forwarded = self._forward_message(message_for_forward, content, storage_url)
        elif deduplicated:
            logger.info(
                "Skipping forward: content deduplicated (who=%s, what=%s)",
                message.who,
                message.what,
            )

        return IngestResult(
            message=reconciled,
            content=content,
            storage_url=storage_url,
            storage_metadata=storage_metadata,
            fetch_metadata=fetch_metadata,
            deduplicated=deduplicated,
            forwarded=forwarded,
        )

    async def process_async(
        self,
        message: TransportMessage,
        compare_before_save: bool | None = None,
    ) -> IngestResult:
        """Process a received message (async version).

        Uses httpx.AsyncClient for heavy content resolution.
        Uses async send methods on forward carrier when available,
        falling back to sync send methods otherwise.

        Pipeline:
        1. Resolve content (fetch if fat/heavy)
        2. Reconcile metadata from fetched content
        3. Apply pre_save_transform (if configured)
        4. Save to storage (if configured) - uses transformed message
        5. Apply pre_forward_transform and forward (if configured and
           not deduplicated)

        Args:
            message: Parsed TransportMessage from any carrier.
            compare_before_save: Per-call override for deduplication passed
                to storage.save(). None means use the storage provider's
                instance-level setting.

        Returns:
            IngestResult with outcomes of each pipeline step.

        Raises:
            ContentFetchError: If heavy content cannot be fetched.
            StorageError: If storage save fails.
            TransformError: If transformation fails.
        """
        # 1. Resolve content
        content, fetch_metadata = await self._resolve_content_async(message)

        # 2. Reconcile metadata from fetched content
        reconciled = self._reconcile_metadata(message, fetch_metadata)

        # 3. Apply pre_save_transform
        message_for_save = await self._apply_transform_async(
            reconciled, content, self.pre_save_transform
        )

        # 4. Optionally save to storage (sync — StorageProvider is sync)
        storage_url = None
        storage_metadata = None
        deduplicated = False
        if self.storage is not None:
            storage_url, storage_metadata = self._save_to_storage(
                message_for_save, content, compare_before_save
            )
            deduplicated = storage_metadata.deduplicated

        # 5+6. Optionally forward (skip if deduplicated)
        forwarded = False
        if self.forward_carrier is not None and not deduplicated:
            message_for_forward = await self._apply_transform_async(
                message_for_save, content, self.pre_forward_transform
            )
            forwarded = await self._forward_message_async(
                message_for_forward, content, storage_url
            )
        elif deduplicated:
            logger.info(
                "Skipping forward: content deduplicated (who=%s, what=%s)",
                message.who,
                message.what,
            )

        return IngestResult(
            message=reconciled,
            content=content,
            storage_url=storage_url,
            storage_metadata=storage_metadata,
            fetch_metadata=fetch_metadata,
            deduplicated=deduplicated,
            forwarded=forwarded,
        )

    def _resolve_content(
        self, message: TransportMessage
    ) -> tuple[bytes, StorageMetadata | None]:
        """Resolve message content synchronously.

        Delegates to rpsd_transport.resolve.resolve_content().

        Args:
            message: TransportMessage to resolve.

        Returns:
            Tuple of (content_bytes, fetch_metadata). fetch_metadata
            is None for slim/fast messages.

        Raises:
            ContentFetchError: If heavy content fetch fails.
            ValueError: If slim message has no content.
        """
        return resolve_content(message)

    async def _resolve_content_async(
        self, message: TransportMessage
    ) -> tuple[bytes, StorageMetadata | None]:
        """Resolve message content asynchronously.

        Delegates to rpsd_transport.resolve.resolve_content_async().

        Args:
            message: TransportMessage to resolve.

        Returns:
            Tuple of (content_bytes, fetch_metadata). fetch_metadata
            is None for slim/fast messages.

        Raises:
            ContentFetchError: If heavy content fetch fails.
            ValueError: If slim message has no content.
        """
        return await resolve_content_async(message)

    def _reconcile_metadata(
        self,
        message: TransportMessage,
        fetch_metadata: StorageMetadata | None,
    ) -> TransportMessage:
        """Reconcile message metadata with fetched content metadata.

        Delegates to rpsd_transport.resolve.reconcile_metadata().

        Args:
            message: Original TransportMessage.
            fetch_metadata: StorageMetadata from content fetch,
                or None for slim/fast messages.

        Returns:
            New TransportMessage with reconciled metadata, or
            original message if fetch_metadata is None.
        """
        return reconcile_metadata(message, fetch_metadata)

    def _save_to_storage(
        self,
        message: TransportMessage,
        content: bytes,
        compare_before_save: bool | None = None,
    ) -> tuple[str, StorageMetadata]:
        """Save resolved content to storage provider.

        Args:
            message: Original TransportMessage (for metadata).
            content: Resolved content bytes to save.
            compare_before_save: Per-call override for deduplication.
                None means use the storage provider's instance-level setting.

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
                filename=message.metadata.filename,
                who=message.who,
                what=message.what,
                content_type=message.metadata.content_type,
                source_url=(message.where if message.is_fatheavy else None),
                custom_metadata=message.metadata.custom_metadata,
                compare_before_save=compare_before_save,
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
                custom_metadata=message.metadata.custom_metadata or None,
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
                custom_metadata=message.metadata.custom_metadata or None,
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
                custom_metadata=message.metadata.custom_metadata or None,
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
                custom_metadata=message.metadata.custom_metadata or None,
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

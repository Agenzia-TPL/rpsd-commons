"""
Message transformers for rpsd-transport.

Provides Protocol-based transformers for modifying messages in the
IngestProcessor pipeline. Transformers can be applied before saving
to storage or before forwarding to a carrier.

The recommended approach for the common case (enriching custom_metadata)
is to use the `with_custom_metadata()` helper function.
"""

from collections.abc import Awaitable, Callable
from typing import Any, Protocol, runtime_checkable

from rpsd_transport.models import TransportMessage


@runtime_checkable
class MessageTransformer(Protocol):
    """Protocol for synchronous message transformers.

    Transformers receive the message and resolved content, and
    return a NEW TransportMessage (preserving immutability).

    Can raise exceptions to abort the pipeline.

    Example:
        ```python
        class MetadataEnricher:
            def transform(
                self,
                message: TransportMessage,
                content: bytes
            ) -> TransportMessage:
                return message.model_copy(
                    update={
                        "metadata": message.metadata.model_copy(
                            update={
                                "custom_metadata": {
                                    **message.metadata.custom_metadata,
                                    "timestamp": "...",
                                }
                            }
                        )
                    }
                )
        ```
    """

    def transform(
        self,
        message: TransportMessage,
        content: bytes,
    ) -> TransportMessage:
        """Transform the message before save/forward.

        Args:
            message: Original TransportMessage.
            content: Resolved content bytes.

        Returns:
            New TransportMessage with transformations applied.

        Raises:
            Any exception to abort the pipeline.
        """
        ...


@runtime_checkable
class AsyncMessageTransformer(Protocol):
    """Protocol for asynchronous message transformers.

    Same as MessageTransformer but async.

    Example:
        ```python
        class AsyncValidator:
            async def transform(
                self,
                message: TransportMessage,
                content: bytes
            ) -> TransportMessage:
                # Perform async validation
                await validate_content(content)

                # Return enriched message
                return message.model_copy(...)
        ```
    """

    async def transform(
        self,
        message: TransportMessage,
        content: bytes,
    ) -> TransportMessage:
        """Transform the message before save/forward (async).

        Args:
            message: Original TransportMessage.
            content: Resolved content bytes.

        Returns:
            New TransportMessage with transformations applied.

        Raises:
            Any exception to abort the pipeline.
        """
        ...


# Convenience type aliases for simple callable transformers
MessageTransformFn = Callable[[TransportMessage, bytes], TransportMessage]
AsyncMessageTransformFn = Callable[
    [TransportMessage, bytes], Awaitable[TransportMessage]
]


def with_custom_metadata(
    enricher: Callable[[dict[str, Any], bytes], dict[str, Any]],
) -> MessageTransformer:
    """Helper to create a transformer that only modifies custom_metadata.

    This is the recommended approach for the common case of metadata
    enrichment. The enricher function receives the current custom_metadata
    dict and content bytes, and returns a new custom_metadata dict.

    The enricher should typically use the spread operator to preserve
    existing metadata: `{**meta, "new_field": "value"}`.

    Args:
        enricher: Function that takes (custom_metadata, content) and
            returns a new custom_metadata dict.

    Returns:
        A MessageTransformer that applies the enricher to custom_metadata.

    Example:
        ```python
        from datetime import datetime, timezone
        import hashlib

        def add_processing_info(meta: dict, content: bytes) -> dict:
            return {
                **meta,
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "sha256": hashlib.sha256(content).hexdigest(),
                "size": len(content),
            }

        processor = IngestProcessor(
            storage=storage_provider,
            pre_save_transform=with_custom_metadata(add_processing_info),
        )
        ```
    """

    class CustomMetadataTransformer:
        """Transformer that applies enricher to custom_metadata."""

        def transform(
            self, message: TransportMessage, content: bytes
        ) -> TransportMessage:
            """Apply enricher to custom_metadata."""
            new_custom_metadata = enricher(message.metadata.custom_metadata, content)
            return message.model_copy(
                update={
                    "metadata": message.metadata.model_copy(
                        update={"custom_metadata": new_custom_metadata}
                    )
                }
            )

    return CustomMetadataTransformer()


def with_async_custom_metadata(
    enricher: Callable[[dict[str, Any], bytes], Awaitable[dict[str, Any]]],
) -> AsyncMessageTransformer:
    """Helper to create an async transformer that modifies custom_metadata.

    Like `with_custom_metadata()` but for async enricher functions.

    Args:
        enricher: Async function that takes (custom_metadata, content)
            and returns a new custom_metadata dict.

    Returns:
        An AsyncMessageTransformer that applies the enricher to
        custom_metadata.

    Example:
        ```python
        async def enrich_from_api(meta: dict, content: bytes) -> dict:
            async with httpx.AsyncClient() as client:
                response = await client.post("/validate", content=content)
                validation_result = response.json()

            return {
                **meta,
                "validated": True,
                "validation_result": validation_result,
            }

        processor = IngestProcessor(
            storage=storage_provider,
            pre_save_transform=with_async_custom_metadata(enrich_from_api),
        )
        ```
    """

    class AsyncCustomMetadataTransformer:
        """Async transformer that applies enricher to custom_metadata."""

        async def transform(
            self, message: TransportMessage, content: bytes
        ) -> TransportMessage:
            """Apply async enricher to custom_metadata."""
            new_custom_metadata = await enricher(
                message.metadata.custom_metadata, content
            )
            return message.model_copy(
                update={
                    "metadata": message.metadata.model_copy(
                        update={"custom_metadata": new_custom_metadata}
                    )
                }
            )

    return AsyncCustomMetadataTransformer()

"""
Base carrier abstract class for transport implementations.
"""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from rpsd_transport.models import TransportMessage


class CarrierOptions(BaseModel):
    """Base options common to all carriers.

    Each carrier type can extend this with carrier-specific options
    using Pydantic validation and defaults.

    Attributes:
        metadata_use_inline: If True, metadata is embedded in the
            message payload (JSON). If False, metadata is sent
            via carrier-specific outline mechanisms.
    """

    metadata_use_inline: bool = True


class BaseCarrier(ABC):
    """Abstract base class for transport carriers.

    Carriers implement different transport mechanisms (HTTP, PubSub,
    etc.) for sending and receiving data in both slim/fast and
    fat/heavy modes.

    Methods to implement:
    - send_slimfast: Send content inline (fast/slim mode)
    - send_fatheavy: Send content by reference (heavy/fat mode)

    Hook methods to override:
    - received: Called after successful message parsing for custom
      behavior (storage integration, metrics, validation, etc.)

    Each carrier type defines its own receive mechanism:
    - HTTPCarrier: async receive(request) -> TransportMessage
    - PubSubCarrier: async consume(topic) -> AsyncIterator
    """

    @abstractmethod
    def send_slimfast(
        self,
        recipient: str,
        who: str,
        what: str,
        content: bytes,
        content_type: str = "application/octet-stream",
        filename: str | None = None,
        custom_metadata: dict[str, Any] | None = None,
        options: CarrierOptions | None = None,
    ) -> dict:
        """Send data inline (fast/slim mode).

        Args:
            recipient: Target identifier (URL for HTTP, topic
                for PubSub, etc.)
            who: Entity identifier
            what: Content type/category
            content: Data to send
            content_type: MIME type of the data
            filename: Optional original filename
            custom_metadata: Optional additional metadata
            options: Carrier-specific options. Each carrier type
                defines its own options subclass with defaults.

        Returns:
            dict: Response from recipient

        Raises:
            Exception: If sending fails
        """
        pass

    @abstractmethod
    def send_fatheavy(
        self,
        recipient: str,
        who: str,
        what: str,
        content: bytes | None,
        content_type: str = "application/octet-stream",
        filename: str | None = None,
        custom_metadata: dict[str, Any] | None = None,
        options: CarrierOptions | None = None,
        where: str | None = None,
        expose_ttl: int = 3600,
    ) -> dict:
        """Send data by reference (heavy/fat mode).

        Either content or where must be provided.

        Args:
            recipient: Target identifier (URL for HTTP, topic
                for PubSub, etc.)
            who: Entity identifier
            what: Content type/category
            content: New data to save and expose or None
            content_type: MIME type of the data
            filename: Optional original filename
            custom_metadata: Optional additional metadata
            options: Carrier-specific options. Each carrier type
                defines its own options subclass with defaults.
            where: URL where content is available
            expose_ttl: Time-to-live for exposed URL in seconds

        Returns:
            dict: Response from recipient

        Raises:
            ValueError: If neither content nor where is provided
            Exception: If sending fails
        """
        pass

    async def send_slimfast_async(
        self,
        recipient: str,
        who: str,
        what: str,
        content: bytes,
        content_type: str = "application/octet-stream",
        filename: str | None = None,
        custom_metadata: dict[str, Any] | None = None,
        options: CarrierOptions | None = None,
    ) -> dict:
        """Send data inline (fast/slim mode) - async version.

        Default implementation runs the sync send_slimfast in a
        thread pool. Carriers with native async support (e.g.,
        KafkaPubSubCarrier) should override this for better
        performance.

        Args:
            recipient: Target identifier (URL for HTTP, topic
                for PubSub, etc.)
            who: Entity identifier
            what: Content type/category
            content: Data to send
            content_type: MIME type of the data
            filename: Optional original filename
            custom_metadata: Optional additional metadata
            options: Carrier-specific options. Each carrier type
                defines its own options subclass with defaults.

        Returns:
            dict: Response from recipient

        Raises:
            Exception: If sending fails
        """
        import asyncio

        return await asyncio.to_thread(
            self.send_slimfast,
            recipient=recipient,
            who=who,
            what=what,
            content=content,
            content_type=content_type,
            filename=filename,
            custom_metadata=custom_metadata,
            options=options,
        )

    async def send_fatheavy_async(
        self,
        recipient: str,
        who: str,
        what: str,
        content: bytes | None,
        content_type: str = "application/octet-stream",
        filename: str | None = None,
        custom_metadata: dict[str, Any] | None = None,
        options: CarrierOptions | None = None,
        where: str | None = None,
        expose_ttl: int = 3600,
    ) -> dict:
        """Send data by reference (heavy/fat mode) - async version.

        Default implementation runs the sync send_fatheavy in a
        thread pool. Carriers with native async support (e.g.,
        KafkaPubSubCarrier) should override this for better
        performance.

        Either content or where must be provided.

        Args:
            recipient: Target identifier (URL for HTTP, topic
                for PubSub, etc.)
            who: Entity identifier
            what: Content type/category
            content: New data to save and expose or None
            content_type: MIME type of the data
            filename: Optional original filename
            custom_metadata: Optional additional metadata
            options: Carrier-specific options. Each carrier type
                defines its own options subclass with defaults.
            where: URL where content is available
            expose_ttl: Time-to-live for exposed URL in seconds

        Returns:
            dict: Response from recipient

        Raises:
            ValueError: If neither content nor where is provided
            Exception: If sending fails
        """
        import asyncio

        return await asyncio.to_thread(
            self.send_fatheavy,
            recipient=recipient,
            who=who,
            what=what,
            content=content,
            content_type=content_type,
            filename=filename,
            custom_metadata=custom_metadata,
            options=options,
            where=where,
            expose_ttl=expose_ttl,
        )

    def received(self, message: TransportMessage) -> None:
        """Hook called after receiving and parsing a message.

        Override this method in subclasses to add custom behavior:
        - Storage integration (fetch heavy content, save to storage)
        - Metrics collection
        - Validation
        - Notifications
        - Auditing

        Should have side effects only (no return value).
        Should not modify the message object itself.
        CAN raise exceptions to reject the message.

        Args:
            message: Successfully parsed TransportMessage

        Raises:
            Any exception to reject message and propagate error

        Default implementation: no-op
        """
        pass

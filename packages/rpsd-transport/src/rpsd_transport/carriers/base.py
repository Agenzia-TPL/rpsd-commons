"""
Base carrier abstract class for transport implementations.
"""

from abc import ABC, abstractmethod

from fastapi import Request

from rpsd_transport.models import TransportMessage


class BaseCarrier(ABC):
    """
    Abstract base class for transport carriers.

    Carriers implement different transport mechanisms (HTTP, PubSub, etc.)
    for sending and receiving data in both fast and heavy modes.

    Methods to implement:
    - send_slimfast: Send content inline (fast/slim mode)
    - send_fatheavy: Send content by reference (heavy/fat mode)
    - receive: Parse incoming message and return TransportMessage

    Hook methods to override:
    - received: Called after successful message parsing for custom behavior
      (storage integration, metrics, validation, etc.)
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
        metadata_use_inline: bool = True,
        metadata_use_headers: bool = True,
        content_use_body: bool = True,
    ) -> dict:
        """
        Send data inline (fast/slim mode).

        Args:
            recipient: Target identifier (URL for HTTP, topic/channel for PubSub, etc.)
            who: Entity identifier
            what: Content type/category
            content: Data to send
            content_type: MIME type of the data
            filename: Optional original filename
            metadata_use_inline: True=inline JSON, False=outline headers/query
            metadata_use_headers: True=headers, False=query params
                (when metadata_use_inline=False)
            content_use_body: True=raw body, False=multipart
                (when metadata_use_inline=False)

        Returns:
            dict: Response from recipient (SuccessResponse or ErrorResponse)

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
        metadata_use_inline: bool = True,
        metadata_use_headers: bool = True,
        where: str | None = None,
        expose_ttl: int = 3600,
    ) -> dict:
        """
        Send data by reference (heavy/fat mode).

        Either content or where must be provided.

        Args:
            recipient: Target identifier (URL for HTTP, topic/channel for PubSub, etc.)
            who: Entity identifier
            what: Content type/category
            content: New data to save and expose (Phase 2) or None
            content_type: MIME type of the data
            filename: Optional original filename
            metadata_use_inline: True=inline JSON, False=outline headers/query
            metadata_use_headers: True=headers, False=query params
                (when metadata_use_inline=False)
            where: URL where content is available
            expose_ttl: Time-to-live for exposed URL in seconds

        Returns:
            dict: Response from recipient (SuccessResponse or ErrorResponse)

        Raises:
            ValueError: If neither content nor where is provided
            Exception: If sending fails
        """
        pass

    @abstractmethod
    async def receive(self, request: Request) -> TransportMessage:
        """
        Receive and parse incoming message.

        Extracts metadata and content (if fast message) from the carrier's
        native request format. Logs the message and calls received() hook.
        Does not fetch heavy content or save to storage.

        Args:
            request: Request object (FastAPI Request for HTTP/PubSub carriers)

        Returns:
            TransportMessage: Parsed message ready for processing

        Raises:
            Various transport exceptions for malformed requests
        """
        pass

    def received(self, message: TransportMessage) -> None:
        """
        Hook called after successfully receiving and parsing a message.

        Override this method in subclasses to add custom behavior:
        - Storage integration (fetch heavy content, save to storage)
        - Metrics collection
        - Validation
        - Notifications
        - Auditing

        Should have side effects only (no return value).
        Should not modify the message object itself.
        CAN raise exceptions to reject the message (validation, storage errors, etc.)

        Args:
            message: Successfully parsed TransportMessage

        Raises:
            Any exception to reject message and propagate error to caller

        Default implementation: no-op
        """
        pass

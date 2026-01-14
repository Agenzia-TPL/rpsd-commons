"""
Base carrier abstract class for transport implementations.
"""

from abc import ABC, abstractmethod


class BaseCarrier(ABC):
    """
    Abstract base class for transport carriers.

    Carriers implement different transport mechanisms (HTTP, Dapr, etc.)
    for sending and receiving data in both fast and heavy modes.
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
            recipient: Target identifier (URL for HTTP, app_id for Dapr, etc.)
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
            recipient: Target identifier (URL for HTTP, app_id for Dapr, etc.)
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

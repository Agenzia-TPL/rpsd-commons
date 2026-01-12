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
        data: bytes,
        who: str,
        what: str,
        content_type: str = "application/octet-stream",
        filename: str | None = None,
    ) -> dict:
        """
        Send data inline (fast/slim mode).

        Args:
            recipient: Target identifier (URL for HTTP, app_id for Dapr, etc.)
            data: Data to send (inlined in message)
            who: Entity identifier
            what: Content type/category
            content_type: MIME type of the data
            filename: Optional original filename

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
        data: bytes | None = None,
        storage_url: str | None = None,
        expose_ttl: int = 3600,
        content_type: str = "application/octet-stream",
        filename: str | None = None,
    ) -> dict:
        """
        Send data by reference (heavy/fat mode).

        Either data or storage_url must be provided.

        Args:
            recipient: Target identifier (URL for HTTP, app_id for Dapr, etc.)
            who: Entity identifier
            what: Content type/category
            data: New data to save and expose (if storage_url not provided)
            storage_url: Existing storage URL to expose (if data not provided)
            expose_ttl: Time-to-live for exposed URL in seconds
            content_type: MIME type of the data
            filename: Optional original filename

        Returns:
            dict: Response from recipient (SuccessResponse or ErrorResponse)

        Raises:
            ValueError: If neither data nor storage_url is provided
            Exception: If sending fails
        """
        pass

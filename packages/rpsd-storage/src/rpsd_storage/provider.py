from abc import ABC, abstractmethod
from typing import Any


class StorageProvider(ABC):
    """
    Abstract base class for storage providers.
    """

    @abstractmethod
    def save(
        self,
        content,
        filename,
        content_type="application/xml",
        source_url=None,
        who=None,
        what=None,
        custom_metadata=None,
    ):
        """
        Saves content to the storage provider.
        """
        pass

    @abstractmethod
    def load(self, object_id: str) -> tuple[bytes, dict[str, Any]]:
        """
        Loads content and metadata from the storage provider using the object_id.

        Args:
            object_id: The object ID returned by the save() method

        Returns:
            tuple: A tuple containing:
                - content (bytes): The file content
                - metadata (dict): The metadata associated with the file

        Raises:
            FileNotFoundError: If the object with the given ID does not exist
            Exception: For other storage-related errors
        """
        pass

from abc import ABC, abstractmethod
from typing import Any
from urllib.parse import urlparse


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
    ) -> tuple[str, dict[str, Any]]:
        """
        Saves content to the storage provider.

        Returns:
            tuple: A tuple containing:
                - url (str): Complete URL of the saved object/file
                - metadata (dict): The metadata associated with the file
        """
        pass

    @abstractmethod
    def load(self, url: str) -> tuple[bytes, dict[str, Any]]:
        """
        Loads content and metadata from the storage provider using the URL.

        Args:
            url: The complete URL returned by the save() method

        Returns:
            tuple: A tuple containing:
                - content (bytes): The file content
                - metadata (dict): The metadata associated with the file

        Raises:
            FileNotFoundError: If the object at the given URL does not exist
            Exception: For other storage-related errors
        """
        pass

    def load_by_parts(
        self, who: str, what: str, object_id: str
    ) -> tuple[bytes, dict[str, Any]]:
        """
        Convenience method to load content using separate who, what, and object_id.

        Args:
            who: The "who" value
            what: The "what" value
            object_id: The object ID (UUID)

        Returns:
            tuple: A tuple containing:
                - content (bytes): The file content
                - metadata (dict): The metadata associated with the file
        """
        url = self._build_url(who, what, object_id)
        return self.load(url)

    @abstractmethod
    def _build_url(self, who: str, what: str, object_id: str) -> str:
        """
        Builds the complete URL for the given parameters.
        Note: object_id now includes the file extension
        """
        pass

    @staticmethod
    def load_from_url(url: str) -> tuple[bytes, dict[str, Any]]:
        """
        Static method to load content using URL, automatically selecting the provider.

        Args:
            url: The complete URL (e.g., s3://bucket/path or file:///path)

        Returns:
            tuple: A tuple containing:
                - content (bytes): The file content
                - metadata (dict): The metadata associated with the file
        """
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()

        if scheme == "s3":
            from rpsd_storage.s3 import S3StorageProvider

            bucket_name = parsed.netloc
            provider = S3StorageProvider(bucket_name)
            return provider.load(url)
        elif scheme == "file":
            # For FS URLs, we need to extract a reasonable base path
            # The URL format is file:///base_path/who/what/object_id
            # We'll use a temporary provider just to call load method
            import tempfile

            from rpsd_storage.fs import FSStorageProvider

            with tempfile.TemporaryDirectory() as temp_dir:
                provider = FSStorageProvider(temp_dir)
                return provider.load(url)
        else:
            raise ValueError(f"Unsupported URL scheme: {scheme}")

    @staticmethod
    def load_from_parts(
        who: str, what: str, object_id: str
    ) -> tuple[bytes, dict[str, Any]]:
        """
        Static convenience method to load content using separate parameters.
        Note: This requires a configured default provider since we can't determine
        the provider type from the parameters alone.

        Args:
            who: The "who" value
            what: The "what" value
            object_id: The object ID (UUID)

        Returns:
            tuple: A tuple containing:
                - content (bytes): The file content
                - metadata (dict): The metadata associated with the file
        """
        from rpsd_storage import storage_provider

        return storage_provider.load_by_parts(who, what, object_id)

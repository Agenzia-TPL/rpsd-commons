# SPDX-License-Identifier: BSD-3-Clause
# SPDX-FileCopyrightText: 2026 AGENZIA TPL BACINO CITTA' METROPOLITANA MILANO,
# MONZA E BRIANZA, LODI, PAVIA
import mimetypes
from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from typing import BinaryIO
from urllib.parse import urlparse

from rpsd_storage.metadata import StorageMetadata


class StorageProvider(ABC):
    """
    Abstract base class for storage providers.
    """

    def __init__(self, *, compare_before_save: bool = False) -> None:
        self.compare_before_save = compare_before_save

    @staticmethod
    def extension_from_mime(mime_type: str) -> str:
        """
        Convert a MIME type to a file extension.

        Uses Python's mimetypes module with overrides for common quirks.

        Args:
            mime_type: MIME type string (e.g., "application/json")

        Returns:
            str: File extension including the dot (e.g., ".json")
                 Falls back to ".xml" if no mapping is found.

        Example:
            >>> StorageProvider.extension_from_mime("application/json")
            '.json'
            >>> StorageProvider.extension_from_mime("application/xml")
            '.xml'
            >>> StorageProvider.extension_from_mime("unknown/type")
            '.xml'
        """
        # Override dict for MIME types where mimetypes module
        # returns unexpected extensions
        overrides = {
            "application/xml": ".xml",  # Default returns .xsl
        }

        if mime_type in overrides:
            return overrides[mime_type]

        extension = mimetypes.guess_extension(mime_type)
        return extension if extension else ".xml"

    @abstractmethod
    def save(
        self,
        content,
        filename,
        who: str,
        what: str,
        content_type="application/xml",
        source_url=None,
        custom_metadata=None,
        compare_before_save: bool | None = None,
    ) -> tuple[str, StorageMetadata]:
        """
        Saves content to the storage provider.

        Args:
            content: The content to save
            filename: The original filename
            content_type: The MIME type of the content (default: "application/xml")
            source_url: Optional source URL where content was originally located
            who: Required identifier for the entity saving the content
            what: Required identifier for the content type/category
            custom_metadata: Optional additional metadata
            compare_before_save: Per-call override for deduplication. When True,
                skip the write if an identical or newer version already exists.
                When False, always write. When None (default), falls back to
                the instance-level compare_before_save setting.

        Returns:
            tuple: A tuple containing:
                - url (str): Complete URL of the saved object/file
                - metadata (StorageMetadata): The metadata associated with the file
        """
        pass

    @abstractmethod
    def load(self, url: str) -> tuple[bytes, StorageMetadata]:
        """
        Loads content and metadata from the storage provider using the URL.

        Args:
            url: The complete URL returned by the save() method

        Returns:
            tuple: A tuple containing:
                - content (bytes): The file content
                - metadata (StorageMetadata): The metadata associated with the file

        Raises:
            FileNotFoundError: If the object at the given URL does not exist
            Exception: For other storage-related errors
        """
        pass

    @abstractmethod
    def load_content(self, url: str) -> bytes:
        """
        Loads only the content from the storage provider using the URL.

        Args:
            url: The complete URL returned by the save() method

        Returns:
            bytes: The file content

        Raises:
            FileNotFoundError: If the object at the given URL does not exist
            Exception: For other storage-related errors
        """
        pass

    @abstractmethod
    def open_content(self, url: str) -> AbstractContextManager[BinaryIO]:
        """
        Open the content at *url* as a binary stream (content only).

        Streaming counterpart of load_content(): instead of returning the full
        payload as bytes, this returns a context manager yielding a readable
        binary file-like object, so large files can be processed without
        buffering the whole content in memory (e.g. lxml's etree.parse(stream)).

        The stream is closed when the context exits; callers must NOT close it
        themselves.

        Args:
            url: The complete URL returned by the save() method

        Returns:
            AbstractContextManager[BinaryIO]: Context manager yielding a readable
            binary stream (supports .read(n), iteration). The stream is NOT
            seekable for the HTTP and S3 providers; the FS provider returns a
            seekable file handle. Callers needing seek can read into io.BytesIO.

        Raises:
            FileNotFoundError: If the object at the given URL does not exist
            Exception: For other storage-related errors
        """
        pass

    @abstractmethod
    def load_metadata(self, url: str) -> StorageMetadata:
        """
        Loads only the metadata from the storage provider using the URL.

        Args:
            url: The complete URL returned by the save() method

        Returns:
            StorageMetadata: The metadata associated with the file

        Raises:
            FileNotFoundError: If the object at the given URL does not exist
            Exception: For other storage-related errors
        """
        pass

    @abstractmethod
    def delete(self, url: str) -> None:
        """
        Deletes the object from the storage provider using the URL.

        Args:
            url: The complete URL returned by the save() method

        Raises:
            FileNotFoundError: If the object at the given URL does not exist
            Exception: For other storage-related errors
        """
        pass

    def load_by_parts(
        self, who: str, what: str, object_id: str
    ) -> tuple[bytes, StorageMetadata]:
        """
        Convenience method to load content using separate who, what, and object_id.

        Args:
            who: The "who" value
            what: The "what" value
            object_id: The object ID (UUID)

        Returns:
            tuple: A tuple containing:
                - content (bytes): The file content
                - metadata (StorageMetadata): The metadata associated with the file
        """
        url = self._build_url(who, what, object_id)
        return self.load(url)

    def load_content_by_parts(self, who: str, what: str, object_id: str) -> bytes:
        """
        Convenience method to load only content using separate who, what, and object_id.

        Args:
            who: The "who" value
            what: The "what" value
            object_id: The object ID (UUID)

        Returns:
            bytes: The file content
        """
        url = self._build_url(who, what, object_id)
        return self.load_content(url)

    def open_content_by_parts(
        self, who: str, what: str, object_id: str
    ) -> AbstractContextManager[BinaryIO]:
        """
        Convenience method to open a content stream using separate parameters.

        Streaming counterpart of load_content_by_parts().

        Args:
            who: The "who" value
            what: The "what" value
            object_id: The object ID (UUID)

        Returns:
            AbstractContextManager[BinaryIO]: Context manager yielding a readable
            binary stream. The caller must NOT close the stream itself.
        """
        url = self._build_url(who, what, object_id)
        return self.open_content(url)

    def load_metadata_by_parts(
        self, who: str, what: str, object_id: str
    ) -> StorageMetadata:
        """
        Convenience method to load only metadata using separate parameters.

        Args:
            who: The "who" value
            what: The "what" value
            object_id: The object ID (UUID)

        Returns:
            StorageMetadata: The metadata associated with the file
        """
        url = self._build_url(who, what, object_id)
        return self.load_metadata(url)

    @abstractmethod
    def _build_url(self, who: str, what: str, object_id: str) -> str:
        """
        Builds the complete URL for the given parameters.
        Note: object_id now includes the file extension
        """
        pass

    @staticmethod
    def load_from_url(url: str) -> tuple[bytes, StorageMetadata]:
        """
        Static method to load content using URL, automatically selecting the provider.

        Args:
            url: The complete URL (e.g., s3://bucket/path or file:///path)

        Returns:
            tuple: A tuple containing:
                - content (bytes): The file content
                - metadata (StorageMetadata): The metadata associated with the file
        """
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()

        if scheme == "s3":
            from rpsd_storage.providers.s3 import S3StorageProvider

            bucket_name = parsed.netloc
            provider = S3StorageProvider(bucket_name)
            return provider.load(url)
        elif scheme == "file":
            # For FS URLs, we need to extract a reasonable base path
            # The URL format is file:///base_path/who/what/object_id
            # We'll use a temporary provider just to call load method
            import tempfile

            from rpsd_storage.providers.fs import FSStorageProvider

            with tempfile.TemporaryDirectory() as temp_dir:
                provider = FSStorageProvider(temp_dir)
                return provider.load(url)
        elif scheme in ("http", "https"):
            from rpsd_storage.providers.http import HTTPStorageProvider

            provider = HTTPStorageProvider()
            return provider.load(url)
        else:
            raise ValueError(f"Unsupported URL scheme: {scheme}")

    @staticmethod
    def load_content_from_url(url: str) -> bytes:
        """
        Static method to load only content using URL, auto-selecting the provider.

        Args:
            url: The complete URL (e.g., s3://bucket/path or file:///path)

        Returns:
            bytes: The file content
        """
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()

        if scheme == "s3":
            from rpsd_storage.providers.s3 import S3StorageProvider

            bucket_name = parsed.netloc
            provider = S3StorageProvider(bucket_name)
            return provider.load_content(url)
        elif scheme == "file":
            import tempfile

            from rpsd_storage.providers.fs import FSStorageProvider

            with tempfile.TemporaryDirectory() as temp_dir:
                provider = FSStorageProvider(temp_dir)
                return provider.load_content(url)
        elif scheme in ("http", "https"):
            from rpsd_storage.providers.http import HTTPStorageProvider

            provider = HTTPStorageProvider()
            return provider.load_content(url)
        else:
            raise ValueError(f"Unsupported URL scheme: {scheme}")

    @staticmethod
    def open_content_from_url(url: str) -> AbstractContextManager[BinaryIO]:
        """
        Static method to open a content stream using URL, auto-selecting the
        provider.

        Streaming counterpart of load_content_from_url().

        Args:
            url: The complete URL (e.g., s3://bucket/path or file:///path)

        Returns:
            AbstractContextManager[BinaryIO]: Context manager yielding a readable
            binary stream. The caller must NOT close the stream itself.
        """
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()

        if scheme == "s3":
            from rpsd_storage.providers.s3 import S3StorageProvider

            bucket_name = parsed.netloc
            provider = S3StorageProvider(bucket_name)
            return provider.open_content(url)
        elif scheme == "file":
            import tempfile

            from rpsd_storage.providers.fs import FSStorageProvider

            # The returned stream targets the URL's own absolute path, so the
            # temp base dir is irrelevant to the stream and its teardown here
            # is harmless (mirrors load_content_from_url's idiom).
            with tempfile.TemporaryDirectory() as temp_dir:
                provider = FSStorageProvider(temp_dir)
                return provider.open_content(url)
        elif scheme in ("http", "https"):
            from rpsd_storage.providers.http import HTTPStorageProvider

            provider = HTTPStorageProvider()
            return provider.open_content(url)
        else:
            raise ValueError(f"Unsupported URL scheme: {scheme}")

    @staticmethod
    def load_metadata_from_url(url: str) -> StorageMetadata:
        """
        Static method to load only metadata using URL, auto-selecting the provider.

        Args:
            url: The complete URL (e.g., s3://bucket/path or file:///path)

        Returns:
            StorageMetadata: The metadata associated with the file
        """
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()

        if scheme == "s3":
            from rpsd_storage.providers.s3 import S3StorageProvider

            bucket_name = parsed.netloc
            provider = S3StorageProvider(bucket_name)
            return provider.load_metadata(url)
        elif scheme == "file":
            import tempfile

            from rpsd_storage.providers.fs import FSStorageProvider

            with tempfile.TemporaryDirectory() as temp_dir:
                provider = FSStorageProvider(temp_dir)
                return provider.load_metadata(url)
        elif scheme in ("http", "https"):
            from rpsd_storage.providers.http import HTTPStorageProvider

            provider = HTTPStorageProvider()
            return provider.load_metadata(url)
        else:
            raise ValueError(f"Unsupported URL scheme: {scheme}")

    @staticmethod
    def compare_from_url(current_url: str, candidate_url: str) -> int:
        """
        Compare metadata from two URLs to determine their relationship.

        This static method loads metadata from both URLs and compares them
        using StorageMetadata.compare() to determine if the candidate
        represents an update, identical content, or older content.

        Args:
            current_url: URL of the currently stored/existing content
            candidate_url: URL of the candidate content to compare

        Returns:
            int: Comparison result:
                -1: candidate is older than current
                 0: candidate has identical content to current
                 1: candidate is newer than current

        Raises:
            ValueError: If who or what fields differ between the metadata
            FileNotFoundError: If either URL does not exist
            Exception: For other storage-related errors

        Example:
            >>> result = StorageProvider.compare_from_url(
            ...     "s3://bucket/who/what/id1.xml",
            ...     "s3://bucket/who/what/id2.xml"
            ... )
            >>> if result == 1:
            ...     print("Candidate is an update")
        """
        current_metadata = StorageProvider.load_metadata_from_url(current_url)
        candidate_metadata = StorageProvider.load_metadata_from_url(candidate_url)
        return StorageMetadata.compare(current_metadata, candidate_metadata)

    @staticmethod
    def delete_from_url(url: str) -> None:
        """
        Static method to delete object using URL, automatically selecting the provider.

        Args:
            url: The complete URL (e.g., s3://bucket/path or file:///path)

        Raises:
            FileNotFoundError: If the object at the given URL does not exist
            Exception: For other storage-related errors
        """
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()

        if scheme == "s3":
            from rpsd_storage.providers.s3 import S3StorageProvider

            bucket_name = parsed.netloc
            provider = S3StorageProvider(bucket_name)
            provider.delete(url)
        elif scheme == "file":
            import tempfile

            from rpsd_storage.providers.fs import FSStorageProvider

            with tempfile.TemporaryDirectory() as temp_dir:
                provider = FSStorageProvider(temp_dir)
                provider.delete(url)
        elif scheme in ("http", "https"):
            from rpsd_storage.providers.http import HTTPStorageProvider

            provider = HTTPStorageProvider()
            provider.delete(url)
        else:
            raise ValueError(f"Unsupported URL scheme: {scheme}")

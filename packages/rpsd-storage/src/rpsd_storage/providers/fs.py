import hashlib
import json
import logging
import os
import uuid
from datetime import UTC, datetime
from urllib.parse import urlparse

from rpsd_storage.metadata import StorageMetadata
from rpsd_storage.providers.base import StorageProvider

logger = logging.getLogger()


class FSStorageProvider(StorageProvider):
    def __init__(self, base_path):
        if not base_path:
            raise Exception("FS base path not configured")
        self.base_path = base_path
        os.makedirs(self.base_path, exist_ok=True)

    def _build_url(self, who: str, what: str, object_id: str) -> str:
        """
        Builds the complete file system URL for the given parameters.
        Format: file:///base_path/who/what/object_id
        Note: object_id now includes the extension
        """
        path = os.path.join(self.base_path, who, what, object_id)
        return f"file://{path}"

    def save(
        self,
        content,
        filename,
        who: str,
        what: str,
        content_type="application/xml",
        source_url=None,
        custom_metadata=None,
    ) -> tuple[str, StorageMetadata]:
        """
        Saves content to the file system.
        """
        uuid_part = str(uuid.uuid4())
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

        # Determine file extension with priority:
        # 1. From filename if provided and has extension
        # 2. From content_type using MIME type mapping
        # 3. Default to .xml
        file_extension = os.path.splitext(filename)[1] if filename else ""
        if not file_extension:
            file_extension = StorageProvider.extension_from_mime(content_type)

        # Include extension in object_id to make it complete
        object_id = f"{uuid_part}{file_extension}"

        # Create directory structure: who/what/
        dir_path = os.path.join(self.base_path, who, what)
        os.makedirs(dir_path, exist_ok=True)

        file_path = os.path.join(dir_path, object_id)

        # Build the complete URL using the actual file path
        url = f"file://{file_path}"

        metadata = StorageMetadata(
            provider="fs",
            url=url,
            content_type=content_type,
            content_length=len(content),
            hash=hashlib.md5(content).hexdigest(),
            who=who,
            what=what,
            original_filename=filename or "unknown",
            object_id=object_id,
            save_stamp=timestamp,
            schema_version=1,
            source_url=source_url or "",
            custom_metadata=custom_metadata or {},
        )

        with open(file_path, "wb") as f:
            f.write(content)

        with open(f"{file_path}.meta", "w") as f:
            f.write(metadata.model_dump_json(indent=4))

        logger.info(f"Saved to file system: {file_path}")
        return url, metadata

    def _parse_and_validate_url(self, url: str) -> str:
        """
        Parse and validate FS URL, returning file path.

        Args:
            url: File system URL to parse

        Returns:
            str: file_path

        Raises:
            ValueError: If URL is invalid
        """
        parsed = urlparse(url)
        if parsed.scheme != "file":
            raise ValueError(f"Invalid URL scheme for FS provider: {parsed.scheme}")

        file_path = parsed.path
        if not os.path.isabs(file_path):
            raise ValueError(f"FS URL must contain absolute path: {url}")

        return file_path

    def _load_file_content(self, file_path: str) -> bytes:
        """
        Load content from file.

        Args:
            file_path: Path to the content file

        Returns:
            bytes: File content

        Raises:
            FileNotFoundError: If file not found
        """
        try:
            with open(file_path, "rb") as f:
                return f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"Content file not found: {file_path}")

    def _load_file_metadata(self, file_path: str) -> StorageMetadata:
        """
        Load metadata from .meta file.

        Args:
            file_path: Path to the content file (metadata file is file_path + ".meta")

        Returns:
            StorageMetadata: Metadata

        Raises:
            FileNotFoundError: If metadata file not found
            Exception: If metadata file is invalid JSON
        """
        meta_path = f"{file_path}.meta"
        try:
            with open(meta_path) as f:
                data = json.load(f)
                return StorageMetadata.model_validate(data)
        except FileNotFoundError:
            raise FileNotFoundError(f"Metadata file not found: {meta_path}")
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid metadata file {meta_path}: {e}")

    def load(self, url: str) -> tuple[bytes, StorageMetadata]:
        """
        Loads content and metadata from the file system using the URL.
        """
        file_path = self._parse_and_validate_url(url)
        content = self._load_file_content(file_path)
        metadata = self._load_file_metadata(file_path)

        logger.info(f"Loaded from file system: {file_path}")
        return content, metadata

    def load_content(self, url: str) -> bytes:
        """
        Loads only the content from the file system using the URL.
        """
        file_path = self._parse_and_validate_url(url)
        content = self._load_file_content(file_path)

        logger.info(f"Loaded content from file system: {file_path}")
        return content

    def load_metadata(self, url: str) -> StorageMetadata:
        """
        Loads only the metadata from the file system using the URL.
        """
        file_path = self._parse_and_validate_url(url)
        metadata = self._load_file_metadata(file_path)

        logger.info(f"Loaded metadata from file system: {file_path}")
        return metadata

    def delete(self, url: str) -> None:
        """
        Deletes the object from the file system using the URL.
        """
        file_path = self._parse_and_validate_url(url)
        meta_path = f"{file_path}.meta"

        # Check if content file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Content file not found: {file_path}")

        # Delete content file
        try:
            os.remove(file_path)
        except OSError as e:
            raise Exception(f"Failed to delete content file {file_path}: {e}")

        # Delete metadata file if it exists
        if os.path.exists(meta_path):
            try:
                os.remove(meta_path)
            except OSError as e:
                # Log warning but don't fail deletion if metadata file can't be removed
                logger.warning(f"Failed to delete metadata file {meta_path}: {e}")

        logger.info(f"Deleted from file system: {file_path}")

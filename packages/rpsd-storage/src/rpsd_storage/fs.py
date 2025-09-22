import json
import logging
import os
import uuid
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from rpsd_storage.provider import StorageProvider

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
        if who and what:
            path = os.path.join(self.base_path, who, what, object_id)
        else:
            path = os.path.join(self.base_path, object_id)
        return f"file://{path}"

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
        Saves content to the file system.
        """
        uuid_part = str(uuid.uuid4())
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

        file_extension = os.path.splitext(filename)[1] if filename else ".xml"
        if not file_extension:
            file_extension = ".xml"

        # Include extension in object_id to make it complete
        object_id = f"{uuid_part}{file_extension}"

        # Create directory structure: who/what/
        if who and what:
            dir_path = os.path.join(self.base_path, who, what)
        else:
            dir_path = self.base_path
        os.makedirs(dir_path, exist_ok=True)

        file_path = os.path.join(dir_path, object_id)

        metadata = {
            "object_id": object_id,
            "original_filename": filename or "unknown",
            "ingestion_timestamp": timestamp,
            "content_type": content_type,
        }
        if source_url:
            metadata["source_url"] = source_url
        if who:
            metadata["who"] = who
        if what:
            metadata["what"] = what
        if custom_metadata:
            metadata["custom_metadata"] = custom_metadata

        with open(file_path, "wb") as f:
            f.write(content)

        with open(f"{file_path}.meta", "w") as f:
            json.dump(metadata, f)

        # Build the complete URL using the actual file path
        url = f"file://{file_path}"

        logger.info(f"Saved to file system: {file_path}")
        return url, metadata

    def load(self, url: str) -> tuple[bytes, dict[str, Any]]:
        """
        Loads content and metadata from the file system using the URL.
        """
        # Parse the URL to get the file path
        parsed = urlparse(url)
        if parsed.scheme != "file":
            raise ValueError(f"Invalid URL scheme for FS provider: {parsed.scheme}")

        file_path = parsed.path
        if not os.path.isabs(file_path):
            raise ValueError(f"FS URL must contain absolute path: {url}")

        meta_path = f"{file_path}.meta"

        # Load the file content
        try:
            with open(file_path, "rb") as f:
                content = f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"Content file not found: {file_path}")

        # Load the metadata
        try:
            with open(meta_path) as f:
                metadata = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Metadata file not found: {meta_path}")
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid metadata file {meta_path}: {e}")

        logger.info(f"Loaded from file system: {file_path}")
        return content, metadata

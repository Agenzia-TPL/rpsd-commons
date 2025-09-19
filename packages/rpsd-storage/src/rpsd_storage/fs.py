import json
import logging
import os
import uuid
from datetime import UTC, datetime

from rpsd_storage.provider import StorageProvider

logger = logging.getLogger()


class FSStorageProvider(StorageProvider):
    def __init__(self, base_path):
        if not base_path:
            raise Exception("FS base path not configured")
        self.base_path = base_path
        os.makedirs(self.base_path, exist_ok=True)

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
        Saves content to the file system.
        """
        object_id = str(uuid.uuid4())
        if who:
            object_id = f"{who}-{object_id}"
        if what:
            object_id = f"{what}-{object_id}"

        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

        file_extension = os.path.splitext(filename)[1] if filename else ".xml"
        if not file_extension:
            file_extension = ".xml"

        file_path = os.path.join(self.base_path, f"{object_id}{file_extension}")

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

        logger.info(f"Saved to file system: {file_path}")
        return object_id

    def load(self, object_id):
        """
        Loads content and metadata from the file system using the object_id.
        """
        # Find the file by searching for files that start with the object_id
        # Since object_id might have prefixes from who/what, we need to be flexible
        matching_files = []
        for file_path in os.listdir(self.base_path):
            if file_path.endswith(".meta"):
                continue  # Skip metadata files in the search
            # Check if this file belongs to our object_id
            base_name = os.path.splitext(file_path)[0]
            if base_name == object_id or base_name.endswith(f"-{object_id}"):
                matching_files.append(file_path)

        if not matching_files:
            raise FileNotFoundError(f"No file found for object_id: {object_id}")

        if len(matching_files) > 1:
            raise Exception(f"Multiple files found for {object_id}: {matching_files}")

        file_name = matching_files[0]
        file_path = os.path.join(self.base_path, file_name)
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
        return {
            "content": content,
            "metadata": metadata
        }

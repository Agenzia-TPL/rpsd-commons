import json
import logging
import os
import uuid
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import boto3

from rpsd_storage.provider import StorageProvider

logger = logging.getLogger()


class S3StorageProvider(StorageProvider):
    def __init__(self, bucket_name):
        if not bucket_name:
            raise Exception("S3 bucket not configured")
        self.bucket_name = bucket_name
        self.s3_client = boto3.client("s3")

    def _build_url(self, who: str, what: str, object_id: str) -> str:
        """
        Builds the complete S3 URL for the given parameters.
        Format: s3://bucket-name/who/what/object_id
        Note: object_id now includes the extension
        """
        s3_key = f"{who}/{what}/{object_id}"
        return f"s3://{self.bucket_name}/{s3_key}"

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
        Saves content to S3
        """
        uuid_part = str(uuid.uuid4())
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

        file_extension = os.path.splitext(filename)[1] if filename else ".xml"
        if not file_extension:
            file_extension = ".xml"

        # Include extension in object_id to make it complete
        object_id = f"{uuid_part}{file_extension}"

        # Create S3 key with new structure: who/what/object_id
        if who and what:
            s3_key = f"{who}/{what}/{object_id}"
        else:
            s3_key = f"ingested/{object_id}"

        metadata = {
            "object_id": object_id,
            "original_filename": filename or "unknown",
            "ingestion_timestamp": timestamp,
        }
        if source_url:
            metadata["source_url"] = source_url
        if who:
            metadata["who"] = who
        if what:
            metadata["what"] = what
        if custom_metadata:
            # S3 metadata values must be strings
            metadata["custom_metadata"] = json.dumps(custom_metadata)

        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=s3_key,
            Body=content,
            ContentType=content_type,
            Metadata=metadata,
        )

        # Build the complete URL
        url = f"s3://{self.bucket_name}/{s3_key}"

        # Add content_type to metadata for consistency with return value
        metadata["content_type"] = content_type

        logger.info(f"Uploaded to S3: {s3_key}")
        return url, metadata

    def _parse_and_validate_url(self, url: str) -> tuple[str, str]:
        """
        Parse and validate S3 URL, returning bucket name and S3 key.

        Args:
            url: S3 URL to parse

        Returns:
            tuple: (bucket_name, s3_key)

        Raises:
            ValueError: If URL is invalid or bucket doesn't match
        """
        parsed = urlparse(url)
        if parsed.scheme != "s3":
            raise ValueError(f"Invalid URL scheme for S3 provider: {parsed.scheme}")

        bucket_name = parsed.netloc
        s3_key = parsed.path.lstrip("/")  # Remove leading slash

        if bucket_name != self.bucket_name:
            raise ValueError(
                f"URL bucket {bucket_name} doesn't match provider bucket "
                f"{self.bucket_name}"
            )

        return bucket_name, s3_key

    def _handle_s3_exception(self, e: Exception, url: str, operation: str) -> None:
        """
        Handle S3 exceptions and raise appropriate errors.

        Args:
            e: The exception that occurred
            url: The URL being accessed
            operation: Description of the operation (for error messages)

        Raises:
            FileNotFoundError: If object not found
            Exception: For other S3 errors
        """
        if "NoSuchKey" in str(e) or "NotFound" in str(e):
            raise FileNotFoundError(f"Object not found: {url}")
        else:
            raise Exception(f"Failed to {operation}: {e}")

    def _extract_metadata_from_response(self, response: dict) -> dict[str, Any]:
        """
        Extract and reconstruct metadata from S3 response.

        Args:
            response: S3 response dict

        Returns:
            dict: Reconstructed metadata
        """
        s3_metadata = response.get("Metadata", {})

        # Reconstruct the metadata dict (S3 metadata keys are lowercase)
        metadata = {
            "object_id": s3_metadata.get("object_id"),
            "original_filename": s3_metadata.get("original_filename"),
            "ingestion_timestamp": s3_metadata.get("ingestion_timestamp"),
            "content_type": response.get("ContentType", "application/octet-stream"),
        }

        # Add optional metadata if present
        if "source_url" in s3_metadata:
            metadata["source_url"] = s3_metadata["source_url"]
        if "who" in s3_metadata:
            metadata["who"] = s3_metadata["who"]
        if "what" in s3_metadata:
            metadata["what"] = s3_metadata["what"]
        if "custom_metadata" in s3_metadata:
            metadata["custom_metadata"] = json.loads(s3_metadata["custom_metadata"])

        return metadata

    def load(self, url: str) -> tuple[bytes, dict[str, Any]]:
        """
        Loads content and metadata from S3 using the URL.
        """
        bucket_name, s3_key = self._parse_and_validate_url(url)

        try:
            response = self.s3_client.get_object(Bucket=bucket_name, Key=s3_key)
            content = response["Body"].read()
            metadata = self._extract_metadata_from_response(response)
        except Exception as e:
            self._handle_s3_exception(e, url, "get S3 object")

        logger.info(f"Loaded from S3: {s3_key}")
        return content, metadata

    def load_content(self, url: str) -> bytes:
        """
        Loads only the content from S3 using the URL.
        """
        bucket_name, s3_key = self._parse_and_validate_url(url)

        try:
            response = self.s3_client.get_object(Bucket=bucket_name, Key=s3_key)
            content = response["Body"].read()
        except Exception as e:
            self._handle_s3_exception(e, url, "get S3 object")

        logger.info(f"Loaded content from S3: {s3_key}")
        return content

    def load_metadata(self, url: str) -> dict[str, Any]:
        """
        Loads only the metadata from S3 using the URL.
        Uses head_object for efficiency (doesn't download content).
        """
        bucket_name, s3_key = self._parse_and_validate_url(url)

        try:
            response = self.s3_client.head_object(Bucket=bucket_name, Key=s3_key)
            metadata = self._extract_metadata_from_response(response)
        except Exception as e:
            self._handle_s3_exception(e, url, "get S3 object metadata")

        logger.info(f"Loaded metadata from S3: {s3_key}")
        return metadata

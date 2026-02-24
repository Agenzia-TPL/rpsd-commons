import hashlib
import json
import logging
import os
from datetime import UTC, datetime
from urllib.parse import urlparse

import boto3

from rpsd_storage.metadata import StorageMetadata
from rpsd_storage.providers.base import StorageProvider
from rpsd_storage.utils import generate_object_id

logger = logging.getLogger()


class S3StorageProvider(StorageProvider):
    def __init__(
        self,
        bucket_name,
        *,
        compare_before_save: bool = False,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        aws_session_token: str | None = None,
        region_name: str | None = None,
        endpoint_url: str | None = None,
    ):
        super().__init__(compare_before_save=compare_before_save)
        if not bucket_name:
            raise Exception("S3 bucket not configured")
        self.bucket_name = bucket_name
        boto3_kwargs: dict[str, str] = {}
        if aws_access_key_id is not None:
            boto3_kwargs["aws_access_key_id"] = aws_access_key_id
        if aws_secret_access_key is not None:
            boto3_kwargs["aws_secret_access_key"] = aws_secret_access_key
        if aws_session_token is not None:
            boto3_kwargs["aws_session_token"] = aws_session_token
        if region_name is not None:
            boto3_kwargs["region_name"] = region_name
        if endpoint_url is not None:
            boto3_kwargs["endpoint_url"] = endpoint_url
        self.s3_client = boto3.client("s3", **boto3_kwargs)

    def _build_url(self, who: str, what: str, object_id: str) -> str:
        """
        Builds the complete S3 URL for the given parameters.
        Format: s3://bucket-name/who/what/object_id
        Note: object_id now includes the extension
        """
        s3_key = f"{who}/{what}/{object_id}"
        return f"s3://{self.bucket_name}/{s3_key}"

    def _find_latest_metadata(self, who: str, what: str) -> StorageMetadata | None:
        """
        Find the latest stored metadata for a (who, what) pair.

        Uses list_objects_v2 with MaxKeys=1. S3 lists in
        ascending order, and bit-flipped UUID7 means the newest
        object has the smallest key, so it comes first.

        Returns:
            StorageMetadata of the latest object, or None.
        """
        prefix = f"{who}/{what}/"
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=1,
            )
        except Exception:
            return None
        contents = response.get("Contents", [])
        if not contents:
            return None
        newest_key = contents[0]["Key"]
        try:
            head = self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=newest_key,
            )
            return self._extract_metadata_from_response(head)
        except Exception:
            return None

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
        Saves content to S3
        """
        uuid_part = generate_object_id()
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

        # Create S3 key with structure: who/what/object_id
        s3_key = f"{who}/{what}/{object_id}"

        # Calculate hash and content length
        content_length = len(content)
        md5_hash = hashlib.md5(content).hexdigest()

        # Build the complete URL
        url = f"s3://{self.bucket_name}/{s3_key}"

        metadata = StorageMetadata(
            provider="s3",
            url=url,
            content_type=content_type,
            content_length=content_length,
            hash=md5_hash,
            who=who,
            what=what,
            original_filename=filename or "unknown",
            object_id=object_id,
            save_stamp=timestamp,
            schema_version=1,
            source_url=source_url or "",
            **({"custom_metadata": custom_metadata} if custom_metadata else {}),
        )

        # Compare-before-save: skip write if not a newer update
        if self.compare_before_save:
            existing = self._find_latest_metadata(who, what)
            if existing is not None:
                if StorageMetadata.compare(existing, metadata) != 1:
                    existing.deduplicated = True
                    return existing.url, existing

        # S3 metadata must be strings
        s3_metadata = {
            k: str(v)
            for k, v in metadata.model_dump(exclude_none=True).items()
            if k != "custom_metadata"
        }
        if custom_metadata:
            s3_metadata["custom_metadata"] = json.dumps(custom_metadata)

        response = self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=s3_key,
            Body=content,
            ContentType=content_type,
            Metadata=s3_metadata,
        )

        # Add ETag to metadata
        if response and "ETag" in response and response["ETag"]:
            metadata.etag = response["ETag"].strip('"')

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

    def _extract_metadata_from_response(self, response: dict) -> StorageMetadata:
        """
        Extract and reconstruct metadata from S3 response.

        Args:
            response: S3 response dict

        Returns:
            StorageMetadata: Reconstructed metadata
        """
        s3_metadata = response.get("Metadata", {})

        # Create a dictionary to build the complete metadata
        metadata_dict = s3_metadata.copy()

        # Add provider field (required)
        metadata_dict["provider"] = "s3"

        # Add standard headers from the response
        if "ContentType" in response:
            metadata_dict["content_type"] = response["ContentType"]
        if "ContentLength" in response:
            metadata_dict["content_length"] = response["ContentLength"]

        etag = response.get("ETag", "")
        if etag:
            metadata_dict["etag"] = etag.strip('"')

        # Handle custom_metadata if it exists, otherwise set to empty dict
        if "custom_metadata" in metadata_dict:
            metadata_dict["custom_metadata"] = json.loads(
                metadata_dict["custom_metadata"]
            )
        else:
            metadata_dict["custom_metadata"] = {}

        # Ensure all required fields are present with defaults if missing
        required_defaults = {
            "url": "",
            "content_length": 0,
            "hash": "",
            "schema_version": 1,
            "source_url": "",
            "original_filename": "unknown",
            "object_id": "",
            "save_stamp": "",
            "who": "",
            "what": "",
        }

        for field, default_value in required_defaults.items():
            if field not in metadata_dict:
                metadata_dict[field] = default_value

        return StorageMetadata.model_validate(metadata_dict)

    def load(self, url: str) -> tuple[bytes, StorageMetadata]:
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

    def load_metadata(self, url: str) -> StorageMetadata:
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

    def delete(self, url: str) -> None:
        """
        Deletes the object from S3 using the URL.
        """
        bucket_name, s3_key = self._parse_and_validate_url(url)

        try:
            self.s3_client.delete_object(Bucket=bucket_name, Key=s3_key)
        except Exception as e:
            self._handle_s3_exception(e, url, "delete S3 object")

        logger.info(f"Deleted from S3: {s3_key}")

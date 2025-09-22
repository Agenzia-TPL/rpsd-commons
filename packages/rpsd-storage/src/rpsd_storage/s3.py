import json
import logging
import os
import uuid
from datetime import UTC, datetime

import boto3

from rpsd_storage.provider import LoadResult, StorageProvider

logger = logging.getLogger()


class S3StorageProvider(StorageProvider):
    def __init__(self, bucket_name):
        if not bucket_name:
            raise Exception("S3 bucket not configured")
        self.bucket_name = bucket_name
        self.s3_client = boto3.client("s3")

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
        Saves content to S3
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

        s3_key = f"ingested/{object_id}{file_extension}"

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

        logger.info(f"Uploaded to S3: {s3_key}")
        return object_id

    def load(self, object_id: str) -> LoadResult:
        """
        Loads content and metadata from S3 using the object_id.
        """
        # Search for objects that match the object_id pattern
        # Since object_id might have prefixes from who/what, we need to be flexible
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix="ingested/"
            )
        except Exception as e:
            raise Exception(f"Failed to list S3 objects: {e}")

        if "Contents" not in response:
            raise FileNotFoundError(f"No objects found in bucket {self.bucket_name}")

        # Find matching objects
        matching_keys = []
        for obj in response["Contents"]:
            key = obj["Key"]
            # Extract the object name part (without ingested/ prefix and file extension)
            if key.startswith("ingested/"):
                obj_name = key[9:]  # Remove "ingested/" prefix
                base_name = os.path.splitext(obj_name)[0]
                if base_name == object_id or base_name.endswith(f"-{object_id}"):
                    matching_keys.append(key)

        if not matching_keys:
            raise FileNotFoundError(f"No S3 object found for object_id: {object_id}")

        if len(matching_keys) > 1:
            raise Exception(f"Multiple S3 objects for {object_id}: {matching_keys}")

        s3_key = matching_keys[0]

        # Load the object content and metadata
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            content = response["Body"].read()

            # Extract metadata from S3 object metadata
            s3_metadata = response.get("Metadata", {})

            # Reconstruct the metadata dict (S3 metadata keys are lowercase)
            metadata = {
                "object_id": s3_metadata.get("object_id"),
                "original_filename": s3_metadata.get("original_filename"),
                "ingestion_timestamp": s3_metadata.get("ingestion_timestamp"),
                "content_type": response.get("ContentType", "application/octet-stream")
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

        except self.s3_client.exceptions.NoSuchKey:
            raise FileNotFoundError(f"S3 object not found: {s3_key}")
        except Exception as e:
            raise Exception(f"Failed to load S3 object {s3_key}: {e}")

        logger.info(f"Loaded from S3: {s3_key}")
        return {
            "content": content,
            "metadata": metadata
        }

import logging
import os
import uuid
from datetime import UTC, datetime

import boto3

from rpsd_storage.provider import StorageProvider

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

        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=s3_key,
            Body=content,
            ContentType=content_type,
            Metadata=metadata,
        )

        logger.info(f"Uploaded to S3: {s3_key}")
        return object_id

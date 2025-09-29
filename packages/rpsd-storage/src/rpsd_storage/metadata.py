"""
Defines the Pydantic model for storage metadata.
"""

from typing import Any

from pydantic import BaseModel, Field


class StorageMetadata(BaseModel):
    """
    Pydantic model for storage metadata.

    Provides runtime validation and a clear schema for the metadata
    associated with stored objects.
    """

    # Required fields for all providers
    provider: str = Field(
        ..., description="The storage provider type (e.g., fs, s3, http)."
    )
    url: str = Field(..., description="Complete URL for loading the content.")
    content_type: str = Field(..., description="The MIME type of the content.")
    content_length: int = Field(..., description="The size of the content in bytes.")
    hash: str = Field(..., description="The MD5 hash of the content.")
    who: str = Field(..., description="Identifier for the entity saving the content.")
    what: str = Field(..., description="Identifier for the content type/category.")
    original_filename: str = Field(
        ..., description="The original filename of the content."
    )
    object_id: str = Field(..., description="Unique identifier for the object.")
    ingestion_timestamp: str = Field(
        ..., description="Timestamp of when the object was ingested."
    )
    schema_version: int = Field(..., description="The version of the metadata schema.")
    source_url: str = Field(..., description="Origin URL of the content.")
    custom_metadata: dict[str, Any] = Field(
        ..., description="Additional metadata (empty dict if none)."
    )

    # Optional provider-specific fields
    etag: str | None = Field(
        default=None, description="ETag of the object, specific to S3."
    )
    status_code: int | None = Field(
        default=None, description="The HTTP status code for HTTP provider."
    )
    headers: dict[str, str] | None = Field(
        default=None, description="The HTTP headers for HTTP provider."
    )
    content_encoding: str | None = Field(
        default=None, description="The content encoding for HTTP provider."
    )

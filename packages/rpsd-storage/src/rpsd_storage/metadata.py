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

    @staticmethod
    def compare(current: "StorageMetadata", candidate: "StorageMetadata") -> int:
        """
        Compare two StorageMetadata instances to determine their relationship.

        This method compares metadata from the same logical entity (same who/what)
        to determine if the candidate represents an update, identical content,
        or older content relative to the current metadata.

        Args:
            current: The currently stored/existing metadata
            candidate: The candidate metadata to compare against current

        Returns:
            int: Comparison result following these semantics:
                -1: candidate is older than current (candidate predates current)
                 0: candidate has identical content to current (same hash/length)
                 1: candidate is newer than current (candidate is an update)

        Raises:
            ValueError: If who or what fields differ (comparing different entities)

        Example:
            >>> result = StorageMetadata.compare(stored_metadata, new_metadata)
            >>> if result == 1:
            ...     print("New metadata is an update")
            >>> elif result == 0:
            ...     print("New metadata is identical")
            >>> else:
            ...     print("New metadata is older")
        """
        # Validate that we're comparing metadata for the same logical entity
        if current.who != candidate.who or current.what != candidate.what:
            raise ValueError(
                f"Cannot compare metadata for different entities. "
                f"Current: who='{current.who}', what='{current.what}' vs "
                f"Candidate: who='{candidate.who}', what='{candidate.what}'"
            )

        # If content is identical (same hash and length), return 0
        if (
            current.content_length == candidate.content_length
            and current.hash == candidate.hash
        ):
            return 0

        # Compare ingestion timestamps
        # If current was ingested after candidate, candidate is older (-1)
        # If current was ingested before candidate, candidate is newer (1)
        if current.ingestion_timestamp > candidate.ingestion_timestamp:
            return -1
        else:
            return 1

    def is_update_of(self, current: "StorageMetadata") -> bool:
        """
        Check if this metadata represents an update of the current metadata.

        This is a convenience method that returns True if this metadata
        is newer than the provided current metadata. It's equivalent to
        checking if compare(current, self) == 1.

        Args:
            current: The currently stored/existing metadata to compare against

        Returns:
            bool: True if this metadata is newer than current, False otherwise

        Raises:
            ValueError: If who or what fields differ (comparing different entities)

        Example:
            >>> if new_metadata.is_update_of(stored_metadata):
            ...     print("This is a newer version, process the update")
            >>> else:
            ...     print("This is not an update (same or older)")
        """
        return StorageMetadata.compare(current, self) == 1

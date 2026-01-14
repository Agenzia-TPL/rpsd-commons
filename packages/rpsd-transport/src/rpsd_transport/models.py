"""
Message and response models for rpsd-transport.

Supports both inline and outline metadata organization:
- Inline: JSON body with {"metadata": {...}, "content": "..."}
- Outline: Metadata in headers/query params, content in body or multipart
"""

import re
import warnings
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

# Regex for valid identifier characters (alphanumeric, dashes, underscores)
IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


class MessageMetadata(BaseModel):
    """
    Transport message metadata.

    Mode is determined by presence/absence of 'where':
    - where is None -> Fast/Slim message
    - where is set -> Heavy/Fat message
    """

    who: str = Field(..., description="Entity identifier")
    what: str = Field(..., description="Content type/category")
    where: str | None = Field(
        default=None, description="URL for heavy messages (None = fast message)"
    )
    content_type: str = Field(
        default="application/octet-stream", description="MIME type of the content"
    )
    filename: str | None = Field(default=None, description="Original filename")

    @property
    def is_slimfast(self) -> bool:
        """Returns True if this is a fast message (no where URL)."""
        return self.where is None

    @property
    def is_fatheavy(self) -> bool:
        """Returns True if this is a heavy message (has where URL)."""
        return self.where is not None

    @field_validator("who", "what")
    @classmethod
    def validate_identifier(cls, v: str) -> str:
        """
        Validate identifier contains only safe characters.

        Allows: alphanumeric, dashes, underscores.
        """
        if not v:
            raise ValueError("Identifier cannot be empty")
        if not IDENTIFIER_PATTERN.match(v):
            raise ValueError(
                "Identifier must contain only alphanumeric characters, "
                "dashes, and underscores"
            )
        return v

    @field_validator("where")
    @classmethod
    def validate_where_url(cls, v: str | None) -> str | None:
        """Validate where URL if provided."""
        if v is None:
            return None
        parsed = urlparse(v)
        # file:// URLs have no netloc but are valid
        if not parsed.scheme:
            raise ValueError("Invalid URL format: must have scheme")
        if parsed.scheme != "file" and not parsed.netloc:
            raise ValueError("Invalid URL format: must have host")
        return v


class TransportMessage(BaseModel):
    """
    Unified transport message model.

    Mode is determined by presence of 'where' in metadata:
    - metadata.where is None -> Fast/Slim message (content in data field)
    - metadata.where is set -> Heavy/Fat message (content at URL)

    This model represents a parsed/normalized message regardless of
    how it was received (inline or outline metadata organization).
    """

    metadata: MessageMetadata
    content: bytes | None = Field(
        default=None,
        description="Content bytes (for fast messages or after fetching heavy content)",
    )

    @property
    def is_slimfast(self) -> bool:
        """Returns True if this is a fast message."""
        return self.metadata.is_slimfast

    @property
    def is_fatheavy(self) -> bool:
        """Returns True if this is a heavy message."""
        return self.metadata.is_fatheavy

    @property
    def who(self) -> str:
        """Convenience accessor for metadata.who."""
        return self.metadata.who

    @property
    def what(self) -> str:
        """Convenience accessor for metadata.what."""
        return self.metadata.what

    @property
    def where(self) -> str | None:
        """Convenience accessor for metadata.where."""
        return self.metadata.where


class InlineMessagePayload(BaseModel):
    """
    Schema for inline metadata JSON payloads.

    Expected format:
    {
        "metadata": {"who": "x", "what": "y", "where": "z"},
        "content": "base64-encoded-content"
    }

    The 'content' field should contain base64-encoded binary data
    for fast messages. For heavy messages, content is fetched from
    the URL specified in metadata.where.
    """

    metadata: MessageMetadata
    content: str | None = Field(
        default=None, description="Base64-encoded content for fast messages"
    )


# =============================================================================
# Legacy models (deprecated, kept for backward compatibility)
# =============================================================================


class BaseMessage(BaseModel):
    """
    Base message with common fields.

    .. deprecated::
        Use TransportMessage instead. Mode is now inferred from 'where' presence.
    """

    who: str = Field(..., description="Entity identifier")
    what: str = Field(..., description="Content type/category")
    mode: Literal["fast", "heavy"]
    content_type: str = Field(
        default="application/octet-stream", description="MIME type of the data"
    )
    filename: str | None = Field(default=None, description="Original filename")

    def __init__(self, **data):
        warnings.warn(
            "BaseMessage is deprecated. Use TransportMessage instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(**data)


class FastMessage(BaseMessage):
    """
    Message with inlined data (fast/slim).

    .. deprecated::
        Use TransportMessage instead.
    """

    mode: Literal["fast"] = "fast"
    data: bytes = Field(..., description="Inlined data content")


class HeavyMessage(BaseMessage):
    """
    Message with external data reference (heavy/fat).

    .. deprecated::
        Use TransportMessage instead.
    """

    mode: Literal["heavy"] = "heavy"
    where: str = Field(..., description="URL to fetch data")


# Aliases for alternative terminology
SlimMessage = FastMessage
FatMessage = HeavyMessage


# =============================================================================
# Response models
# =============================================================================


class SuccessResponse(BaseModel):
    """
    Successful message receipt response (for HTTP endpoints).

    Note: internal_url is set by the application after saving to storage,
    not by the carrier. Carriers only parse and return TransportMessage.
    """

    status: Literal["received"] = "received"
    internal_url: str | None = Field(
        default=None,
        description="Internal storage URL (set by caller after saving)",
    )


class ErrorResponse(BaseModel):
    """Error response for failed message processing."""

    status: Literal["failed"] = "failed"
    error_code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: dict | None = Field(default=None, description="Additional error context")


# =============================================================================
# Error codes
# =============================================================================

ERROR_CODES = {
    # 400 errors - malformed request
    "invalid_json": "Request body is not valid JSON",
    "missing_fields": "Required fields are missing",
    "missing_metadata": "Required metadata (who/what) is missing",
    "duplicate_metadata": "Metadata specified in both header and query parameter",
    "invalid_identifier": "Invalid who/what identifier format",
    "invalid_url": "Invalid URL format in 'where' field",
    "decompression_failed": "Failed to decompress content",
    "invalid_content_encoding": "Invalid or unsupported content encoding",
    "missing_content": "Fast message requires content",
    # Legacy error codes (kept for compatibility)
    "invalid_mode": "Mode must be 'fast' or 'heavy'",
    "missing_where": "Heavy message requires 'where' field",
    "missing_data": "Fast message requires 'data' field",
    # 422 errors - valid format, cannot process
    "content_unreachable": "Cannot fetch content from provided URL",
    "content_fetch_error": "Error occurred while fetching content",
    "invalid_entity": "Invalid who/what identifier",
    # Legacy error codes
    "data_unreachable": "Cannot fetch data from provided URL",
    "data_fetch_error": "Error occurred while fetching data",
    # 500 errors - internal failures
    "storage_error": "Failed to save to internal storage",
    "internal_error": "Unexpected internal error",
}

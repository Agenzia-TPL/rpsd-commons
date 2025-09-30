"""
Message and response models for rpsd-transport.
"""

from typing import Literal

from pydantic import BaseModel, Field


class BaseMessage(BaseModel):
    """Base message with common fields."""

    who: str = Field(..., description="Entity identifier")
    what: str = Field(..., description="Content type/category")
    mode: Literal["fast", "heavy"]
    content_type: str = Field(
        default="application/octet-stream", description="MIME type of the data"
    )
    filename: str | None = Field(default=None, description="Original filename")


class FastMessage(BaseMessage):
    """Message with inlined data (fast/slim)."""

    mode: Literal["fast"] = "fast"
    data: bytes = Field(..., description="Inlined data content")


# Alias for alternative terminology
SlimMessage = FastMessage


class HeavyMessage(BaseMessage):
    """Message with external data reference (heavy/fat)."""

    mode: Literal["heavy"] = "heavy"
    where: str = Field(..., description="URL to fetch data")


# Alias for alternative terminology
FatMessage = HeavyMessage


class SuccessResponse(BaseModel):
    """Successful message receipt response."""

    status: Literal["received"] = "received"
    internal_url: str | None = Field(
        default=None, description="Internal storage URL (for heavy messages)"
    )


class ErrorResponse(BaseModel):
    """Error response for failed message processing."""

    status: Literal["failed"] = "failed"
    error_code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: dict | None = Field(
        default=None, description="Additional error context"
    )


# Standard error codes
ERROR_CODES = {
    # 400 errors - malformed request
    "invalid_json": "Request body is not valid JSON",
    "missing_fields": "Required fields are missing",
    "invalid_mode": "Mode must be 'fast' or 'heavy'",
    # 422 errors - valid format, cannot process
    "data_unreachable": "Cannot fetch data from provided URL",
    "data_fetch_error": "Error occurred while fetching data",
    "invalid_entity": "Invalid who/what identifier",
    "missing_where": "Heavy message requires 'where' field",
    "missing_data": "Fast message requires 'data' field",
    # 500 errors - internal failures
    "storage_error": "Failed to save to internal storage",
    "internal_error": "Unexpected internal error",
}

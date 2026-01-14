"""HTTP utilities for metadata detection and extraction."""

import json
import logging
import re
from enum import Enum

from fastapi import Request

from rpsd_transport.exceptions import (
    DuplicateMetadataError,
    InvalidMetadataError,
    MissingMetadataError,
)
from rpsd_transport.models import MessageMetadata

logger = logging.getLogger(__name__)


class MetadataOrganization(Enum):
    """How metadata is organized in the request."""

    INLINE = "inline"  # Metadata in JSON body
    OUTLINE = "outline"  # Metadata in headers/query params


# Header name mappings: field -> [current_header, legacy_header]
HEADER_MAPPINGS: dict[str, list[str]] = {
    "who": ["X-RPSD-WHO", "X-RAPS-INGEST_WHO"],
    "what": ["X-RPSD-WHAT", "X-RAPS-INGEST_WHAT"],
    "where": ["X-RPSD-WHERE", "X-RAPS-INGEST_WHERE"],
}

# Query parameter names (same as field names)
QUERY_PARAM_NAMES = ["who", "what", "where"]

# Regex for valid identifier characters
IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


def detect_metadata_organization(
    content_type: str, body: bytes
) -> MetadataOrganization:
    """
    Detect whether the request uses inline or outline metadata organization.

    Rules:
    1. If Content-Type contains application/json and body parses as JSON with
       'metadata' key containing 'who' and 'what' -> INLINE
    2. Otherwise -> OUTLINE

    Args:
        content_type: Content-Type header value
        body: Raw request body bytes

    Returns:
        MetadataOrganization.INLINE or MetadataOrganization.OUTLINE
    """
    if "application/json" in content_type:
        try:
            parsed = json.loads(body)
            if isinstance(parsed, dict) and "metadata" in parsed:
                metadata = parsed.get("metadata", {})
                if isinstance(metadata, dict):
                    if "who" in metadata and "what" in metadata:
                        return MetadataOrganization.INLINE
        except (json.JSONDecodeError, TypeError, UnicodeDecodeError):
            pass

    return MetadataOrganization.OUTLINE


def extract_outline_metadata(
    headers: dict[str, str],
    query_params: dict[str, str],
    content_type: str | None = None,
) -> MessageMetadata:
    """
    Extract metadata from headers and query parameters.

    Rules:
    - Each metadata value can come from header OR query param, not both
    - Current headers take precedence over legacy headers
    - Raises DuplicateMetadataError if same value in both header AND query param
    - Raises MissingMetadataError if required fields (who, what) are missing

    Args:
        headers: Request headers (case-insensitive lookup)
        query_params: Query parameters
        content_type: Optional content type for the metadata

    Returns:
        MessageMetadata instance

    Raises:
        DuplicateMetadataError: If metadata in both header and query param
        MissingMetadataError: If required metadata is missing
        InvalidMetadataError: If metadata values are invalid
    """
    # Normalize headers to lowercase for case-insensitive lookup
    lower_headers = {k.lower(): v for k, v in headers.items()}

    result: dict[str, str | None] = {}

    for field in ["who", "what", "where"]:
        header_value = None
        query_value = query_params.get(field)

        # Check headers (current first, then legacy)
        for header_name in HEADER_MAPPINGS[field]:
            val = lower_headers.get(header_name.lower())
            if val:
                header_value = val
                break

        # Validate not in both header AND query param
        if header_value and query_value:
            raise DuplicateMetadataError(
                f"Cannot specify '{field}' in both query parameter and header"
            )

        value = header_value or query_value
        result[field] = value

        # Validate identifier format for who and what
        if field in ["who", "what"] and value:
            if not IDENTIFIER_PATTERN.match(value):
                raise InvalidMetadataError(
                    f"Invalid '{field}' value: must contain only alphanumeric "
                    "characters, dashes, and underscores"
                )

    # Validate required fields
    who_value = result.get("who")
    what_value = result.get("what")

    if not who_value:
        raise MissingMetadataError("Must provide 'who' in query parameter or header")
    if not what_value:
        raise MissingMetadataError("Must provide 'what' in query parameter or header")

    return MessageMetadata(
        who=who_value,
        what=what_value,
        where=result.get("where"),
        content_type=content_type or "application/octet-stream",
    )


def extract_outline_content(
    body: bytes,
    content_type: str,
    is_base64_encoded: bool = False,
) -> tuple[bytes, str | None]:
    """
    Extract content from outline mode request.

    Supports:
    1. Multipart/form-data with file attachment
    2. Raw body content

    Args:
        body: Raw request body bytes
        content_type: Content-Type header value
        is_base64_encoded: Flag from API Gateway (check first)

    Returns:
        Tuple of (content_bytes, filename or None)
    """
    import base64

    # Handle multipart/form-data
    if content_type.startswith("multipart/form-data"):
        return parse_multipart_content(body, content_type)

    # Handle base64 encoding (API Gateway pattern)
    if is_base64_encoded:
        return base64.b64decode(body), None

    # Return raw body as-is
    return body, None


def parse_multipart_content(body: bytes, content_type: str) -> tuple[bytes, str | None]:
    """
    Parse multipart/form-data body and extract file content.

    Args:
        body: Raw multipart body bytes
        content_type: Content-Type header with boundary

    Returns:
        Tuple of (file_content, filename or None)

    Raises:
        ValueError: If parsing fails or no file found
    """
    # Extract boundary from content-type
    boundary = None
    for part in content_type.split(";"):
        part = part.strip()
        if part.startswith("boundary="):
            boundary = part[9:].strip('"')
            break

    if not boundary:
        raise ValueError("No boundary found in multipart content-type")

    try:
        parts = body.split(b"--" + boundary.encode())
        for part in parts:
            if b"Content-Disposition" in part:
                # Split headers from content
                if b"\r\n\r\n" in part:
                    headers_section, content = part.split(b"\r\n\r\n", 1)
                elif b"\n\n" in part:
                    headers_section, content = part.split(b"\n\n", 1)
                else:
                    continue

                headers_str = headers_section.decode("utf-8", errors="replace")

                # Extract filename
                filename = None
                if 'filename="' in headers_str:
                    filename = headers_str.split('filename="')[1].split('"')[0]
                elif "filename=" in headers_str:
                    filename = headers_str.split("filename=")[1].split(";")[0]
                    filename = filename.split("\r")[0].split("\n")[0].strip()

                # Only process parts with filename (actual file uploads)
                if filename:
                    # Remove trailing boundary markers
                    content = content.rstrip(b"\r\n--")
                    content = content.rstrip(b"--")
                    content = content.rstrip(b"\r\n")
                    return content, filename

        raise ValueError("No file found in multipart data")

    except Exception as e:
        logger.error(f"Error parsing multipart data: {e}")
        raise ValueError(f"Failed to parse multipart data: {e}") from e


def get_header_value(
    request: Request, current_name: str, legacy_name: str | None = None
) -> str | None:
    """
    Get header value with fallback to legacy header name.

    Args:
        request: FastAPI request
        current_name: Current header name
        legacy_name: Optional legacy header name

    Returns:
        Header value or None
    """
    value = request.headers.get(current_name)
    if value is None and legacy_name:
        value = request.headers.get(legacy_name)
    return value


def build_outline_headers(
    who: str,
    what: str,
    where: str | None = None,
) -> dict[str, str]:
    """
    Build HTTP headers for outline metadata.

    Uses current header naming convention (X-RPSD-*).

    Args:
        who: Entity identifier
        what: Content type/category
        where: Optional URL for heavy messages

    Returns:
        Dict of header name to value
    """
    headers = {
        "X-RPSD-WHO": who,
        "X-RPSD-WHAT": what,
    }
    if where:
        headers["X-RPSD-WHERE"] = where
    return headers


def build_outline_query_params(
    who: str,
    what: str,
    where: str | None = None,
) -> dict[str, str]:
    """
    Build query parameters for outline metadata.

    Args:
        who: Entity identifier
        what: Content type/category
        where: Optional URL for heavy messages

    Returns:
        Dict of param name to value
    """
    params = {
        "who": who,
        "what": what,
    }
    if where:
        params["where"] = where
    return params

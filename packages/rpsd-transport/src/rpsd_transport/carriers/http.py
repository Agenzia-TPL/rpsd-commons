"""
HTTP carrier implementation for rpsd-transport.

Supports both inline and outline metadata organization:
- Inline: JSON body with {"metadata": {...}, "content": "..."}
- Outline: Metadata in headers/query params, content in body or multipart
"""

import base64
import json
import logging

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from rpsd_transport.carriers.base import BaseCarrier
from rpsd_transport.carriers.http_utils import (
    MetadataOrganization,
    detect_metadata_organization,
    extract_outline_content,
    extract_outline_metadata,
)
from rpsd_transport.compression import decompress_content
from rpsd_transport.exceptions import (
    CompressionError,
    DuplicateMetadataError,
    InvalidJsonError,
    InvalidMetadataError,
    MissingMetadataError,
)
from rpsd_transport.models import (
    ERROR_CODES,
    ErrorResponse,
    InlineMessagePayload,
    MessageMetadata,
    TransportMessage,
)

logger = logging.getLogger(__name__)


class HTTPCarrier(BaseCarrier):
    """
    HTTP-based carrier for external system communication.

    Implements transport via HTTP POST for sending and receiving messages.
    Supports both inline and outline metadata organization.

    Inline metadata: JSON body with {"metadata": {...}, "content": "..."}
    Outline metadata: Metadata in headers/query params, content in body/multipart
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 30.0,
    ):
        """
        Initialize HTTP carrier.

        Args:
            base_url: Base URL for generating temporary endpoints
            timeout: HTTP request timeout in seconds
        """
        self.base_url = base_url
        self.timeout = timeout
        self._http_client = httpx.Client(timeout=timeout)

    def send_slimfast(
        self,
        recipient: str,
        data: bytes,
        who: str,
        what: str,
        content_type: str = "application/octet-stream",
        filename: str | None = None,
    ) -> dict:
        """
        Send data inline via HTTP POST (fast/slim mode) with inline metadata.

        Args:
            recipient: Target URL for HTTP POST
            data: Data to send (inlined in message)
            who: Entity identifier
            what: Content type/category
            content_type: MIME type of the data
            filename: Optional original filename

        Returns:
            dict: Response from recipient

        Raises:
            httpx.HTTPError: If HTTP request fails
        """
        # Build inline message payload
        payload = {
            "metadata": {
                "who": who,
                "what": what,
                "content_type": content_type,
            },
            "content": base64.b64encode(data).decode("utf-8"),
        }

        if filename:
            payload["metadata"]["filename"] = filename

        try:
            response = self._http_client.post(
                recipient,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to send fast message to {recipient}: {e}")
            raise

    def send_fatheavy(
        self,
        recipient: str,
        who: str,
        what: str,
        data: bytes | None = None,
        storage_url: str | None = None,
        expose_ttl: int = 3600,
        content_type: str = "application/octet-stream",
        filename: str | None = None,
    ) -> dict:
        """
        Send data by reference via HTTP POST (heavy/fat mode).

        NOTE: Heavy mode not yet implemented (Phase 2).

        Args:
            recipient: Target URL for HTTP POST
            who: Entity identifier
            what: Content type/category
            data: New data to save and expose
            storage_url: Existing storage URL to expose
            expose_ttl: Time-to-live for exposed URL in seconds
            content_type: MIME type of the data
            filename: Optional original filename

        Returns:
            dict: Response from recipient

        Raises:
            NotImplementedError: Heavy mode not yet implemented
        """
        raise NotImplementedError(
            "Heavy mode not yet implemented. This will be added in Phase 2."
        )

    async def handle_receive(self, request: Request) -> JSONResponse:
        """
        Handle incoming HTTP message (inline or outline metadata).

        Detects the metadata organization from the request and processes
        accordingly:
        - Inline: JSON body with {"metadata": {...}, "content": "..."}
        - Outline: Metadata in headers/query params, content in body/multipart

        Args:
            request: FastAPI Request object

        Returns:
            JSONResponse: Success or error response
        """
        try:
            body = await request.body()
            content_type = request.headers.get("content-type", "")

            # Detect metadata organization
            organization = detect_metadata_organization(content_type, body)

            if organization == MetadataOrganization.INLINE:
                message = await self._handle_inline_message(body)
            else:
                message = await self._handle_outline_message(request, body)

            # Process the message
            return await self._process_message(message)

        except InvalidJsonError as e:
            return self._error_response(400, "invalid_json", str(e))
        except DuplicateMetadataError as e:
            return self._error_response(400, "duplicate_metadata", str(e))
        except MissingMetadataError as e:
            return self._error_response(400, "missing_metadata", str(e))
        except InvalidMetadataError as e:
            return self._error_response(400, "invalid_identifier", str(e))
        except CompressionError as e:
            return self._error_response(400, "decompression_failed", str(e))
        except ValidationError as e:
            # Pydantic validation errors
            return self._error_response(
                400, "missing_fields", f"Validation error: {e.error_count()} errors"
            )
        except ValueError as e:
            return self._error_response(400, "missing_fields", str(e))
        except Exception as e:
            logger.error(f"Unexpected error handling request: {e}", exc_info=True)
            return self._error_response(
                500, "internal_error", ERROR_CODES["internal_error"]
            )

    async def _handle_inline_message(self, body: bytes) -> TransportMessage:
        """
        Parse inline metadata message from JSON body.

        Expected format:
        {
            "metadata": {"who": "x", "what": "y", "where": "z"},
            "content": "base64-encoded-content"
        }

        Args:
            body: Raw JSON body bytes

        Returns:
            TransportMessage instance

        Raises:
            InvalidJsonError: If body is not valid JSON
            ValidationError: If payload doesn't match schema
        """
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as e:
            raise InvalidJsonError(f"Request body is not valid JSON: {e}") from e

        # Validate with Pydantic model
        payload = InlineMessagePayload.model_validate(parsed)

        # Decode content for fast messages
        content = None
        if payload.metadata.is_slimfast and payload.content:
            try:
                content = base64.b64decode(payload.content)
            except Exception as e:
                raise InvalidJsonError(f"Failed to decode base64 content: {e}") from e

            # Decompress if needed
            content = decompress_content(content, payload.metadata.filename)
        elif payload.metadata.is_slimfast and not payload.content:
            raise ValueError("Fast message requires content")

        return TransportMessage(
            metadata=payload.metadata,
            content=content,
        )

    async def _handle_outline_message(
        self,
        request: Request,
        body: bytes,
    ) -> TransportMessage:
        """
        Parse outline metadata message from headers/query params.

        Content can be:
        - Multipart attachment (with filename)
        - Raw body

        Args:
            request: FastAPI request
            body: Raw body bytes

        Returns:
            TransportMessage instance

        Raises:
            DuplicateMetadataError: If metadata in both header and query
            MissingMetadataError: If required metadata missing
        """
        headers = dict(request.headers)
        query_params = dict(request.query_params)
        content_type = headers.get("content-type", "application/octet-stream")

        # Extract metadata from headers/query params
        metadata = extract_outline_metadata(headers, query_params, content_type)

        # For heavy messages, we don't need content in body
        if metadata.is_fatheavy:
            return TransportMessage(metadata=metadata, content=None)

        # Extract content from body or multipart
        is_base64 = query_params.get("isBase64Encoded", "").lower() == "true"
        content, filename = extract_outline_content(body, content_type, is_base64)

        # Update metadata with filename if extracted from multipart
        if filename and not metadata.filename:
            metadata = MessageMetadata(
                who=metadata.who,
                what=metadata.what,
                where=metadata.where,
                content_type=metadata.content_type,
                filename=filename,
            )

        # Decompress if needed
        content = decompress_content(content, metadata.filename)

        return TransportMessage(metadata=metadata, content=content)

    async def _process_message(self, message: TransportMessage) -> JSONResponse:
        """
        Process a received message.

        For Phase 1, just logs and returns success.
        Phase 2 will add:
        - Storage integration (save to rpsd-storage)
        - Heavy message URL fetching
        - Return internal_url in response

        Args:
            message: Parsed TransportMessage

        Returns:
            JSONResponse: Success response
        """
        if message.is_fatheavy:
            # Heavy mode: content needs to be fetched from where URL
            # Phase 2 will implement this
            logger.info(
                f"Received heavy message: who={message.who}, "
                f"what={message.what}, where={message.where}"
            )
            return JSONResponse(
                status_code=501,
                content=ErrorResponse(
                    status="failed",
                    error_code="not_implemented",
                    message="Heavy mode storage not yet implemented (Phase 2)",
                ).model_dump(),
            )

        # Fast mode: content is already available
        content_size = len(message.content) if message.content else 0
        logger.info(
            f"Received fast message: who={message.who}, "
            f"what={message.what}, size={content_size} bytes"
        )

        # Phase 2 will save to storage and return internal_url
        return JSONResponse(
            status_code=200,
            content={"status": "received"},
        )

    def _error_response(
        self,
        status_code: int,
        error_code: str,
        message: str,
        details: dict | None = None,
    ) -> JSONResponse:
        """
        Create a standardized error response.

        Args:
            status_code: HTTP status code
            error_code: Machine-readable error code
            message: Human-readable error message
            details: Optional additional error context

        Returns:
            JSONResponse with error details
        """
        return JSONResponse(
            status_code=status_code,
            content=ErrorResponse(
                status="failed",
                error_code=error_code,
                message=message,
                details=details,
            ).model_dump(),
        )

    def __del__(self):
        """Cleanup HTTP client on deletion."""
        if hasattr(self, "_http_client"):
            self._http_client.close()

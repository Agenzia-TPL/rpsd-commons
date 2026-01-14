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
    build_outline_headers,
    build_outline_query_params,
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
        who: str,
        what: str,
        content: bytes,
        content_type: str = "application/octet-stream",
        filename: str | None = None,
        metadata_use_inline: bool = True,
        metadata_use_headers: bool = True,
        content_use_body: bool = True,
    ) -> dict:
        """
        Send data inline via HTTP POST (fast/slim mode).

        Args:
            recipient: Target URL for HTTP POST
            who: Entity identifier
            what: Content type/category
            content: Data to send
            content_type: MIME type of the data
            filename: Optional original filename
            metadata_use_inline: True=inline JSON, False=outline headers/query
            metadata_use_headers: True=headers, False=query params
                (when metadata_use_inline=False)
            content_use_body: True=raw body, False=multipart
                (when metadata_use_inline=False)

        Returns:
            dict: Response from recipient

        Raises:
            httpx.HTTPError: If HTTP request fails
        """
        try:
            if metadata_use_inline:
                # INLINE MODE: JSON body with metadata and base64 content
                payload = {
                    "metadata": {
                        "who": who,
                        "what": what,
                        "content_type": content_type,
                    },
                    "content": base64.b64encode(content).decode("utf-8"),
                }
                if filename:
                    payload["metadata"]["filename"] = filename

                response = self._http_client.post(
                    recipient,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )

            else:  # OUTLINE MODE
                if metadata_use_headers:
                    headers = build_outline_headers(who, what)
                    params = None
                else:
                    headers = {}
                    params = build_outline_query_params(who, what)

                if content_use_body:
                    # Send as raw body
                    headers["Content-Type"] = content_type
                    response = self._http_client.post(
                        recipient,
                        content=content,
                        headers=headers,
                        params=params,
                    )
                else:
                    # Send as multipart/form-data attachment
                    files = {"file": (filename or "data.bin", content, content_type)}
                    response = self._http_client.post(
                        recipient,
                        files=files,
                        headers=headers,
                        params=params,
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
        content: bytes | None,
        content_type: str = "application/octet-stream",
        filename: str | None = None,
        metadata_use_inline: bool = True,
        metadata_use_headers: bool = True,
        where: str | None = None,
        expose_ttl: int = 3600,
    ) -> dict:
        """
        Send data by reference via HTTP POST (heavy/fat mode).

        Args:
            recipient: Target URL for HTTP POST
            who: Entity identifier
            what: Content type/category
            content: New data to save (Phase 2) or None if using existing 'where'
            content_type: MIME type of the data
            filename: Optional original filename
            metadata_use_inline: True=inline JSON, False=outline headers/query
            metadata_use_headers: True=headers, False=query params
                (when metadata_use_inline=False)
            where: URL where content is available (required for now)
            expose_ttl: Time-to-live for exposed URL in seconds

        Returns:
            dict: Response from recipient

        Raises:
            ValueError: If neither content nor where provided
            NotImplementedError: If content provided (storage integration Phase 2)
            httpx.HTTPError: If HTTP request fails
        """
        # Validate parameters
        if content is None and where is None:
            raise ValueError("Must provide either 'content' or 'where'")

        if content is not None and where is None:
            raise NotImplementedError(
                "Saving content and generating 'where' URL not yet implemented "
                "(Phase 2). Please provide 'where' directly."
            )

        # Use provided 'where' as the URL
        where_url = where

        try:
            if metadata_use_inline:
                # INLINE MODE: JSON body with metadata including where URL
                payload = {
                    "metadata": {
                        "who": who,
                        "what": what,
                        "where": where_url,
                        "content_type": content_type,
                    },
                    "content": None,  # No content in heavy messages
                }
                if filename:
                    payload["metadata"]["filename"] = filename

                response = self._http_client.post(
                    recipient,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )

            else:  # OUTLINE MODE
                if metadata_use_headers:
                    headers = build_outline_headers(who, what, where_url)
                    params = None
                else:
                    headers = {}
                    params = build_outline_query_params(who, what, where_url)

                # Empty body for heavy messages with outline metadata
                headers["Content-Type"] = "application/octet-stream"
                response = self._http_client.post(
                    recipient,
                    content=b"",
                    headers=headers,
                    params=params,
                )

            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to send heavy message to {recipient}: {e}")
            raise

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

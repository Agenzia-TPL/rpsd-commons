"""
HTTP carrier implementation for rpsd-transport.

Supports both inline and outline metadata organization:
- Inline: JSON body with {"metadata": {...}, "content": "..."}
- Outline: Metadata in headers/query params, content in body or multipart
"""

import base64
import json
import logging
from typing import Any

import httpx
from fastapi import Request

from rpsd_transport.carriers.base import BaseCarrier, CarrierOptions
from rpsd_transport.carriers.utils import (
    MetadataOrganization,
    build_outline_headers,
    build_outline_query_params,
    detect_metadata_organization,
    extract_outline_content,
    extract_outline_metadata,
)
from rpsd_transport.compression import decompress_content
from rpsd_transport.exceptions import InvalidJsonError
from rpsd_transport.models import (
    InlineMessagePayload,
    MessageMetadata,
    TransportMessage,
)

logger = logging.getLogger(__name__)


class HTTPCarrierOptions(CarrierOptions):
    """HTTP-specific send options.

    Attributes:
        metadata_use_inline: If True, metadata is embedded in
            JSON body. If False, uses headers or query params.
        metadata_use_headers: When outline mode, if True metadata
            goes in HTTP headers, if False in query params.
        content_use_body: When outline mode, if True content is
            sent as raw body, if False as multipart form-data.
    """

    metadata_use_headers: bool = True
    content_use_body: bool = True


class HTTPCarrier(BaseCarrier):
    """HTTP-based carrier for external system communication.

    Implements transport via HTTP POST for sending and receiving
    messages. Supports both inline and outline metadata organization.

    Inline metadata: JSON body with {"metadata": {...}, "content": "..."}
    Outline metadata: Metadata in headers/query params, content in
    body/multipart
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: int = 30,
    ):
        """Initialize HTTP carrier.

        Args:
            base_url: Base URL for generating temporary endpoints
                (future use)
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
        custom_metadata: dict[str, Any] | None = None,
        options: HTTPCarrierOptions | None = None,
    ) -> dict:
        """Send data inline via HTTP POST (fast/slim mode).

        Args:
            recipient: Target URL for HTTP POST
            who: Entity identifier
            what: Content type/category
            content: Data to send
            content_type: MIME type of the data
            filename: Optional original filename
            custom_metadata: Optional additional metadata
            options: HTTP-specific send options. Defaults to
                HTTPCarrierOptions() (inline metadata).

        Returns:
            dict: Response from recipient

        Raises:
            httpx.HTTPError: If HTTP request fails
        """
        if options is None:
            options = HTTPCarrierOptions()

        try:
            if options.metadata_use_inline:
                # INLINE MODE: JSON body with metadata and base64
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
                if custom_metadata:
                    payload["metadata"]["custom_metadata"] = custom_metadata

                response = self._http_client.post(
                    recipient,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )

            else:  # OUTLINE MODE
                if options.metadata_use_headers:
                    headers = build_outline_headers(who, what)
                    params = None
                else:
                    headers = {}
                    params = build_outline_query_params(who, what)

                if options.content_use_body:
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
                    files = {
                        "file": (
                            filename or "data.bin",
                            content,
                            content_type,
                        )
                    }
                    response = self._http_client.post(
                        recipient,
                        files=files,
                        headers=headers,
                        params=params,
                    )

            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(
                "Failed to send fast message to %s: %s",
                recipient,
                e,
            )
            raise

    def send_fatheavy(
        self,
        recipient: str,
        who: str,
        what: str,
        content: bytes | None,
        content_type: str = "application/octet-stream",
        filename: str | None = None,
        custom_metadata: dict[str, Any] | None = None,
        options: HTTPCarrierOptions | None = None,
        where: str | None = None,
        expose_ttl: int = 3600,
    ) -> dict:
        """Send data by reference via HTTP POST (heavy/fat mode).

        Args:
            recipient: Target URL for HTTP POST
            who: Entity identifier
            what: Content type/category
            content: New data to save or None if using existing
                'where'
            content_type: MIME type of the data
            filename: Optional original filename
            custom_metadata: Optional additional metadata
            options: HTTP-specific send options. Defaults to
                HTTPCarrierOptions() (inline metadata).
            where: URL where content is available (required
                for now)
            expose_ttl: Time-to-live for exposed URL in seconds

        Returns:
            dict: Response from recipient

        Raises:
            ValueError: If neither content nor where provided
            NotImplementedError: If content provided (Phase 2)
            httpx.HTTPError: If HTTP request fails
        """
        if options is None:
            options = HTTPCarrierOptions()

        # Validate parameters
        if content is None and where is None:
            raise ValueError("Must provide either 'content' or 'where'")

        if content is not None and where is None:
            raise NotImplementedError(
                "Saving content and generating 'where' URL not yet "
                "implemented (Phase 2). Please provide 'where' "
                "directly."
            )

        # Use provided 'where' as the URL
        where_url = where

        try:
            if options.metadata_use_inline:
                # INLINE MODE: JSON body with metadata including
                # where URL
                payload = {
                    "metadata": {
                        "who": who,
                        "what": what,
                        "where": where_url,
                        "content_type": content_type,
                    },
                    "content": None,
                }
                if filename:
                    payload["metadata"]["filename"] = filename
                if custom_metadata:
                    payload["metadata"]["custom_metadata"] = custom_metadata

                response = self._http_client.post(
                    recipient,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )

            else:  # OUTLINE MODE
                if options.metadata_use_headers:
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
            logger.error(
                "Failed to send heavy message to %s: %s",
                recipient,
                e,
            )
            raise

    async def receive(self, request: Request) -> TransportMessage:
        """Receive and parse incoming HTTP message.

        Detects metadata organization (inline vs outline), extracts
        into TransportMessage, logs, and calls received() hook.
        Does not fetch heavy content or save to storage.

        Args:
            request: FastAPI Request object

        Returns:
            TransportMessage: Parsed message with metadata and
                content (if fast)

        Raises:
            InvalidJsonError: If inline JSON is malformed
            DuplicateMetadataError: If metadata in both header
                and query
            MissingMetadataError: If required metadata missing
            InvalidMetadataError: If who/what identifiers invalid
            CompressionError: If decompression fails
            ValidationError: If Pydantic validation fails
        """
        body = await request.body()
        content_type = request.headers.get("content-type", "")

        # Detect metadata organization
        organization = detect_metadata_organization(content_type, body)

        if organization == MetadataOrganization.INLINE:
            message = await self._handle_inline_message(body)
        else:
            message = await self._handle_outline_message(request, body)

        # Log received message
        if message.is_fatheavy:
            logger.info(
                "Received heavy message: who=%s, what=%s, where=%s",
                message.who,
                message.what,
                message.where,
            )
        else:
            content_size = len(message.content) if message.content else 0
            logger.info(
                "Received fast message: who=%s, what=%s, size=%d bytes",
                message.who,
                message.what,
                content_size,
            )

        # Call hook for extensibility
        self.received(message)

        return message

    def received(self, message: TransportMessage) -> None:
        """Hook called after receiving and parsing a message.

        Override this method in subclasses to add custom behavior
        like:
        - Storage integration (fetch heavy content, save to
          storage)
        - Metrics collection (count messages by who/what)
        - Validation (check against expected who/what values)
        - Notifications (alert on specific message types)
        - Auditing (record receipt in database)

        This method should have side effects only and not return
        values. It should not modify the message object itself.
        It CAN raise exceptions for error conditions like:
        - Storage failures (cannot save to storage)
        - Validation failures (unauthorized entity)
        - Heavy content unreachable (cannot fetch from where URL)

        Args:
            message: Successfully parsed TransportMessage

        Raises:
            Any exception to reject the message
        """
        pass  # Default: no-op, subclasses can override

    async def _handle_inline_message(self, body: bytes) -> TransportMessage:
        """Parse inline metadata message from JSON body.

        Expected format:
        {
            "metadata": {"who": "x", "what": "y", "where": "z"},
            "content": "base64-encoded-content"
        }
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
        """Parse outline metadata message from headers/query params.

        Content can be:
        - Multipart attachment (with filename)
        - Raw body
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
        content, filename = extract_outline_content(body, content_type)

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

    def __del__(self):
        """Cleanup HTTP client on deletion."""
        if hasattr(self, "_http_client"):
            self._http_client.close()

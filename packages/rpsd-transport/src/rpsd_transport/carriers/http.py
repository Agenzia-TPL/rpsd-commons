"""
HTTP carrier implementation for rpsd-transport.
"""

import json
import logging

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse

from rpsd_transport.carriers.base import BaseCarrier
from rpsd_transport.models import ERROR_CODES, ErrorResponse, FastMessage

logger = logging.getLogger(__name__)


class HTTPCarrier(BaseCarrier):
    """
    HTTP-based carrier for external system communication.

    Implements transport via HTTP POST for sending and receiving messages.
    Currently supports fast mode only (Phase 1 implementation).
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

    def send_fast(
        self,
        recipient: str,
        data: bytes,
        who: str,
        what: str,
        content_type: str = "application/octet-stream",
        filename: str | None = None,
    ) -> dict:
        """
        Send data inline via HTTP POST (fast/slim mode).

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
        message = FastMessage(
            mode="fast",
            who=who,
            what=what,
            data=data,
            content_type=content_type,
            filename=filename,
        )

        # Convert to dict for JSON serialization
        # Note: bytes need special handling in JSON
        message_dict = message.model_dump()
        # Convert bytes to base64 for JSON transport
        import base64

        message_dict["data"] = base64.b64encode(data).decode("utf-8")

        try:
            response = self._http_client.post(
                recipient,
                json=message_dict,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to send fast message to {recipient}: {e}")
            raise

    def send_heavy(
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
        Handle incoming HTTP message (fast or heavy mode).

        Currently only supports fast mode (Phase 1).

        Args:
            request: FastAPI Request object

        Returns:
            JSONResponse: Success or error response
        """
        try:
            # Parse JSON body
            try:
                body = await request.json()
            except json.JSONDecodeError:
                return JSONResponse(
                    status_code=400,
                    content=ErrorResponse(
                        status="failed",
                        error_code="invalid_json",
                        message=ERROR_CODES["invalid_json"],
                    ).model_dump(),
                )

            # Validate required fields
            if not all(k in body for k in ["mode", "who", "what"]):
                return JSONResponse(
                    status_code=400,
                    content=ErrorResponse(
                        status="failed",
                        error_code="missing_fields",
                        message=ERROR_CODES["missing_fields"],
                    ).model_dump(),
                )

            mode = body.get("mode")

            # Check for unsupported heavy mode
            if mode == "heavy":
                return JSONResponse(
                    status_code=501,  # Not Implemented
                    content=ErrorResponse(
                        status="failed",
                        error_code="not_implemented",
                        message="Heavy mode not yet implemented (Phase 2)",
                    ).model_dump(),
                )

            # Handle fast mode
            if mode == "fast":
                return await self._handle_fast_message(body)

            # Invalid mode
            return JSONResponse(
                status_code=400,
                content=ErrorResponse(
                    status="failed",
                    error_code="invalid_mode",
                    message=ERROR_CODES["invalid_mode"],
                ).model_dump(),
            )

        except Exception as e:
            logger.error(f"Unexpected error handling request: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content=ErrorResponse(
                    status="failed",
                    error_code="internal_error",
                    message=ERROR_CODES["internal_error"],
                ).model_dump(),
            )

    async def _handle_fast_message(self, body: dict) -> JSONResponse:
        """
        Handle fast mode message.

        Args:
            body: Parsed message body

        Returns:
            JSONResponse: Success or error response
        """
        # Validate fast message has data field
        if "data" not in body:
            return JSONResponse(
                status_code=400,
                content=ErrorResponse(
                    status="failed",
                    error_code="missing_data",
                    message=ERROR_CODES["missing_data"],
                ).model_dump(),
            )

        # Decode base64 data
        import base64

        try:
            data = base64.b64decode(body["data"])
        except Exception as e:
            return JSONResponse(
                status_code=400,
                content=ErrorResponse(
                    status="failed",
                    error_code="invalid_data",
                    message=f"Failed to decode data: {str(e)}",
                ).model_dump(),
            )

        # For Phase 1, we just validate and return success
        # Phase 2 will add storage integration
        logger.info(
            f"Received fast message: who={body['who']}, "
            f"what={body['what']}, size={len(data)} bytes"
        )

        return JSONResponse(
            status_code=200,
            content={"status": "received"},
        )

    def __del__(self):
        """Cleanup HTTP client on deletion."""
        if hasattr(self, "_http_client"):
            self._http_client.close()

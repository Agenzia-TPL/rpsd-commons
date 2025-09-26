import logging
from typing import Any
from urllib.parse import urlparse

import httpx

from rpsd_storage.provider import StorageProvider

logger = logging.getLogger(__name__)


class HTTPStorageProvider(StorageProvider):
    """
    HTTP storage provider for retrieving data via HTTP/HTTPS.

    This provider supports:
    - load(): HTTP GET requests to retrieve data from URLs
    - save(): Not implemented (raises NotImplementedError)
    """

    def __init__(self, timeout: float = 30.0):
        """
        Initialize HTTP storage provider.

        Args:
            timeout: Request timeout in seconds (default: 30.0)
        """
        self.timeout = timeout

    def _build_url(self, who: str, what: str, object_id: str) -> str:
        """
        For HTTP provider, this method is not used in the typical way.
        HTTP URLs are complete and don't need to be constructed from parts.

        Args:
            who: Not used for HTTP URLs
            what: Not used for HTTP URLs
            object_id: Not used for HTTP URLs

        Returns:
            str: Placeholder - HTTP URLs should be provided directly to load()
        """
        # Parameters are intentionally unused for HTTP provider
        _ = who, what, object_id
        raise NotImplementedError(
            "HTTP provider requires complete URLs. "
            "Use load(url) directly with full HTTP/HTTPS URLs."
        )

    def save(
        self,
        content,
        filename,
        content_type="application/xml",
        source_url=None,
        who=None,
        what=None,
        custom_metadata=None,
    ) -> tuple[str, dict[str, Any]]:
        """
        Save method is not implemented for HTTP provider.

        Raises:
            NotImplementedError: HTTP POST saving is not yet implemented
        """
        # Parameters are intentionally unused for HTTP provider
        _ = content, filename, content_type, source_url, who, what, custom_metadata
        raise NotImplementedError(
            "HTTP provider save() method is not yet implemented. "
            "Only load() operations are currently supported."
        )

    def _validate_url_scheme(self, url: str) -> None:
        """
        Validate that URL has HTTP or HTTPS scheme.

        Args:
            url: URL to validate

        Raises:
            ValueError: If URL scheme is not http or https
        """
        parsed = urlparse(url)
        if parsed.scheme.lower() not in ("http", "https"):
            raise ValueError(f"Unsupported URL scheme: {parsed.scheme}")

    def _handle_http_response(self, response: httpx.Response, url: str) -> None:
        """
        Handle HTTP response status and raise appropriate errors.

        Args:
            response: HTTP response object
            url: URL being accessed

        Raises:
            FileNotFoundError: If response status is 404
            Exception: For other HTTP error status codes (via raise_for_status)
        """
        # Handle 404 as FileNotFoundError to match other providers
        if response.status_code == 404:
            raise FileNotFoundError(f"Resource not found at URL: {url}")

        # Raise exception for other HTTP error status codes
        response.raise_for_status()

    def _handle_http_exceptions(self, e: Exception, url: str, operation: str) -> None:
        """
        Handle HTTP client exceptions and raise appropriate errors.

        Args:
            e: The exception that occurred
            url: URL being accessed
            operation: Description of the operation

        Raises:
            Exception: Converted exception with appropriate message
        """
        if isinstance(e, httpx.RequestError):
            logger.error(f"Network error while {operation} from {url}: {e}")
            raise Exception(f"Network error: {e}") from e
        elif isinstance(e, httpx.HTTPStatusError):
            logger.error(f"HTTP error {e.response.status_code} for {url}: {e}")
            raise Exception(
                f"HTTP {e.response.status_code}: {e.response.reason_phrase}"
            ) from e
        else:
            logger.error(f"Unexpected error {operation} from {url}: {e}")
            raise

    def _build_metadata_from_response(
        self, response: httpx.Response, url: str, include_content_length: bool = True
    ) -> dict[str, Any]:
        """
        Build metadata dict from HTTP response.

        Args:
            response: HTTP response object
            url: URL being accessed
            include_content_length: Whether to include content_length field

        Returns:
            dict: Metadata including HTTP headers and status
        """
        metadata = {
            "url": url,
            "status_code": response.status_code,
            "content_type": response.headers.get("content-type", ""),
            "headers": dict(response.headers),
            "provider": "http",
        }

        if include_content_length:
            if hasattr(response, "content") and response.content:
                # For GET responses, use actual content length
                metadata["content_length"] = len(response.content)
            elif "content-length" in response.headers:
                # For HEAD responses, use header value
                metadata["content_length"] = int(response.headers["content-length"])
            else:
                # Default to 0 if no content or header
                metadata["content_length"] = 0

        # Add content encoding if present
        if "content-encoding" in response.headers:
            metadata["content_encoding"] = response.headers["content-encoding"]

        return metadata

    def load(self, url: str) -> tuple[bytes, dict[str, Any]]:
        """
        Load content from an HTTP/HTTPS URL.

        Args:
            url: Complete HTTP or HTTPS URL to retrieve

        Returns:
            tuple: A tuple containing:
                - content (bytes): The HTTP response body
                - metadata (dict): Metadata including HTTP headers and status

        Raises:
            ValueError: If URL scheme is not http or https
            FileNotFoundError: If HTTP response status is 404
            Exception: For other HTTP errors or network issues
        """
        self._validate_url_scheme(url)

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url)
                self._handle_http_response(response, url)

                metadata = self._build_metadata_from_response(response, url)

                logger.info(
                    f"Successfully loaded {len(response.content)} bytes from {url}"
                )

                return response.content, metadata

        except Exception as e:
            self._handle_http_exceptions(e, url, "loading")
            raise  # This line should never be reached, but satisfies type checker

    def load_content(self, url: str) -> bytes:
        """
        Load only content from an HTTP/HTTPS URL.

        Args:
            url: Complete HTTP or HTTPS URL to retrieve

        Returns:
            bytes: The HTTP response body

        Raises:
            ValueError: If URL scheme is not http or https
            FileNotFoundError: If HTTP response status is 404
            Exception: For other HTTP errors or network issues
        """
        self._validate_url_scheme(url)

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url)
                self._handle_http_response(response, url)

                logger.info(
                    f"Successfully loaded {len(response.content)} bytes from {url}"
                )

                return response.content

        except Exception as e:
            self._handle_http_exceptions(e, url, "loading content")
            raise  # This line should never be reached, but satisfies type checker

    def load_metadata(self, url: str) -> dict[str, Any]:
        """
        Load only metadata from an HTTP/HTTPS URL using HEAD request.

        Args:
            url: Complete HTTP or HTTPS URL to retrieve metadata from

        Returns:
            dict: Metadata including HTTP headers and status

        Raises:
            ValueError: If URL scheme is not http or https
            FileNotFoundError: If HTTP response status is 404
            Exception: For other HTTP errors or network issues
        """
        self._validate_url_scheme(url)

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.head(url)
                self._handle_http_response(response, url)

                metadata = self._build_metadata_from_response(
                    response, url, include_content_length=True
                )

                logger.info(f"Successfully loaded metadata from {url}")

                return metadata

        except Exception as e:
            self._handle_http_exceptions(e, url, "loading metadata")
            raise  # This line should never be reached, but satisfies type checker

    def load_by_parts(
        self, who: str, what: str, object_id: str
    ) -> tuple[bytes, dict[str, Any]]:
        """
        HTTP provider doesn't support loading by parts.
        Use load(url) directly with complete HTTP URLs.

        Raises:
            NotImplementedError: HTTP URLs must be complete
        """
        # Parameters are intentionally unused for HTTP provider
        _ = who, what, object_id
        raise NotImplementedError(
            "HTTP provider requires complete URLs. "
            "Use load(url) directly with full HTTP/HTTPS URLs."
        )

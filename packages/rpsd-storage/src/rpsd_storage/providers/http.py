# SPDX-License-Identifier: BSD-3-Clause
# SPDX-FileCopyrightText: 2026 AGENZIA TPL BACINO CITTA' METROPOLITANA MILANO,
# MONZA E BRIANZA, LODI, PAVIA
from __future__ import annotations

import io
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, BinaryIO
from urllib.parse import urlparse

import httpx

from rpsd_storage.metadata import StorageMetadata

if TYPE_CHECKING:
    from _typeshed import WriteableBuffer

logger = logging.getLogger(__name__)

# Import StorageProvider after other imports to avoid circular dependency
from rpsd_storage.providers.base import StorageProvider  # noqa: E402


class _HttpxStreamReader(io.RawIOBase):
    """Adapt an httpx byte-chunk iterator into a readable BinaryIO.

    httpx exposes streamed bodies as an iterator of byte chunks rather than a
    file object with .read(n). This wraps that iterator so consumers (e.g.
    lxml's etree.parse) get a real readable stream. Wrap in io.BufferedReader
    for a buffered .read(n) on top of readinto().
    """

    def __init__(self, response: httpx.Response) -> None:
        # iter_bytes() transparently decodes content-encoding (gzip/deflate).
        self._chunks = response.iter_bytes()
        self._leftover = b""

    def readable(self) -> bool:
        return True

    def readinto(self, b: WriteableBuffer) -> int:
        if not self._leftover:
            self._leftover = next(self._chunks, b"")
            if not self._leftover:
                return 0
        buffer = memoryview(b)
        n = min(len(buffer), len(self._leftover))
        buffer[:n] = self._leftover[:n]
        self._leftover = self._leftover[n:]
        return n


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
        super().__init__(compare_before_save=False)
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
        who: str,
        what: str,
        content_type="application/xml",
        source_url=None,
        custom_metadata=None,
    ) -> tuple[str, StorageMetadata]:
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
        self, response: httpx.Response, url: str
    ) -> StorageMetadata:
        """
        Build metadata dict from HTTP response.

        Args:
            response: HTTP response object
            url: URL being accessed

        Returns:
            StorageMetadata: Metadata including HTTP headers and status
        """
        import hashlib
        from datetime import UTC, datetime
        from urllib.parse import urlparse

        from rpsd_storage.utils import generate_object_id

        content_length = None
        if hasattr(response, "content") and response.content:
            content_length = len(response.content)
        elif "content-length" in response.headers:
            content_length = int(response.headers["content-length"])

        # Calculate hash of content
        content_hash = hashlib.md5(response.content).hexdigest()

        # Extract filename from URL or Content-Disposition header
        original_filename = "unknown"
        if "content-disposition" in response.headers:
            cd_header = response.headers["content-disposition"]
            if "filename=" in cd_header:
                original_filename = cd_header.split("filename=")[1].strip('"')
        else:
            # Try to extract from URL path
            parsed_url = urlparse(url)
            if parsed_url.path and "/" in parsed_url.path:
                original_filename = parsed_url.path.split("/")[-1] or "unknown"

        # Generate object_id from URL
        parsed_url = urlparse(url)
        if parsed_url.path:
            object_id = f"http_{abs(hash(url))}_{generate_object_id()[:8]}"
        else:
            object_id = f"http_{generate_object_id()}"

        # Generate timestamp
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

        return StorageMetadata(
            provider="http",
            url=url,
            content_type=response.headers.get(
                "content-type", "application/octet-stream"
            ),
            content_length=content_length or 0,
            hash=content_hash,
            who="http",
            what="resource",
            original_filename=original_filename,
            object_id=object_id,
            save_stamp=timestamp,
            schema_version=1,
            source_url=url,  # For HTTP, source_url is the same as url
            etag=response.headers.get("etag"),  # HTTP ETag if present
            status_code=response.status_code,
            headers=dict(response.headers),
            content_encoding=response.headers.get("content-encoding"),
        )

    def load(self, url: str) -> tuple[bytes, StorageMetadata]:
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

    @contextmanager
    def open_content(self, url: str) -> Iterator[BinaryIO]:
        """
        Open content from an HTTP/HTTPS URL as a binary stream.

        Streams the response body without buffering it all in memory. The
        yielded stream is NOT seekable. The caller must NOT close it; the
        context manager closes the response and client on exit.

        Args:
            url: Complete HTTP or HTTPS URL to retrieve

        Raises:
            ValueError: If URL scheme is not http or https
            FileNotFoundError: If HTTP response status is 404
            Exception: For other HTTP errors or network issues
        """
        self._validate_url_scheme(url)

        with httpx.Client(timeout=self.timeout) as client:
            with client.stream("GET", url) as response:
                self._handle_http_response(response, url)
                logger.info(f"Opened content stream from {url}")
                yield io.BufferedReader(_HttpxStreamReader(response))

    def load_metadata(self, url: str) -> StorageMetadata:
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

                metadata = self._build_metadata_from_response(response, url)

                logger.info(f"Successfully loaded metadata from {url}")

                return metadata

        except Exception as e:
            self._handle_http_exceptions(e, url, "loading metadata")
            raise  # This line should never be reached, but satisfies type checker

    def delete(self, url: str) -> None:
        """
        Delete method is not implemented for HTTP provider.

        Args:
            url: Complete HTTP or HTTPS URL

        Raises:
            NotImplementedError: HTTP DELETE operations are not yet implemented
        """
        # Validate URL for consistency with other methods
        self._validate_url_scheme(url)

        raise NotImplementedError(
            "HTTP provider delete() method is not yet implemented. "
            "Only load() operations are currently supported."
        )

    def load_by_parts(
        self, who: str, what: str, object_id: str
    ) -> tuple[bytes, StorageMetadata]:
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

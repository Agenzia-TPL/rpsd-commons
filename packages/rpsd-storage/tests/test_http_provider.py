"""
Tests for HTTPStorageProvider.
"""

import pytest
import respx
from httpx import Response

from rpsd_storage.http import HTTPStorageProvider
from rpsd_storage.provider import StorageProvider

from .test_utils import TestContent


class TestHTTPStorageProviderInit:
    """Test HTTPStorageProvider initialization."""

    def test_init_with_default_timeout(self):
        """Test initialization with default timeout."""
        provider = HTTPStorageProvider()
        assert provider.timeout == 30.0

    def test_init_with_custom_timeout(self):
        """Test initialization with custom timeout."""
        provider = HTTPStorageProvider(timeout=60.0)
        assert provider.timeout == 60.0


class TestHTTPStorageProviderSave:
    """Test HTTPStorageProvider save method."""

    def test_save_raises_not_implemented(self):
        """Test that save method raises NotImplementedError."""
        provider = HTTPStorageProvider()

        with pytest.raises(
            NotImplementedError, match="save\\(\\) method is not yet implemented"
        ):
            provider.save(content=b"test data", filename="test.txt")


class TestHTTPStorageProviderLoad:
    """Test HTTPStorageProvider load method."""

    @respx.mock
    def test_load_successful_get(self):
        """Test successful HTTP GET request."""
        url = "https://example.com/test.txt"
        test_content = b"Hello, World!"

        respx.get(url).mock(
            return_value=Response(
                200,
                content=test_content,
                headers={
                    "content-type": "text/plain",
                    "content-length": str(len(test_content)),
                    "custom-header": "test-value",
                },
            )
        )

        provider = HTTPStorageProvider()
        content, metadata = provider.load(url)

        assert content == test_content
        assert metadata["url"] == url
        assert metadata["status_code"] == 200
        assert metadata["content_type"] == "text/plain"
        assert metadata["content_length"] == len(test_content)
        assert metadata["provider"] == "http"
        assert "headers" in metadata
        assert metadata["headers"]["custom-header"] == "test-value"

    @respx.mock
    def test_load_with_http_url(self):
        """Test loading from HTTP (not HTTPS) URL."""
        url = "http://example.com/data.json"
        test_content = b'{"key": "value"}'

        respx.get(url).mock(
            return_value=Response(
                200, content=test_content, headers={"content-type": "application/json"}
            )
        )

        provider = HTTPStorageProvider()
        content, metadata = provider.load(url)

        assert content == test_content
        assert metadata["content_type"] == "application/json"

    @respx.mock
    def test_load_with_content_encoding(self):
        """Test loading with content encoding header."""
        url = "https://example.com/compressed.txt"
        test_content = b"compressed data"

        # Mock the response without automatic decompression
        # to test that our metadata captures the header
        respx.get(url).mock(
            return_value=Response(
                200,
                content=test_content,
                headers={
                    "content-type": "text/plain",
                    "content-encoding": "identity",  # Use identity encoding
                },
            )
        )

        provider = HTTPStorageProvider()
        content, metadata = provider.load(url)

        assert content == test_content
        assert metadata["content_encoding"] == "identity"

    def test_load_invalid_url_scheme(self):
        """Test loading with invalid URL scheme."""
        provider = HTTPStorageProvider()

        with pytest.raises(ValueError, match="Unsupported URL scheme: ftp"):
            provider.load("ftp://example.com/file.txt")

    @respx.mock
    def test_load_404_error(self):
        """Test loading non-existent resource (404)."""
        url = "https://example.com/notfound.txt"

        respx.get(url).mock(return_value=Response(404))

        provider = HTTPStorageProvider()

        with pytest.raises(FileNotFoundError, match="Resource not found at URL"):
            provider.load(url)

    @respx.mock
    def test_load_500_error(self):
        """Test loading with server error (500)."""
        url = "https://example.com/error.txt"

        respx.get(url).mock(return_value=Response(500, text="Internal Server Error"))

        provider = HTTPStorageProvider()

        with pytest.raises(Exception, match="HTTP 500"):
            provider.load(url)

    @respx.mock
    def test_load_network_error(self):
        """Test loading with network error."""
        url = "https://example.com/unreachable.txt"

        respx.get(url).mock(side_effect=Exception("Connection failed"))

        provider = HTTPStorageProvider()

        with pytest.raises(Exception, match="Connection failed"):
            provider.load(url)

    @respx.mock
    def test_load_empty_content(self):
        """Test loading empty content."""
        url = "https://example.com/empty.txt"

        respx.get(url).mock(
            return_value=Response(
                200, content=b"", headers={"content-type": "text/plain"}
            )
        )

        provider = HTTPStorageProvider()
        content, metadata = provider.load(url)

        assert content == b""
        assert metadata["content_length"] == 0

    @respx.mock
    def test_load_large_content(self):
        """Test loading larger content."""
        url = "https://example.com/large.bin"
        test_content = b"x" * 10000  # 10KB of data

        respx.get(url).mock(
            return_value=Response(
                200,
                content=test_content,
                headers={"content-type": "application/octet-stream"},
            )
        )

        provider = HTTPStorageProvider()
        content, metadata = provider.load(url)

        assert content == test_content
        assert metadata["content_length"] == 10000


class TestHTTPStorageProviderBuildUrl:
    """Test HTTPStorageProvider _build_url method."""

    def test_build_url_raises_not_implemented(self):
        """Test that _build_url raises NotImplementedError."""
        provider = HTTPStorageProvider()

        with pytest.raises(
            NotImplementedError, match="HTTP provider requires complete URLs"
        ):
            provider._build_url("user", "document", "123.txt")


class TestHTTPStorageProviderLoadByParts:
    """Test HTTPStorageProvider load_by_parts method."""

    def test_load_by_parts_raises_not_implemented(self):
        """Test that load_by_parts raises NotImplementedError."""
        provider = HTTPStorageProvider()

        with pytest.raises(
            NotImplementedError, match="HTTP provider requires complete URLs"
        ):
            provider.load_by_parts("user", "document", "123.txt")


class TestHTTPProviderIntegration:
    """Test HTTP provider integration with static methods."""

    @respx.mock
    def test_load_from_url_with_http_scheme(self):
        """Test StorageProvider.load_from_url with HTTP URL."""
        url = "https://example.com/integration.txt"
        test_content = b"Integration test content"

        respx.get(url).mock(
            return_value=Response(
                200, content=test_content, headers={"content-type": "text/plain"}
            )
        )

        content, metadata = StorageProvider.load_from_url(url)

        assert content == test_content
        assert metadata["provider"] == "http"
        assert metadata["url"] == url

    @respx.mock
    def test_load_from_url_with_https_scheme(self):
        """Test StorageProvider.load_from_url with HTTPS URL."""
        url = "http://example.com/integration.json"
        test_content = b'{"test": "data"}'

        respx.get(url).mock(
            return_value=Response(
                200, content=test_content, headers={"content-type": "application/json"}
            )
        )

        content, metadata = StorageProvider.load_from_url(url)

        assert content == test_content
        assert metadata["provider"] == "http"
        assert metadata["content_type"] == "application/json"


class TestHTTPStorageProviderMetadata:
    """Test HTTP provider metadata structure."""

    @respx.mock
    def test_metadata_structure_compliance(self):
        """Test that HTTP provider metadata follows expected structure."""
        url = "https://example.com/metadata-test.xml"
        test_content = TestContent.XML_DATA

        respx.get(url).mock(
            return_value=Response(
                200,
                content=test_content,
                headers={
                    "content-type": "application/xml",
                    "last-modified": "Wed, 21 Oct 2023 07:28:00 GMT",
                    "etag": '"abc123"',
                },
            )
        )

        provider = HTTPStorageProvider()
        content, metadata = provider.load(url)

        # HTTP provider metadata has a different structure than file-based providers
        # It doesn't have the same required fields like object_id, etc.
        # Instead, verify HTTP-specific metadata structure

        # Verify HTTP-specific metadata
        assert metadata["provider"] == "http"
        assert metadata["url"] == url
        assert metadata["status_code"] == 200
        assert "headers" in metadata
        assert isinstance(metadata["headers"], dict)
        assert metadata["headers"]["etag"] == '"abc123"'

"""
Tests for HTTPCarrier with inline and outline metadata organization.
"""

import base64
import gzip
import warnings

import pytest
import respx
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from rpsd_transport.carriers import HTTPCarrier
from rpsd_transport.models import FastMessage


@pytest.fixture
def http_carrier():
    """Create HTTP carrier instance."""
    return HTTPCarrier(base_url="https://test.example.com", timeout=5.0)


@pytest.fixture
def test_app(http_carrier):
    """Create test FastAPI app with receive endpoint."""
    app = FastAPI()

    @app.post("/receive")
    async def receive(request: Request):
        return await http_carrier.handle_receive(request)

    return app


# =============================================================================
# Send Tests
# =============================================================================


class TestHTTPCarrierSendFast:
    """Test HTTPCarrier.send_slimfast() method."""

    @respx.mock
    def test_send_slimfast_success_inline(self, http_carrier):
        """Test successful fast message send with inline metadata (default)."""
        recipient = "https://external.example.com/webhook"
        test_data = b"Hello, World!"

        # Mock the HTTP POST response
        respx.post(recipient).mock(
            return_value=respx.MockResponse(200, json={"status": "received"})
        )

        result = http_carrier.send_slimfast(
            recipient=recipient,
            who="user123",
            what="document",
            content=test_data,
            content_type="text/plain",
            filename="test.txt",
        )

        assert result == {"status": "received"}

    @respx.mock
    def test_send_slimfast_payload_structure_inline(self, http_carrier):
        """Test send_slimfast creates correct inline metadata payload."""
        recipient = "https://external.example.com/webhook"
        test_data = b"Hello, World!"

        def check_request(request):
            import json

            body = json.loads(request.content)
            # Verify nested metadata structure
            assert "metadata" in body
            assert body["metadata"]["who"] == "user123"
            assert body["metadata"]["what"] == "document"
            assert body["metadata"]["content_type"] == "text/plain"
            assert body["metadata"]["filename"] == "test.txt"
            # Verify content is base64 encoded
            assert body["content"] == base64.b64encode(test_data).decode("utf-8")
            return respx.MockResponse(200, json={"status": "received"})

        respx.post(recipient).mock(side_effect=check_request)

        http_carrier.send_slimfast(
            recipient=recipient,
            who="user123",
            what="document",
            content=test_data,
            content_type="text/plain",
            filename="test.txt",
        )

    @respx.mock
    def test_send_slimfast_with_http_error(self, http_carrier):
        """Test send_slimfast with HTTP error."""
        recipient = "https://external.example.com/webhook"
        test_data = b"Test data"

        respx.post(recipient).mock(return_value=respx.MockResponse(500))

        with pytest.raises(Exception):
            http_carrier.send_slimfast(
                recipient=recipient,
                who="user123",
                what="document",
                content=test_data,
            )

    @respx.mock
    def test_send_slimfast_outline_body_headers(self, http_carrier):
        """Test fast message send with outline metadata (headers) and body."""
        recipient = "https://external.example.com/webhook"
        test_data = b"Hello, World!"

        def check_request(request):
            # Verify headers contain metadata
            assert request.headers["X-RPSD-WHO"] == "user123"
            assert request.headers["X-RPSD-WHAT"] == "document"
            assert request.headers["Content-Type"] == "text/plain"
            # Verify body is raw content (not base64)
            assert request.content == test_data
            return respx.MockResponse(200, json={"status": "received"})

        respx.post(recipient).mock(side_effect=check_request)

        result = http_carrier.send_slimfast(
            recipient=recipient,
            who="user123",
            what="document",
            content=test_data,
            content_type="text/plain",
            metadata_use_inline=False,
            metadata_use_headers=True,
            content_use_body=True,
        )

        assert result == {"status": "received"}

    @respx.mock
    def test_send_slimfast_outline_body_query_params(self, http_carrier):
        """Test fast message send with outline metadata (query params) and body."""
        recipient = "https://external.example.com/webhook"
        test_data = b"Hello, World!"

        def check_request(request):
            # Verify query params contain metadata
            assert "who=user123" in str(request.url)
            assert "what=document" in str(request.url)
            # Verify body is raw content
            assert request.content == test_data
            assert request.headers["Content-Type"] == "text/plain"
            return respx.MockResponse(200, json={"status": "received"})

        respx.post(recipient).mock(side_effect=check_request)

        result = http_carrier.send_slimfast(
            recipient=recipient,
            who="user123",
            what="document",
            content=test_data,
            content_type="text/plain",
            metadata_use_inline=False,
            metadata_use_headers=False,
            content_use_body=True,
        )

        assert result == {"status": "received"}

    @respx.mock
    def test_send_slimfast_outline_attachment_headers(self, http_carrier):
        """Test fast message send with outline metadata (headers) and attachment."""
        recipient = "https://external.example.com/webhook"
        test_data = b"Hello, World!"

        def check_request(request):
            # Verify headers contain metadata
            assert request.headers["X-RPSD-WHO"] == "user123"
            assert request.headers["X-RPSD-WHAT"] == "document"
            # Verify it's multipart
            assert "multipart/form-data" in request.headers.get("Content-Type", "")
            # Verify data is in body
            assert test_data in request.content
            return respx.MockResponse(200, json={"status": "received"})

        respx.post(recipient).mock(side_effect=check_request)

        result = http_carrier.send_slimfast(
            recipient=recipient,
            who="user123",
            what="document",
            content=test_data,
            content_type="text/plain",
            filename="test.txt",
            metadata_use_inline=False,
            metadata_use_headers=True,
            content_use_body=False,
        )

        assert result == {"status": "received"}

    @respx.mock
    def test_send_slimfast_outline_attachment_query_params(self, http_carrier):
        """
        Test fast message send with outline metadata (query params)
        and attachment.
        """
        recipient = "https://external.example.com/webhook"
        test_data = b"Hello, World!"

        def check_request(request):
            # Verify query params contain metadata
            assert "who=user123" in str(request.url)
            assert "what=document" in str(request.url)
            # Verify it's multipart
            assert "multipart/form-data" in request.headers.get("Content-Type", "")
            # Verify data is in body
            assert test_data in request.content
            return respx.MockResponse(200, json={"status": "received"})

        respx.post(recipient).mock(side_effect=check_request)

        result = http_carrier.send_slimfast(
            recipient=recipient,
            who="user123",
            what="document",
            content=test_data,
            content_type="text/plain",
            filename="test.txt",
            metadata_use_inline=False,
            metadata_use_headers=False,
            content_use_body=False,
        )

        assert result == {"status": "received"}


class TestHTTPCarrierSendHeavy:
    """Test HTTPCarrier.send_fatheavy() method."""

    def test_send_fatheavy_validation_no_content_no_where(self, http_carrier):
        """Test that heavy mode requires either content or where."""
        with pytest.raises(ValueError, match="Must provide either"):
            http_carrier.send_fatheavy(
                recipient="https://example.com/webhook",
                who="user123",
                what="document",
                content=None,
                where=None,
            )

    def test_send_fatheavy_validation_content_without_where(self, http_carrier):
        """Test that providing content without where raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="Phase 2"):
            http_carrier.send_fatheavy(
                recipient="https://example.com/webhook",
                who="user123",
                what="document",
                content=b"test",
                where=None,
            )

    @respx.mock
    def test_send_fatheavy_inline(self, http_carrier):
        """Test heavy message send with inline metadata."""
        recipient = "https://external.example.com/webhook"
        where_url = "https://storage.example.com/file123"

        def check_request(request):
            import json

            body = json.loads(request.content)
            # Verify metadata structure with where URL
            assert "metadata" in body
            assert body["metadata"]["who"] == "user123"
            assert body["metadata"]["what"] == "document"
            assert body["metadata"]["where"] == where_url
            assert body["content"] is None
            return respx.MockResponse(200, json={"status": "received"})

        respx.post(recipient).mock(side_effect=check_request)

        result = http_carrier.send_fatheavy(
            recipient=recipient,
            who="user123",
            what="document",
            content=None,
            where=where_url,
        )

        assert result == {"status": "received"}

    @respx.mock
    def test_send_fatheavy_outline_headers(self, http_carrier):
        """Test heavy message send with outline metadata (headers)."""
        recipient = "https://external.example.com/webhook"
        where_url = "https://storage.example.com/file123"

        def check_request(request):
            # Verify headers contain metadata including where
            assert request.headers["X-RPSD-WHO"] == "user123"
            assert request.headers["X-RPSD-WHAT"] == "document"
            assert request.headers["X-RPSD-WHERE"] == where_url
            # Verify empty body
            assert request.content == b""
            return respx.MockResponse(200, json={"status": "received"})

        respx.post(recipient).mock(side_effect=check_request)

        result = http_carrier.send_fatheavy(
            recipient=recipient,
            who="user123",
            what="document",
            content=None,
            where=where_url,
            metadata_use_inline=False,
            metadata_use_headers=True,
        )

        assert result == {"status": "received"}

    @respx.mock
    def test_send_fatheavy_outline_query_params(self, http_carrier):
        """Test heavy message send with outline metadata (query params)."""
        recipient = "https://external.example.com/webhook"
        where_url = "https://storage.example.com/file123"

        def check_request(request):
            # Verify query params contain metadata including where
            assert "who=user123" in str(request.url)
            assert "what=document" in str(request.url)
            assert "where=https" in str(request.url)
            # Verify empty body
            assert request.content == b""
            return respx.MockResponse(200, json={"status": "received"})

        respx.post(recipient).mock(side_effect=check_request)

        result = http_carrier.send_fatheavy(
            recipient=recipient,
            who="user123",
            what="document",
            content=None,
            where=where_url,
            metadata_use_inline=False,
            metadata_use_headers=False,
        )

        assert result == {"status": "received"}


# =============================================================================
# Receive Tests - Inline Metadata
# =============================================================================


class TestHTTPCarrierReceiveInline:
    """Test HTTPCarrier.handle_receive() with inline metadata."""

    def test_receive_inline_fast_message(self, test_app):
        """Test receiving fast message with inline JSON metadata."""
        client = TestClient(test_app)
        test_data = b"Test payload"

        message = {
            "metadata": {
                "who": "user123",
                "what": "document",
                "content_type": "text/plain",
            },
            "content": base64.b64encode(test_data).decode("utf-8"),
        }

        response = client.post("/receive", json=message)

        assert response.status_code == 200
        assert response.json()["status"] == "received"

    def test_receive_inline_heavy_message(self, test_app):
        """Test receiving heavy message with inline JSON metadata."""
        client = TestClient(test_app)

        message = {
            "metadata": {
                "who": "user123",
                "what": "document",
                "where": "https://storage.example.com/file.xml",
            },
        }

        response = client.post("/receive", json=message)

        # Heavy mode returns 501 (not implemented yet)
        assert response.status_code == 501
        assert response.json()["error_code"] == "not_implemented"

    def test_receive_inline_with_compression_gzip(self, test_app):
        """Test receiving compressed content in inline format (GZIP)."""
        client = TestClient(test_app)
        original = b"Hello, World! This is compressed content."
        compressed = gzip.compress(original)

        message = {
            "metadata": {
                "who": "user123",
                "what": "document",
                "filename": "data.gz",
            },
            "content": base64.b64encode(compressed).decode("utf-8"),
        }

        response = client.post("/receive", json=message)

        assert response.status_code == 200
        assert response.json()["status"] == "received"

    def test_receive_inline_invalid_json(self, test_app):
        """Test receiving invalid JSON falls back to outline mode."""
        client = TestClient(test_app)

        # When JSON parsing fails, detection falls back to outline mode
        # which requires metadata in headers/query params
        response = client.post(
            "/receive",
            content="not valid json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 400
        # Falls back to outline mode, which requires who/what in headers
        assert response.json()["error_code"] == "missing_metadata"

    def test_receive_inline_missing_who(self, test_app):
        """Test receiving inline message missing 'who' falls back to outline."""
        client = TestClient(test_app)

        # Missing 'who' in metadata means detection sees incomplete inline
        # and falls back to outline mode
        message = {
            "metadata": {
                "what": "document",
            },
            "content": base64.b64encode(b"test").decode("utf-8"),
        }

        response = client.post("/receive", json=message)

        assert response.status_code == 400
        # Falls back to outline mode due to incomplete metadata
        assert response.json()["error_code"] == "missing_metadata"

    def test_receive_inline_missing_what(self, test_app):
        """Test receiving inline message missing 'what' falls back to outline."""
        client = TestClient(test_app)

        # Missing 'what' in metadata means detection sees incomplete inline
        # and falls back to outline mode
        message = {
            "metadata": {
                "who": "user123",
            },
            "content": base64.b64encode(b"test").decode("utf-8"),
        }

        response = client.post("/receive", json=message)

        assert response.status_code == 400
        # Falls back to outline mode due to incomplete metadata
        assert response.json()["error_code"] == "missing_metadata"

    def test_receive_inline_fast_missing_content(self, test_app):
        """Test receiving fast inline message without content."""
        client = TestClient(test_app)

        message = {
            "metadata": {
                "who": "user123",
                "what": "document",
            },
            # Missing content for fast message
        }

        response = client.post("/receive", json=message)

        assert response.status_code == 400
        assert response.json()["error_code"] == "missing_fields"

    def test_receive_inline_invalid_identifier(self, test_app):
        """Test receiving inline message with invalid identifier."""
        client = TestClient(test_app)

        message = {
            "metadata": {
                "who": "user@123",  # Invalid character @
                "what": "document",
            },
            "content": base64.b64encode(b"test").decode("utf-8"),
        }

        response = client.post("/receive", json=message)

        assert response.status_code == 400
        # Could be missing_fields due to Pydantic validation
        assert response.json()["status"] == "failed"


# =============================================================================
# Receive Tests - Outline Metadata
# =============================================================================


class TestHTTPCarrierReceiveOutline:
    """Test HTTPCarrier.handle_receive() with outline metadata."""

    def test_receive_outline_raw_body(self, test_app):
        """Test receiving with metadata in headers, content in raw body."""
        client = TestClient(test_app)
        test_data = b"<xml>content</xml>"

        response = client.post(
            "/receive",
            content=test_data,
            headers={
                "Content-Type": "application/xml",
                "X-RPSD-WHO": "user123",
                "X-RPSD-WHAT": "document",
            },
        )

        assert response.status_code == 200
        assert response.json()["status"] == "received"

    def test_receive_outline_with_query_params(self, test_app):
        """Test receiving with metadata in query parameters."""
        client = TestClient(test_app)
        test_data = b"plain text content"

        response = client.post(
            "/receive?who=user123&what=document",
            content=test_data,
            headers={"Content-Type": "text/plain"},
        )

        assert response.status_code == 200
        assert response.json()["status"] == "received"

    def test_receive_outline_legacy_headers(self, test_app):
        """Test receiving with legacy X-RAPS-INGEST_* headers."""
        client = TestClient(test_app)
        test_data = b"legacy content"

        response = client.post(
            "/receive",
            content=test_data,
            headers={
                "Content-Type": "application/octet-stream",
                "X-RAPS-INGEST_WHO": "user123",
                "X-RAPS-INGEST_WHAT": "document",
            },
        )

        assert response.status_code == 200
        assert response.json()["status"] == "received"

    def test_receive_outline_heavy_message(self, test_app):
        """Test receiving heavy message with 'where' in header."""
        client = TestClient(test_app)

        response = client.post(
            "/receive",
            content=b"",  # No body content for heavy message
            headers={
                "X-RPSD-WHO": "user123",
                "X-RPSD-WHAT": "document",
                "X-RPSD-WHERE": "https://storage.example.com/file.xml",
            },
        )

        # Heavy mode returns 501 (not implemented yet)
        assert response.status_code == 501

    def test_receive_outline_multipart(self, test_app):
        """Test receiving with multipart/form-data attachment."""
        client = TestClient(test_app)

        response = client.post(
            "/receive",
            files={"file": ("test.xml", b"<xml>content</xml>", "application/xml")},
            headers={
                "X-RPSD-WHO": "user123",
                "X-RPSD-WHAT": "document",
            },
        )

        assert response.status_code == 200
        assert response.json()["status"] == "received"

    def test_receive_outline_with_compression(self, test_app):
        """Test receiving compressed content in outline format."""
        client = TestClient(test_app)
        original = b"Compressed outline content"
        compressed = gzip.compress(original)

        response = client.post(
            "/receive?who=user123&what=document",
            content=compressed,
            headers={"Content-Type": "application/gzip"},
        )

        # Content is auto-decompressed based on magic bytes
        assert response.status_code == 200
        assert response.json()["status"] == "received"


# =============================================================================
# Receive Tests - Validation Errors
# =============================================================================


class TestHTTPCarrierReceiveValidation:
    """Test validation error handling."""

    def test_reject_duplicate_metadata_header_and_query(self, test_app):
        """Test rejection when metadata in both header and query param."""
        client = TestClient(test_app)

        response = client.post(
            "/receive?who=user123",  # who in query
            content=b"test content",
            headers={
                "Content-Type": "text/plain",
                "X-RPSD-WHO": "user456",  # who also in header
                "X-RPSD-WHAT": "document",
            },
        )

        assert response.status_code == 400
        assert response.json()["error_code"] == "duplicate_metadata"

    def test_reject_missing_who_outline(self, test_app):
        """Test rejection when 'who' is missing in outline mode."""
        client = TestClient(test_app)

        response = client.post(
            "/receive",
            content=b"test content",
            headers={
                "Content-Type": "text/plain",
                "X-RPSD-WHAT": "document",
                # Missing X-RPSD-WHO
            },
        )

        assert response.status_code == 400
        assert response.json()["error_code"] == "missing_metadata"

    def test_reject_missing_what_outline(self, test_app):
        """Test rejection when 'what' is missing in outline mode."""
        client = TestClient(test_app)

        response = client.post(
            "/receive",
            content=b"test content",
            headers={
                "Content-Type": "text/plain",
                "X-RPSD-WHO": "user123",
                # Missing X-RPSD-WHAT
            },
        )

        assert response.status_code == 400
        assert response.json()["error_code"] == "missing_metadata"

    def test_reject_invalid_identifier_outline(self, test_app):
        """Test rejection of invalid identifier in outline mode."""
        client = TestClient(test_app)

        response = client.post(
            "/receive",
            content=b"test content",
            headers={
                "Content-Type": "text/plain",
                "X-RPSD-WHO": "user@invalid",  # Invalid character
                "X-RPSD-WHAT": "document",
            },
        )

        assert response.status_code == 400
        assert response.json()["error_code"] == "invalid_identifier"


# =============================================================================
# Legacy Model Tests (Deprecated)
# =============================================================================


class TestFastMessage:
    """Test FastMessage model (deprecated)."""

    def test_fast_message_creation(self):
        """Test creating a FastMessage (with deprecation warning)."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            msg = FastMessage(
                mode="fast",
                who="user123",
                what="document",
                data=b"test",
                content_type="text/plain",
                filename="test.txt",
            )

            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "deprecated" in str(w[0].message).lower()

        assert msg.mode == "fast"
        assert msg.who == "user123"
        assert msg.what == "document"
        assert msg.data == b"test"
        assert msg.content_type == "text/plain"
        assert msg.filename == "test.txt"

    def test_fast_message_defaults(self):
        """Test FastMessage with default values."""
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            msg = FastMessage(mode="fast", who="user123", what="document", data=b"test")

        assert msg.content_type == "application/octet-stream"
        assert msg.filename is None

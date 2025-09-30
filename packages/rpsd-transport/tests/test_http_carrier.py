"""
Minimal tests for HTTPCarrier fast mode.
"""

import base64

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


class TestHTTPCarrierSendFast:
    """Test HTTPCarrier.send_fast() method."""

    @respx.mock
    def test_send_fast_success(self, http_carrier):
        """Test successful fast message send."""
        recipient = "https://external.example.com/webhook"
        test_data = b"Hello, World!"

        # Mock the HTTP POST response
        respx.post(recipient).mock(
            return_value=respx.MockResponse(200, json={"status": "received"})
        )

        result = http_carrier.send_fast(
            recipient=recipient,
            data=test_data,
            who="user123",
            what="document",
            content_type="text/plain",
            filename="test.txt",
        )

        assert result == {"status": "received"}

    @respx.mock
    def test_send_fast_with_http_error(self, http_carrier):
        """Test send_fast with HTTP error."""
        recipient = "https://external.example.com/webhook"
        test_data = b"Test data"

        # Mock HTTP error
        respx.post(recipient).mock(return_value=respx.MockResponse(500))

        with pytest.raises(Exception):
            http_carrier.send_fast(
                recipient=recipient,
                data=test_data,
                who="user123",
                what="document",
            )


class TestHTTPCarrierSendHeavy:
    """Test HTTPCarrier.send_heavy() method."""

    def test_send_heavy_not_implemented(self, http_carrier):
        """Test that heavy mode raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="Heavy mode not yet"):
            http_carrier.send_heavy(
                recipient="https://example.com/webhook",
                who="user123",
                what="document",
                data=b"test",
            )


class TestHTTPCarrierReceive:
    """Test HTTPCarrier.handle_receive() method."""

    def test_receive_fast_message_success(self, test_app):
        """Test receiving a valid fast message."""
        client = TestClient(test_app)
        test_data = b"Test payload"

        message = {
            "mode": "fast",
            "who": "user123",
            "what": "document",
            "data": base64.b64encode(test_data).decode("utf-8"),
            "content_type": "application/octet-stream",
        }

        response = client.post("/receive", json=message)

        assert response.status_code == 200
        assert response.json()["status"] == "received"

    def test_receive_invalid_json(self, test_app):
        """Test receiving invalid JSON."""
        client = TestClient(test_app)

        response = client.post(
            "/receive",
            content="not json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 400
        assert response.json()["error_code"] == "invalid_json"

    def test_receive_missing_fields(self, test_app):
        """Test receiving message with missing required fields."""
        client = TestClient(test_app)

        message = {"mode": "fast"}  # Missing who and what

        response = client.post("/receive", json=message)

        assert response.status_code == 400
        assert response.json()["error_code"] == "missing_fields"

    def test_receive_heavy_not_implemented(self, test_app):
        """Test that heavy mode returns not implemented."""
        client = TestClient(test_app)

        message = {
            "mode": "heavy",
            "who": "user123",
            "what": "document",
            "where": "https://external.com/data",
        }

        response = client.post("/receive", json=message)

        assert response.status_code == 501
        assert response.json()["error_code"] == "not_implemented"

    def test_receive_invalid_mode(self, test_app):
        """Test receiving message with invalid mode."""
        client = TestClient(test_app)

        message = {"mode": "invalid", "who": "user123", "what": "document"}

        response = client.post("/receive", json=message)

        assert response.status_code == 400
        assert response.json()["error_code"] == "invalid_mode"

    def test_receive_fast_missing_data(self, test_app):
        """Test receiving fast message without data field."""
        client = TestClient(test_app)

        message = {
            "mode": "fast",
            "who": "user123",
            "what": "document",
            # Missing data field
        }

        response = client.post("/receive", json=message)

        assert response.status_code == 400
        assert response.json()["error_code"] == "missing_data"


class TestFastMessage:
    """Test FastMessage model."""

    def test_fast_message_creation(self):
        """Test creating a FastMessage."""
        msg = FastMessage(
            mode="fast",
            who="user123",
            what="document",
            data=b"test",
            content_type="text/plain",
            filename="test.txt",
        )

        assert msg.mode == "fast"
        assert msg.who == "user123"
        assert msg.what == "document"
        assert msg.data == b"test"
        assert msg.content_type == "text/plain"
        assert msg.filename == "test.txt"

    def test_fast_message_defaults(self):
        """Test FastMessage with default values."""
        msg = FastMessage(mode="fast", who="user123", what="document", data=b"test")

        assert msg.content_type == "application/octet-stream"
        assert msg.filename is None

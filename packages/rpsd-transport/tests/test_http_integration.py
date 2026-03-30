"""
Integration tests for HTTPCarrier - testing send and receive together.

These tests verify that messages sent via send_slimfast/send_fatheavy can be
successfully received and parsed by the receive method, ensuring complete
round-trip communication works correctly.
"""

import base64

import httpx
import pytest
import respx
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from rpsd_transport.carriers.http import HTTPCarrier, HTTPCarrierOptions
from rpsd_transport.carriers.utils import (
    exception_to_json_response,
    message_to_json_response,
)


@pytest.fixture
def receiving_app():
    """Create a FastAPI app that receives messages."""
    app = FastAPI()
    carrier = HTTPCarrier()

    @app.post("/receive")
    async def receive_endpoint(request: Request):
        try:
            message = await carrier.receive(request)
            return message_to_json_response(message)
        except Exception as e:
            return exception_to_json_response(e)

    return app


@pytest.fixture
def test_client(receiving_app):
    """Create a test client for the receiving app."""
    return TestClient(receiving_app)


@pytest.fixture
def sending_carrier():
    """Create an HTTPCarrier for sending messages."""
    return HTTPCarrier(base_url="http://testserver", timeout=30)


class TestSlimfastIntegration:
    """Test slim/fast message round-trips."""

    def test_slimfast_inline_roundtrip(self, test_client, sending_carrier):
        """Test send/receive slim/fast with inline metadata."""
        content = b"Test content for slim/fast inline message"
        who = "test-sender"
        what = "test-data"

        with respx.mock:
            route = respx.post("http://testserver/receive").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "status": "received",
                        "internal_url": None,
                    },
                )
            )

            response = sending_carrier.send_slimfast(
                recipient="http://testserver/receive",
                who=who,
                what=what,
                content=content,
                content_type="text/plain",
            )

            assert response["status"] == "received"

            assert route.called
            request = route.calls.last.request

            actual_response = test_client.post(
                "/receive",
                content=request.content,
                headers=dict(request.headers),
            )

            assert actual_response.status_code == 200
            data = actual_response.json()
            assert data["status"] == "received"

    def test_slimfast_outline_with_headers(self, test_client, sending_carrier):
        """Test send/receive slim/fast with outline metadata."""
        content = b"Test content for outline headers"
        who = "test-sender"
        what = "test-data"

        with respx.mock:
            route = respx.post("http://testserver/receive").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "status": "received",
                        "internal_url": None,
                    },
                )
            )

            response = sending_carrier.send_slimfast(
                recipient="http://testserver/receive",
                who=who,
                what=what,
                content=content,
                content_type="text/plain",
                options=HTTPCarrierOptions(
                    metadata_use_inline=False,
                    metadata_use_headers=True,
                    content_use_body=True,
                ),
            )

            assert response["status"] == "received"

            request = route.calls.last.request

            actual_response = test_client.post(
                "/receive",
                content=request.content,
                headers=dict(request.headers),
            )

            assert actual_response.status_code == 200
            data = actual_response.json()
            assert data["status"] == "received"

    def test_slimfast_outline_with_query_params(self, test_client, sending_carrier):
        """Test send/receive slim/fast with outline query params."""
        content = b"Test content for outline query params"
        who = "test-sender"
        what = "test-data"

        with respx.mock:
            route = respx.post("http://testserver/receive").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "status": "received",
                        "internal_url": None,
                    },
                )
            )

            response = sending_carrier.send_slimfast(
                recipient="http://testserver/receive",
                who=who,
                what=what,
                content=content,
                content_type="text/plain",
                options=HTTPCarrierOptions(
                    metadata_use_inline=False,
                    metadata_use_headers=False,
                    content_use_body=True,
                ),
            )

            assert response["status"] == "received"

            request = route.calls.last.request

            actual_response = test_client.post(
                request.url.path + "?" + request.url.query.decode(),
                content=request.content,
                headers=dict(request.headers),
            )

            assert actual_response.status_code == 200
            data = actual_response.json()
            assert data["status"] == "received"

    def test_slimfast_outline_with_multipart(self, test_client, sending_carrier):
        """Test send/receive slim/fast with multipart form data."""
        content = b"Test content for multipart"
        who = "test-sender"
        what = "test-data"

        with respx.mock:
            route = respx.post("http://testserver/receive").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "status": "received",
                        "internal_url": None,
                    },
                )
            )

            response = sending_carrier.send_slimfast(
                recipient="http://testserver/receive",
                who=who,
                what=what,
                content=content,
                content_type="text/plain",
                filename="test.txt",
                options=HTTPCarrierOptions(
                    metadata_use_inline=False,
                    metadata_use_headers=True,
                    content_use_body=False,
                ),
            )

            assert response["status"] == "received"

            request = route.calls.last.request

            actual_response = test_client.post(
                "/receive",
                content=request.content,
                headers=dict(request.headers),
            )

            assert actual_response.status_code == 200
            data = actual_response.json()
            assert data["status"] == "received"


class TestFatheavyIntegration:
    """Test fat/heavy message round-trips."""

    def test_fatheavy_inline_with_where(self, test_client, sending_carrier):
        """Test send/receive fat/heavy message with where URL."""
        who = "test-sender"
        what = "test-data"
        where = "https://example.com/external/content.xml"

        with respx.mock:
            route = respx.post("http://testserver/receive").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "status": "received",
                        "internal_url": None,
                    },
                )
            )

            response = sending_carrier.send_fatheavy(
                recipient="http://testserver/receive",
                who=who,
                what=what,
                content=None,
                where=where,
            )

            assert response["status"] == "received"

            request = route.calls.last.request

            actual_response = test_client.post(
                "/receive",
                content=request.content,
                headers=dict(request.headers),
            )

            assert actual_response.status_code == 200
            data = actual_response.json()
            assert data["status"] == "received"

    def test_fatheavy_outline_with_headers(self, test_client, sending_carrier):
        """Test send/receive fat/heavy with outline metadata."""
        who = "test-sender"
        what = "test-data"
        where = "https://example.com/external/data.json"

        with respx.mock:
            route = respx.post("http://testserver/receive").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "status": "received",
                        "internal_url": None,
                    },
                )
            )

            response = sending_carrier.send_fatheavy(
                recipient="http://testserver/receive",
                who=who,
                what=what,
                content=None,
                where=where,
                options=HTTPCarrierOptions(
                    metadata_use_inline=False,
                    metadata_use_headers=True,
                ),
            )

            assert response["status"] == "received"

            request = route.calls.last.request

            actual_response = test_client.post(
                "/receive",
                content=request.content,
                headers=dict(request.headers),
            )

            assert actual_response.status_code == 200
            data = actual_response.json()
            assert data["status"] == "received"


class TestEndToEndWithStorage:
    """Test end-to-end scenarios with storage integration via hook."""

    def test_roundtrip_with_storage_hook(self, test_client):
        """Test complete round-trip with storage integration."""
        from rpsd_transport.models import TransportMessage

        saved_messages = []

        class StorageHTTPCarrier(HTTPCarrier):
            def received(self, message: TransportMessage) -> None:
                """Hook to track received messages."""
                saved_messages.append(
                    {
                        "who": message.who,
                        "what": message.what,
                        "content_size": (
                            len(message.content) if message.content else 0
                        ),
                        "is_heavy": message.is_fatheavy,
                        "where": (message.where if message.is_fatheavy else None),
                    }
                )

        app = FastAPI()
        carrier = StorageHTTPCarrier()

        @app.post("/receive")
        async def receive_endpoint(request: Request):
            try:
                message = await carrier.receive(request)
                return message_to_json_response(message)
            except Exception as e:
                return exception_to_json_response(e)

        client = TestClient(app)

        # Send a fast message
        response = client.post(
            "/receive",
            json={
                "metadata": {"who": "sender", "what": "data"},
                "content": base64.b64encode(b"test content").decode(),
            },
            headers={"content-type": "application/json"},
        )

        assert response.status_code == 200
        assert len(saved_messages) == 1
        assert saved_messages[0]["who"] == "sender"
        assert saved_messages[0]["what"] == "data"
        assert saved_messages[0]["content_size"] == 12
        assert not saved_messages[0]["is_heavy"]

        # Send a heavy message
        response = client.post(
            "/receive",
            json={
                "metadata": {
                    "who": "sender",
                    "what": "data",
                    "where": "https://example.com/file.xml",
                },
                "content": None,
            },
            headers={"content-type": "application/json"},
        )

        assert response.status_code == 200
        assert len(saved_messages) == 2
        assert saved_messages[1]["is_heavy"]
        assert saved_messages[1]["where"] == "https://example.com/file.xml"

    def test_received_hook_can_reject_messages(self, test_client):
        """Test that received() hook can reject messages."""
        from rpsd_transport.models import TransportMessage

        class ValidatingCarrier(HTTPCarrier):
            def received(self, message: TransportMessage) -> None:
                """Hook that validates who is allowed."""
                allowed_entities = ["trusted-sender", "admin"]
                if message.who not in allowed_entities:
                    raise ValueError(f"Unauthorized entity: {message.who}")

        app = FastAPI()
        carrier = ValidatingCarrier()

        @app.post("/receive")
        async def receive_endpoint(request: Request):
            try:
                message = await carrier.receive(request)
                return message_to_json_response(message)
            except Exception as e:
                return exception_to_json_response(e)

        client = TestClient(app)

        # Authorized sender should succeed
        response = client.post(
            "/receive",
            json={
                "metadata": {
                    "who": "trusted-sender",
                    "what": "data",
                },
                "content": base64.b64encode(b"test").decode(),
            },
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 200

        # Unauthorized sender should be rejected
        response = client.post(
            "/receive",
            json={
                "metadata": {
                    "who": "untrusted-sender",
                    "what": "data",
                },
                "content": base64.b64encode(b"test").decode(),
            },
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "failed"
        assert "Unauthorized entity" in data["message"]

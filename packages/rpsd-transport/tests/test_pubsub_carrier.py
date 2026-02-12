"""
Tests for PubSubCarrier base class and KafkaPubSubCarrier.

PubSubCarrier.receive() is tested directly (sync parser).
KafkaPubSubCarrier send/consume methods use mocked aiokafka.
"""

import base64
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rpsd_transport.carriers.pubsub.base import PubSubCarrier
from rpsd_transport.carriers.pubsub.kafka import (
    KafkaCarrierOptions,
    KafkaPubSubCarrier,
)
from rpsd_transport.models import TransportMessage


@pytest.fixture
def anyio_backend():
    """Use asyncio backend only (trio not installed)."""
    return "asyncio"


# =============================================================================
# Concrete PubSubCarrier for testing the base class
# =============================================================================


class StubPubSubCarrier(PubSubCarrier):
    """Minimal concrete PubSubCarrier for testing base methods."""

    def send_slimfast(self, recipient, who, what, content, **kwargs):
        return {"status": "sent"}

    def send_fatheavy(self, recipient, who, what, content, **kwargs):
        return {"status": "sent"}

    async def consume(self, topic):
        yield  # pragma: no cover

    async def start(self) -> None:
        """No-op start for testing."""
        pass

    async def stop(self) -> None:
        """No-op stop for testing."""
        pass


# =============================================================================
# PubSubCarrier.receive() — inline metadata
# =============================================================================


class TestPubSubReceiveInline:
    """Test PubSubCarrier.receive() with inline JSON messages."""

    def test_receive_inline_fast_message(self):
        """Parse inline fast message with base64 content."""
        carrier = StubPubSubCarrier()
        payload = {
            "metadata": {
                "who": "sender1",
                "what": "report",
                "content_type": "text/plain",
            },
            "content": base64.b64encode(b"hello world").decode("utf-8"),
        }
        raw = json.dumps(payload).encode("utf-8")

        msg = carrier.receive(raw)

        assert isinstance(msg, TransportMessage)
        assert msg.who == "sender1"
        assert msg.what == "report"
        assert msg.content == b"hello world"
        assert msg.is_slimfast is True

    def test_receive_inline_heavy_message(self):
        """Parse inline heavy message (where URL, no content)."""
        carrier = StubPubSubCarrier()
        payload = {
            "metadata": {
                "who": "sender1",
                "what": "report",
                "where": "https://storage.example.com/file.xml",
            },
            "content": None,
        }
        raw = json.dumps(payload).encode("utf-8")

        msg = carrier.receive(raw)

        assert msg.is_fatheavy is True
        assert msg.where == "https://storage.example.com/file.xml"
        assert msg.content is None

    def test_receive_inline_fast_missing_content_raises(self):
        """Fast inline message without content raises ValueError."""
        carrier = StubPubSubCarrier()
        payload = {
            "metadata": {
                "who": "sender1",
                "what": "report",
            },
        }
        raw = json.dumps(payload).encode("utf-8")

        with pytest.raises(ValueError, match="Fast message requires"):
            carrier.receive(raw)

    def test_receive_inline_with_filename(self):
        """Parse inline message with optional filename."""
        carrier = StubPubSubCarrier()
        payload = {
            "metadata": {
                "who": "sender1",
                "what": "report",
                "content_type": "application/pdf",
                "filename": "report.pdf",
            },
            "content": base64.b64encode(b"pdf-bytes").decode("utf-8"),
        }
        raw = json.dumps(payload).encode("utf-8")

        msg = carrier.receive(raw)

        assert msg.metadata.filename == "report.pdf"
        assert msg.metadata.content_type == "application/pdf"

    def test_receive_inline_ignores_non_dict(self):
        """Non-dict JSON falls through to outline parsing."""
        carrier = StubPubSubCarrier()
        raw = json.dumps([1, 2, 3]).encode("utf-8")

        with pytest.raises(ValueError, match="no headers provided"):
            carrier.receive(raw)

    def test_receive_inline_ignores_missing_metadata_key(self):
        """Dict without 'metadata' key falls through to outline."""
        carrier = StubPubSubCarrier()
        raw = json.dumps({"data": "something"}).encode("utf-8")

        with pytest.raises(ValueError, match="no headers provided"):
            carrier.receive(raw)

    def test_receive_inline_ignores_missing_who(self):
        """Dict with metadata missing 'who' falls through."""
        carrier = StubPubSubCarrier()
        payload = {
            "metadata": {"what": "report"},
            "content": "abc",
        }
        raw = json.dumps(payload).encode("utf-8")

        with pytest.raises(ValueError, match="no headers provided"):
            carrier.receive(raw)


# =============================================================================
# PubSubCarrier.receive() — outline metadata (headers)
# =============================================================================


class TestPubSubReceiveOutline:
    """Test PubSubCarrier.receive() with outline metadata."""

    def test_receive_outline_fast_message(self):
        """Parse outline fast message: metadata in headers."""
        carrier = StubPubSubCarrier()
        content = b"raw binary data"
        headers = {
            "rpsd-who": "sender1",
            "rpsd-what": "report",
            "rpsd-content-type": "application/octet-stream",
        }

        msg = carrier.receive(content, headers)

        assert msg.who == "sender1"
        assert msg.what == "report"
        assert msg.content == content
        assert msg.is_slimfast is True

    def test_receive_outline_heavy_message(self):
        """Parse outline heavy message: where in headers."""
        carrier = StubPubSubCarrier()
        headers = {
            "rpsd-who": "sender1",
            "rpsd-what": "report",
            "rpsd-where": "https://storage.example.com/f.xml",
            "rpsd-content-type": "application/xml",
        }

        msg = carrier.receive(b"", headers)

        assert msg.is_fatheavy is True
        assert msg.where == "https://storage.example.com/f.xml"
        assert msg.content is None

    def test_receive_outline_with_filename(self):
        """Parse outline message with filename header."""
        carrier = StubPubSubCarrier()
        headers = {
            "rpsd-who": "sender1",
            "rpsd-what": "report",
            "rpsd-content-type": "text/csv",
            "rpsd-filename": "data.csv",
        }

        msg = carrier.receive(b"col1,col2\n1,2", headers)

        assert msg.metadata.filename == "data.csv"
        assert msg.metadata.content_type == "text/csv"

    def test_receive_outline_missing_headers_raises(self):
        """Non-JSON message without headers raises ValueError."""
        carrier = StubPubSubCarrier()

        with pytest.raises(ValueError, match="no headers provided"):
            carrier.receive(b"\x00\x01binary")

    def test_receive_outline_missing_who_raises(self):
        """Headers missing 'who' raises ValueError."""
        carrier = StubPubSubCarrier()
        headers = {"rpsd-what": "report"}

        with pytest.raises(ValueError, match="requires 'who' and 'what'"):
            carrier.receive(b"data", headers)

    def test_receive_outline_missing_what_raises(self):
        """Headers missing 'what' raises ValueError."""
        carrier = StubPubSubCarrier()
        headers = {"rpsd-who": "sender1"}

        with pytest.raises(ValueError, match="requires 'who' and 'what'"):
            carrier.receive(b"data", headers)

    def test_receive_outline_short_header_names(self):
        """Accept short header names (who/what) as fallback."""
        carrier = StubPubSubCarrier()
        headers = {
            "who": "sender1",
            "what": "report",
        }

        msg = carrier.receive(b"data", headers)

        assert msg.who == "sender1"
        assert msg.what == "report"


# =============================================================================
# PubSubCarrier.received() hook
# =============================================================================


class TestPubSubReceivedHook:
    """Test that receive() calls the received() hook."""

    def test_received_hook_called(self):
        """receive() calls received() after parsing."""
        carrier = StubPubSubCarrier()
        carrier.received = MagicMock()

        payload = {
            "metadata": {
                "who": "sender1",
                "what": "report",
            },
            "content": base64.b64encode(b"test").decode("utf-8"),
        }
        raw = json.dumps(payload).encode("utf-8")

        msg = carrier.receive(raw)

        carrier.received.assert_called_once_with(msg)

    def test_received_hook_exception_propagates(self):
        """Exception from received() hook propagates up."""
        carrier = StubPubSubCarrier()
        carrier.received = MagicMock(side_effect=RuntimeError("rejected"))

        payload = {
            "metadata": {
                "who": "sender1",
                "what": "report",
            },
            "content": base64.b64encode(b"test").decode("utf-8"),
        }
        raw = json.dumps(payload).encode("utf-8")

        with pytest.raises(RuntimeError, match="rejected"):
            carrier.receive(raw)


# =============================================================================
# PubSubCarrier helper methods
# =============================================================================


class TestPubSubHelpers:
    """Test static helper methods on PubSubCarrier."""

    def test_build_inline_payload_fast(self):
        """Build inline JSON payload for fast message."""
        payload_bytes = PubSubCarrier._build_inline_payload(
            who="sender1",
            what="report",
            content=b"hello",
            content_type="text/plain",
        )
        parsed = json.loads(payload_bytes)

        assert parsed["metadata"]["who"] == "sender1"
        assert parsed["metadata"]["what"] == "report"
        assert parsed["metadata"]["content_type"] == "text/plain"
        assert base64.b64decode(parsed["content"]) == b"hello"

    def test_build_inline_payload_heavy(self):
        """Build inline JSON payload for heavy message."""
        payload_bytes = PubSubCarrier._build_inline_payload(
            who="sender1",
            what="report",
            content=b"",
            content_type="application/xml",
            where="https://storage.example.com/file.xml",
        )
        parsed = json.loads(payload_bytes)

        assert parsed["metadata"]["where"] == "https://storage.example.com/file.xml"
        assert parsed["content"] is None

    def test_build_inline_payload_with_filename(self):
        """Build inline JSON payload includes filename."""
        payload_bytes = PubSubCarrier._build_inline_payload(
            who="sender1",
            what="report",
            content=b"data",
            content_type="text/csv",
            filename="data.csv",
        )
        parsed = json.loads(payload_bytes)

        assert parsed["metadata"]["filename"] == "data.csv"

    def test_build_outline_headers_fast(self):
        """Build outline headers for fast message."""
        headers = PubSubCarrier._build_outline_headers(
            who="sender1",
            what="report",
            content_type="text/plain",
        )

        assert headers["rpsd-who"] == "sender1"
        assert headers["rpsd-what"] == "report"
        assert headers["rpsd-content-type"] == "text/plain"
        assert "rpsd-where" not in headers

    def test_build_outline_headers_heavy(self):
        """Build outline headers for heavy message."""
        headers = PubSubCarrier._build_outline_headers(
            who="sender1",
            what="report",
            content_type="application/xml",
            where="https://storage.example.com/file.xml",
        )

        assert headers["rpsd-where"] == "https://storage.example.com/file.xml"

    def test_build_outline_headers_with_filename(self):
        """Build outline headers includes filename."""
        headers = PubSubCarrier._build_outline_headers(
            who="sender1",
            what="report",
            content_type="text/csv",
            filename="data.csv",
        )

        assert headers["rpsd-filename"] == "data.csv"


# =============================================================================
# KafkaCarrierOptions
# =============================================================================


class TestKafkaCarrierOptions:
    """Test KafkaCarrierOptions model."""

    def test_defaults(self):
        """Default options: inline metadata, no partition/key."""
        opts = KafkaCarrierOptions()

        assert opts.metadata_use_inline is True
        assert opts.partition is None
        assert opts.key is None

    def test_custom_values(self):
        """Custom options for partition and key."""
        opts = KafkaCarrierOptions(
            metadata_use_inline=False,
            partition=3,
            key="my-key",
        )

        assert opts.metadata_use_inline is False
        assert opts.partition == 3
        assert opts.key == "my-key"


# =============================================================================
# KafkaPubSubCarrier — send_slimfast_async
# =============================================================================


class TestKafkaSendSlimfastAsync:
    """Test KafkaPubSubCarrier.send_slimfast_async()."""

    @pytest.fixture
    def kafka_carrier(self):
        """Create KafkaPubSubCarrier with mocked producer."""
        with patch.dict("sys.modules", {"aiokafka": MagicMock()}):
            carrier = KafkaPubSubCarrier(
                bootstrap_servers="localhost:9092",
                group_id="test-group",
            )
        # Mock the producer
        carrier._producer = AsyncMock()
        carrier._producer.send_and_wait = AsyncMock(
            return_value=SimpleNamespace(
                topic="test-topic",
                partition=0,
                offset=42,
            )
        )
        return carrier

    @pytest.mark.anyio
    async def test_send_inline(self, kafka_carrier):
        """Send fast message with inline metadata (default)."""
        result = await kafka_carrier.send_slimfast_async(
            recipient="test-topic",
            who="sender1",
            what="report",
            content=b"hello world",
            content_type="text/plain",
        )

        assert result["status"] == "published"
        assert result["topic"] == "test-topic"
        assert result["partition"] == 0
        assert result["offset"] == 42

        # Verify producer was called with inline JSON
        call_args = kafka_carrier._producer.send_and_wait.call_args
        assert call_args.kwargs["topic"] == "test-topic"
        value = call_args.kwargs["value"]
        parsed = json.loads(value)
        assert parsed["metadata"]["who"] == "sender1"
        assert parsed["metadata"]["what"] == "report"
        assert call_args.kwargs["headers"] is None

    @pytest.mark.anyio
    async def test_send_outline(self, kafka_carrier):
        """Send fast message with outline metadata (headers)."""
        result = await kafka_carrier.send_slimfast_async(
            recipient="test-topic",
            who="sender1",
            what="report",
            content=b"hello world",
            options=KafkaCarrierOptions(metadata_use_inline=False),
        )

        assert result["status"] == "published"

        # Verify producer was called with raw content + headers
        call_args = kafka_carrier._producer.send_and_wait.call_args
        assert call_args.kwargs["value"] == b"hello world"
        headers = dict(call_args.kwargs["headers"])
        assert headers["rpsd-who"] == b"sender1"
        assert headers["rpsd-what"] == b"report"

    @pytest.mark.anyio
    async def test_send_with_key_and_partition(self, kafka_carrier):
        """Send with explicit key and partition."""
        await kafka_carrier.send_slimfast_async(
            recipient="test-topic",
            who="sender1",
            what="report",
            content=b"data",
            options=KafkaCarrierOptions(
                partition=2,
                key="my-key",
            ),
        )

        call_args = kafka_carrier._producer.send_and_wait.call_args
        assert call_args.kwargs["key"] == b"my-key"
        assert call_args.kwargs["partition"] == 2

    @pytest.mark.anyio
    async def test_send_with_filename(self, kafka_carrier):
        """Send inline message includes filename in metadata."""
        await kafka_carrier.send_slimfast_async(
            recipient="test-topic",
            who="sender1",
            what="report",
            content=b"csv data",
            content_type="text/csv",
            filename="data.csv",
        )

        call_args = kafka_carrier._producer.send_and_wait.call_args
        parsed = json.loads(call_args.kwargs["value"])
        assert parsed["metadata"]["filename"] == "data.csv"

    @pytest.mark.anyio
    async def test_send_producer_not_started(self):
        """Raise RuntimeError if producer not started."""
        with patch.dict("sys.modules", {"aiokafka": MagicMock()}):
            carrier = KafkaPubSubCarrier()
        # _producer is None by default

        with pytest.raises(RuntimeError, match="Producer not started"):
            await carrier.send_slimfast_async(
                recipient="topic",
                who="sender1",
                what="report",
                content=b"data",
            )


# =============================================================================
# KafkaPubSubCarrier — send_fatheavy_async
# =============================================================================


class TestKafkaSendFatheavyAsync:
    """Test KafkaPubSubCarrier.send_fatheavy_async()."""

    @pytest.fixture
    def kafka_carrier(self):
        """Create KafkaPubSubCarrier with mocked producer."""
        with patch.dict("sys.modules", {"aiokafka": MagicMock()}):
            carrier = KafkaPubSubCarrier(
                bootstrap_servers="localhost:9092",
            )
        carrier._producer = AsyncMock()
        carrier._producer.send_and_wait = AsyncMock(
            return_value=SimpleNamespace(
                topic="test-topic",
                partition=0,
                offset=99,
            )
        )
        return carrier

    @pytest.mark.anyio
    async def test_send_heavy_inline(self, kafka_carrier):
        """Send heavy message with inline metadata."""
        result = await kafka_carrier.send_fatheavy_async(
            recipient="test-topic",
            who="sender1",
            what="report",
            content=None,
            where="https://storage.example.com/file.xml",
        )

        assert result["status"] == "published"
        assert result["offset"] == 99

        call_args = kafka_carrier._producer.send_and_wait.call_args
        parsed = json.loads(call_args.kwargs["value"])
        assert parsed["metadata"]["where"] == "https://storage.example.com/file.xml"
        assert parsed["content"] is None

    @pytest.mark.anyio
    async def test_send_heavy_outline(self, kafka_carrier):
        """Send heavy message with outline metadata."""
        await kafka_carrier.send_fatheavy_async(
            recipient="test-topic",
            who="sender1",
            what="report",
            content=None,
            where="https://storage.example.com/file.xml",
            options=KafkaCarrierOptions(metadata_use_inline=False),
        )

        call_args = kafka_carrier._producer.send_and_wait.call_args
        assert call_args.kwargs["value"] == b""
        headers = dict(call_args.kwargs["headers"])
        assert headers["rpsd-who"] == b"sender1"
        assert headers["rpsd-where"] == b"https://storage.example.com/file.xml"

    @pytest.mark.anyio
    async def test_send_heavy_no_content_no_where_raises(self, kafka_carrier):
        """Raise ValueError if neither content nor where."""
        with pytest.raises(ValueError, match="Must provide either"):
            await kafka_carrier.send_fatheavy_async(
                recipient="topic",
                who="sender1",
                what="report",
                content=None,
                where=None,
            )

    @pytest.mark.anyio
    async def test_send_heavy_content_without_where_raises(self, kafka_carrier):
        """Raise NotImplementedError for content without where."""
        with pytest.raises(NotImplementedError, match="not yet implemented"):
            await kafka_carrier.send_fatheavy_async(
                recipient="topic",
                who="sender1",
                what="report",
                content=b"data",
                where=None,
            )

    @pytest.mark.anyio
    async def test_send_heavy_producer_not_started(self):
        """Raise RuntimeError if producer not started."""
        with patch.dict("sys.modules", {"aiokafka": MagicMock()}):
            carrier = KafkaPubSubCarrier()

        with pytest.raises(RuntimeError, match="Producer not started"):
            await carrier.send_fatheavy_async(
                recipient="topic",
                who="sender1",
                what="report",
                content=None,
                where="https://example.com/file",
            )


# =============================================================================
# KafkaPubSubCarrier — consume()
# =============================================================================


class TestKafkaConsume:
    """Test KafkaPubSubCarrier.consume() async iterator."""

    @pytest.mark.anyio
    async def test_consume_inline_messages(self):
        """Consume yields parsed inline messages."""
        mock_aiokafka = MagicMock()

        with patch.dict("sys.modules", {"aiokafka": mock_aiokafka}):
            carrier = KafkaPubSubCarrier(
                bootstrap_servers="localhost:9092",
                group_id="test-group",
            )

        # Build a fake inline Kafka message
        payload = {
            "metadata": {
                "who": "sender1",
                "what": "report",
            },
            "content": base64.b64encode(b"data").decode("utf-8"),
        }
        fake_msg = SimpleNamespace(
            value=json.dumps(payload).encode("utf-8"),
            headers=None,
            topic="test-topic",
            partition=0,
            offset=42,
        )

        # Mock the consumer as an async iterator
        mock_consumer = AsyncMock()
        mock_consumer.start = AsyncMock()
        mock_consumer.stop = AsyncMock()
        mock_consumer.__aiter__ = MagicMock(return_value=self._async_iter([fake_msg]))
        mock_aiokafka.AIOKafkaConsumer = MagicMock(return_value=mock_consumer)

        with patch.dict("sys.modules", {"aiokafka": mock_aiokafka}):
            messages = []
            async for msg in carrier.consume("test-topic"):
                messages.append(msg)

        assert len(messages) == 1
        assert messages[0].who == "sender1"
        assert messages[0].what == "report"
        assert messages[0].content == b"data"

        mock_consumer.start.assert_awaited_once()
        mock_consumer.stop.assert_awaited_once()

    @pytest.mark.anyio
    async def test_consume_outline_messages(self):
        """Consume yields parsed outline messages."""
        mock_aiokafka = MagicMock()

        with patch.dict("sys.modules", {"aiokafka": mock_aiokafka}):
            carrier = KafkaPubSubCarrier(
                bootstrap_servers="localhost:9092",
                group_id="test-group",
            )

        fake_msg = SimpleNamespace(
            value=b"raw content bytes",
            headers=[
                ("rpsd-who", b"sender1"),
                ("rpsd-what", b"report"),
                (
                    "rpsd-content-type",
                    b"application/octet-stream",
                ),
            ],
            topic="test-topic",
            partition=0,
            offset=10,
        )

        mock_consumer = AsyncMock()
        mock_consumer.start = AsyncMock()
        mock_consumer.stop = AsyncMock()
        mock_consumer.__aiter__ = MagicMock(return_value=self._async_iter([fake_msg]))
        mock_aiokafka.AIOKafkaConsumer = MagicMock(return_value=mock_consumer)

        with patch.dict("sys.modules", {"aiokafka": mock_aiokafka}):
            messages = []
            async for msg in carrier.consume("test-topic"):
                messages.append(msg)

        assert len(messages) == 1
        assert messages[0].who == "sender1"
        assert messages[0].content == b"raw content bytes"

    @pytest.mark.anyio
    async def test_consume_requires_group_id(self):
        """consume() raises if group_id not set."""
        mock_aiokafka = MagicMock()

        with patch.dict("sys.modules", {"aiokafka": mock_aiokafka}):
            carrier = KafkaPubSubCarrier(
                bootstrap_servers="localhost:9092",
                group_id=None,
            )

            with pytest.raises(RuntimeError, match="group_id is required"):
                async for _ in carrier.consume("test-topic"):
                    pass  # pragma: no cover

    @pytest.mark.anyio
    async def test_consume_stops_consumer_on_exception(self):
        """Consumer is stopped even if processing raises."""
        mock_aiokafka = MagicMock()

        with patch.dict("sys.modules", {"aiokafka": mock_aiokafka}):
            carrier = KafkaPubSubCarrier(
                bootstrap_servers="localhost:9092",
                group_id="test-group",
            )

        # A message that will cause a parsing error
        fake_msg = SimpleNamespace(
            value=b"not json",
            headers=None,  # No headers -> will fail outline
            topic="test-topic",
            partition=0,
            offset=0,
        )

        mock_consumer = AsyncMock()
        mock_consumer.start = AsyncMock()
        mock_consumer.stop = AsyncMock()
        mock_consumer.__aiter__ = MagicMock(return_value=self._async_iter([fake_msg]))
        mock_aiokafka.AIOKafkaConsumer = MagicMock(return_value=mock_consumer)

        with patch.dict("sys.modules", {"aiokafka": mock_aiokafka}):
            with pytest.raises(ValueError):
                async for _ in carrier.consume("test-topic"):
                    pass  # pragma: no cover

        # Consumer should still be stopped via finally block
        mock_consumer.stop.assert_awaited_once()

    @pytest.mark.anyio
    async def test_consume_uses_manual_commit(self):
        """Consumer is created with enable_auto_commit=False."""
        mock_aiokafka = MagicMock()

        with patch.dict("sys.modules", {"aiokafka": mock_aiokafka}):
            carrier = KafkaPubSubCarrier(
                bootstrap_servers="localhost:9092",
                group_id="test-group",
            )

        payload = {
            "metadata": {
                "who": "sender1",
                "what": "report",
            },
            "content": base64.b64encode(b"data").decode("utf-8"),
        }
        fake_msg = SimpleNamespace(
            value=json.dumps(payload).encode("utf-8"),
            headers=None,
            topic="test-topic",
            partition=0,
            offset=0,
        )

        mock_consumer = AsyncMock()
        mock_consumer.start = AsyncMock()
        mock_consumer.stop = AsyncMock()
        mock_consumer.__aiter__ = MagicMock(return_value=self._async_iter([fake_msg]))
        mock_aiokafka.AIOKafkaConsumer = MagicMock(return_value=mock_consumer)

        with patch.dict("sys.modules", {"aiokafka": mock_aiokafka}):
            async for _ in carrier.consume("test-topic"):
                pass

        # Verify enable_auto_commit=False was passed
        call_kwargs = mock_aiokafka.AIOKafkaConsumer.call_args.kwargs
        assert call_kwargs["enable_auto_commit"] is False

    @pytest.mark.anyio
    async def test_consume_sets_ack_nack(self):
        """Consumed messages have ack/nack functions set."""
        mock_aiokafka = MagicMock()

        with patch.dict("sys.modules", {"aiokafka": mock_aiokafka}):
            carrier = KafkaPubSubCarrier(
                bootstrap_servers="localhost:9092",
                group_id="test-group",
            )

        payload = {
            "metadata": {
                "who": "sender1",
                "what": "report",
            },
            "content": base64.b64encode(b"data").decode("utf-8"),
        }
        fake_msg = SimpleNamespace(
            value=json.dumps(payload).encode("utf-8"),
            headers=None,
            topic="test-topic",
            partition=0,
            offset=5,
        )

        mock_consumer = AsyncMock()
        mock_consumer.start = AsyncMock()
        mock_consumer.stop = AsyncMock()
        mock_consumer.commit = AsyncMock()
        mock_consumer.seek = MagicMock()
        mock_consumer.__aiter__ = MagicMock(return_value=self._async_iter([fake_msg]))
        mock_aiokafka.AIOKafkaConsumer = MagicMock(return_value=mock_consumer)

        with patch.dict("sys.modules", {"aiokafka": mock_aiokafka}):
            async for msg in carrier.consume("test-topic"):
                # ack/nack should be set
                assert msg._ack_fn is not None
                assert msg._nack_fn is not None

                # Test ack commits offset + 1
                await msg.ack()
                mock_consumer.commit.assert_awaited_once()

                # Test nack with requeue seeks back
                await msg.nack(requeue=True)
                mock_consumer.seek.assert_called_once()

    @staticmethod
    async def _async_iter(items):
        """Helper to create an async iterator from a list."""
        for item in items:
            yield item


# =============================================================================
# KafkaPubSubCarrier — start/stop lifecycle
# =============================================================================


class TestKafkaLifecycle:
    """Test KafkaPubSubCarrier start/stop lifecycle."""

    @pytest.mark.anyio
    async def test_start_creates_producer(self):
        """start() creates and starts an aiokafka producer."""
        mock_producer = AsyncMock()
        mock_producer.start = AsyncMock()

        mock_aiokafka = MagicMock()
        mock_aiokafka.AIOKafkaProducer = MagicMock(return_value=mock_producer)

        with patch.dict("sys.modules", {"aiokafka": mock_aiokafka}):
            carrier = KafkaPubSubCarrier(
                bootstrap_servers="broker:9092",
                client_id="test-client",
            )
            await carrier.start()

        assert carrier._producer is mock_producer
        mock_producer.start.assert_awaited_once()

    @pytest.mark.anyio
    async def test_stop_stops_producer(self):
        """stop() stops the producer and sets it to None."""
        mock_producer = AsyncMock()
        mock_producer.stop = AsyncMock()

        with patch.dict("sys.modules", {"aiokafka": MagicMock()}):
            carrier = KafkaPubSubCarrier()

        carrier._producer = mock_producer
        await carrier.stop()

        assert carrier._producer is None
        mock_producer.stop.assert_awaited_once()

    @pytest.mark.anyio
    async def test_stop_noop_when_not_started(self):
        """stop() is a no-op when producer is None."""
        with patch.dict("sys.modules", {"aiokafka": MagicMock()}):
            carrier = KafkaPubSubCarrier()

        await carrier.stop()  # Should not raise

    @pytest.mark.anyio
    async def test_start_idempotent(self):
        """Calling start() twice does not create a second producer."""
        mock_producer = AsyncMock()
        mock_producer.start = AsyncMock()

        mock_aiokafka = MagicMock()
        mock_aiokafka.AIOKafkaProducer = MagicMock(return_value=mock_producer)

        with patch.dict("sys.modules", {"aiokafka": mock_aiokafka}):
            carrier = KafkaPubSubCarrier()
            await carrier.start()
            await carrier.start()  # Second call

        # Producer constructor should be called only once
        mock_aiokafka.AIOKafkaProducer.assert_called_once()


# =============================================================================
# KafkaPubSubCarrier — import guard
# =============================================================================


class TestKafkaImportGuard:
    """Test that KafkaPubSubCarrier gives clear import error."""

    def test_missing_aiokafka_raises(self):
        """ImportError with install instructions if aiokafka missing."""
        with patch.dict("sys.modules", {"aiokafka": None}):
            with pytest.raises(ImportError, match="uv add rpsd-transport"):
                KafkaPubSubCarrier()

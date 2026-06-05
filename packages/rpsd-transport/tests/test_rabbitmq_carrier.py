# SPDX-License-Identifier: BSD-3-Clause
# SPDX-FileCopyrightText: 2026 AGENZIA TPL BACINO CITTA' METROPOLITANA MILANO,
# MONZA E BRIANZA, LODI, PAVIA
"""
Tests for RabbitMQPubSubCarrier.

RabbitMQ send/consume methods use mocked aio_pika.
Follows the same pattern as test_pubsub_carrier.py for Kafka.
"""

import base64
import json
from unittest.mock import (
    AsyncMock,
    MagicMock,
    patch,
)

import pytest

from rpsd_transport.carriers.pubsub.rabbitmq import (
    RabbitMQCarrierOptions,
    RabbitMQPubSubCarrier,
)


@pytest.fixture
def anyio_backend():
    """Use asyncio backend only (trio not installed)."""
    return "asyncio"


def _make_mock_aio_pika():
    """Create a mock aio_pika module with common types."""
    mock_mod = MagicMock()

    # DeliveryMode enum
    mock_mod.DeliveryMode.PERSISTENT = 2

    # ExchangeType enum
    mock_mod.ExchangeType = MagicMock(side_effect=lambda x: x)

    # Message class
    mock_mod.Message = MagicMock()

    # connect_robust returns a mock connection
    mock_connection = AsyncMock()
    mock_channel = AsyncMock()
    mock_exchange = AsyncMock()

    mock_channel.default_exchange = mock_exchange
    mock_channel.set_qos = AsyncMock()
    mock_channel.declare_exchange = AsyncMock(return_value=mock_exchange)
    mock_connection.channel = AsyncMock(return_value=mock_channel)
    mock_connection.close = AsyncMock()
    mock_mod.connect_robust = AsyncMock(return_value=mock_connection)

    return mock_mod, mock_connection, mock_channel, mock_exchange


# =============================================================================
# RabbitMQCarrierOptions
# =============================================================================


class TestRabbitMQCarrierOptions:
    """Test RabbitMQCarrierOptions model."""

    def test_defaults(self):
        """Default options: inline metadata, no routing_key."""
        opts = RabbitMQCarrierOptions()

        assert opts.metadata_use_inline is True
        assert opts.routing_key is None
        assert opts.priority is None

    def test_custom_values(self):
        """Custom options for routing_key and priority."""
        opts = RabbitMQCarrierOptions(
            metadata_use_inline=False,
            routing_key="my.routing.key",
            priority=5,
        )

        assert opts.metadata_use_inline is False
        assert opts.routing_key == "my.routing.key"
        assert opts.priority == 5


# =============================================================================
# RabbitMQPubSubCarrier — send_slimfast_async
# =============================================================================


class TestRabbitMQSendSlimfastAsync:
    """Test RabbitMQPubSubCarrier.send_slimfast_async()."""

    @pytest.fixture
    def rabbitmq_carrier(self):
        """Create carrier with mocked exchange."""
        mock_mod = MagicMock()
        mock_mod.DeliveryMode.PERSISTENT = 2
        mock_mod.Message = MagicMock()

        with patch.dict("sys.modules", {"aio_pika": mock_mod}):
            carrier = RabbitMQPubSubCarrier(
                url="amqp://guest:guest@localhost/",
            )

        mock_exchange = AsyncMock()
        mock_exchange.publish = AsyncMock()
        carrier._exchange = mock_exchange
        carrier._connection = MagicMock()
        carrier._aio_pika_mod = mock_mod
        return carrier, mock_mod

    @pytest.mark.anyio
    async def test_send_inline(self, rabbitmq_carrier):
        """Send fast message with inline metadata."""
        carrier, mock_mod = rabbitmq_carrier

        with patch.dict("sys.modules", {"aio_pika": mock_mod}):
            result = await carrier.send_slimfast_async(
                recipient="my-queue",
                who="sender1",
                what="report",
                content=b"hello world",
                content_type="text/plain",
            )

        assert result["status"] == "published"
        assert result["routing_key"] == "my-queue"

        # Verify Message was created
        mock_mod.Message.assert_called_once()
        call_kwargs = mock_mod.Message.call_args.kwargs
        body = call_kwargs["body"]
        parsed = json.loads(body)
        assert parsed["metadata"]["who"] == "sender1"
        assert parsed["metadata"]["what"] == "report"
        assert call_kwargs["headers"] is None

        # Verify publish was called with timeout
        carrier._exchange.publish.assert_awaited_once()
        pub_kwargs = carrier._exchange.publish.call_args.kwargs
        assert pub_kwargs["timeout"] == 30

    @pytest.mark.anyio
    async def test_send_outline(self, rabbitmq_carrier):
        """Send fast message with outline metadata."""
        carrier, mock_mod = rabbitmq_carrier

        with patch.dict("sys.modules", {"aio_pika": mock_mod}):
            result = await carrier.send_slimfast_async(
                recipient="my-queue",
                who="sender1",
                what="report",
                content=b"hello world",
                options=RabbitMQCarrierOptions(metadata_use_inline=False),
            )

        assert result["status"] == "published"

        call_kwargs = mock_mod.Message.call_args.kwargs
        assert call_kwargs["body"] == b"hello world"
        headers = call_kwargs["headers"]
        assert headers["rpsd-who"] == "sender1"
        assert headers["rpsd-what"] == "report"

    @pytest.mark.anyio
    async def test_send_with_routing_key(self, rabbitmq_carrier):
        """Send with explicit routing key from options."""
        carrier, mock_mod = rabbitmq_carrier

        with patch.dict("sys.modules", {"aio_pika": mock_mod}):
            result = await carrier.send_slimfast_async(
                recipient="my-queue",
                who="sender1",
                what="report",
                content=b"data",
                options=RabbitMQCarrierOptions(
                    routing_key="custom.route",
                ),
            )

        assert result["routing_key"] == "custom.route"
        publish_kwargs = carrier._exchange.publish.call_args.kwargs
        assert publish_kwargs["routing_key"] == "custom.route"

    @pytest.mark.anyio
    async def test_send_with_priority(self, rabbitmq_carrier):
        """Send with message priority."""
        carrier, mock_mod = rabbitmq_carrier

        with patch.dict("sys.modules", {"aio_pika": mock_mod}):
            await carrier.send_slimfast_async(
                recipient="my-queue",
                who="sender1",
                what="report",
                content=b"data",
                options=RabbitMQCarrierOptions(priority=5),
            )

        call_kwargs = mock_mod.Message.call_args.kwargs
        assert call_kwargs["priority"] == 5

    @pytest.mark.anyio
    async def test_send_not_started_raises(self):
        """Raise RuntimeError if connection not started."""
        with patch.dict("sys.modules", {"aio_pika": MagicMock()}):
            carrier = RabbitMQPubSubCarrier()

            with pytest.raises(RuntimeError, match="Connection not started"):
                await carrier.send_slimfast_async(
                    recipient="queue",
                    who="sender1",
                    what="report",
                    content=b"data",
                )


# =============================================================================
# RabbitMQPubSubCarrier — send_fatheavy_async
# =============================================================================


class TestRabbitMQSendFatheavyAsync:
    """Test RabbitMQPubSubCarrier.send_fatheavy_async()."""

    @pytest.fixture
    def rabbitmq_carrier(self):
        """Create carrier with mocked exchange."""
        mock_mod = MagicMock()
        mock_mod.DeliveryMode.PERSISTENT = 2
        mock_mod.Message = MagicMock()

        with patch.dict("sys.modules", {"aio_pika": mock_mod}):
            carrier = RabbitMQPubSubCarrier()

        mock_exchange = AsyncMock()
        mock_exchange.publish = AsyncMock()
        carrier._exchange = mock_exchange
        carrier._connection = MagicMock()
        return carrier, mock_mod

    @pytest.mark.anyio
    async def test_send_heavy_inline(self, rabbitmq_carrier):
        """Send heavy message with inline metadata."""
        carrier, mock_mod = rabbitmq_carrier

        with patch.dict("sys.modules", {"aio_pika": mock_mod}):
            result = await carrier.send_fatheavy_async(
                recipient="my-queue",
                who="sender1",
                what="report",
                content=None,
                where="https://storage.example.com/f.xml",
            )

        assert result["status"] == "published"

        call_kwargs = mock_mod.Message.call_args.kwargs
        parsed = json.loads(call_kwargs["body"])
        assert parsed["metadata"]["where"] == "https://storage.example.com/f.xml"
        assert parsed["content"] is None

    @pytest.mark.anyio
    async def test_send_heavy_no_content_no_where_raises(self, rabbitmq_carrier):
        """Raise ValueError if neither content nor where."""
        carrier, mock_mod = rabbitmq_carrier

        with patch.dict("sys.modules", {"aio_pika": mock_mod}):
            with pytest.raises(ValueError, match="Must provide either"):
                await carrier.send_fatheavy_async(
                    recipient="queue",
                    who="sender1",
                    what="report",
                    content=None,
                    where=None,
                )

    @pytest.mark.anyio
    async def test_send_heavy_content_without_where_raises(self, rabbitmq_carrier):
        """Raise NotImplementedError for content without where."""
        carrier, mock_mod = rabbitmq_carrier

        with patch.dict("sys.modules", {"aio_pika": mock_mod}):
            with pytest.raises(
                NotImplementedError,
                match="not yet implemented",
            ):
                await carrier.send_fatheavy_async(
                    recipient="queue",
                    who="sender1",
                    what="report",
                    content=b"data",
                    where=None,
                )

    @pytest.mark.anyio
    async def test_send_heavy_not_started_raises(self):
        """Raise RuntimeError if connection not started."""
        with patch.dict("sys.modules", {"aio_pika": MagicMock()}):
            carrier = RabbitMQPubSubCarrier()

            with pytest.raises(RuntimeError, match="Connection not started"):
                await carrier.send_fatheavy_async(
                    recipient="queue",
                    who="sender1",
                    what="report",
                    content=None,
                    where="https://example.com/file",
                )


# =============================================================================
# RabbitMQPubSubCarrier — consume()
# =============================================================================


class TestRabbitMQConsume:
    """Test RabbitMQPubSubCarrier.consume() async iterator."""

    @staticmethod
    async def _async_iter(items):
        """Helper to create an async iterator from a list."""
        for item in items:
            yield item

    def _make_fake_amqp_msg(self, body, headers=None):
        """Create a fake aio_pika.IncomingMessage."""
        msg = AsyncMock()
        msg.body = body
        msg.headers = headers
        msg.ack = AsyncMock()
        msg.nack = AsyncMock()
        return msg

    @pytest.mark.anyio
    async def test_consume_inline_messages(self):
        """Consume yields parsed inline messages."""
        (
            mock_mod,
            mock_conn,
            mock_channel,
            mock_exchange,
        ) = _make_mock_aio_pika()

        with patch.dict("sys.modules", {"aio_pika": mock_mod}):
            carrier = RabbitMQPubSubCarrier(
                url="amqp://localhost/",
            )

        # Build a fake inline message
        payload = {
            "metadata": {
                "who": "sender1",
                "what": "report",
            },
            "content": base64.b64encode(b"data").decode("utf-8"),
        }
        fake_msg = self._make_fake_amqp_msg(
            body=json.dumps(payload).encode("utf-8"),
        )

        # Mock queue with iterator
        mock_queue = AsyncMock()
        mock_queue_iter = AsyncMock()
        mock_queue_iter.__aenter__ = AsyncMock(
            return_value=self._async_iter([fake_msg])
        )
        mock_queue_iter.__aexit__ = AsyncMock(return_value=False)
        mock_queue.iterator = MagicMock(return_value=mock_queue_iter)
        mock_channel.declare_queue = AsyncMock(return_value=mock_queue)

        # Inject mocked connection/channel
        carrier._connection = mock_conn
        carrier._channel = mock_channel
        carrier._exchange = mock_exchange

        with patch.dict("sys.modules", {"aio_pika": mock_mod}):
            messages = []
            async for msg in carrier.consume("tasks"):
                messages.append(msg)

        assert len(messages) == 1
        assert messages[0].who == "sender1"
        assert messages[0].what == "report"
        assert messages[0].content == b"data"

        # Verify queue was declared
        mock_channel.declare_queue.assert_awaited_once_with("tasks", durable=True)

    @pytest.mark.anyio
    async def test_consume_outline_messages(self):
        """Consume yields parsed outline messages."""
        (
            mock_mod,
            mock_conn,
            mock_channel,
            mock_exchange,
        ) = _make_mock_aio_pika()

        with patch.dict("sys.modules", {"aio_pika": mock_mod}):
            carrier = RabbitMQPubSubCarrier()

        fake_msg = self._make_fake_amqp_msg(
            body=b"raw content bytes",
            headers={
                "rpsd-who": "sender1",
                "rpsd-what": "report",
                "rpsd-content-type": "application/octet-stream",
            },
        )

        mock_queue = AsyncMock()
        mock_queue_iter = AsyncMock()
        mock_queue_iter.__aenter__ = AsyncMock(
            return_value=self._async_iter([fake_msg])
        )
        mock_queue_iter.__aexit__ = AsyncMock(return_value=False)
        mock_queue.iterator = MagicMock(return_value=mock_queue_iter)
        mock_channel.declare_queue = AsyncMock(return_value=mock_queue)

        carrier._connection = mock_conn
        carrier._channel = mock_channel
        carrier._exchange = mock_exchange

        with patch.dict("sys.modules", {"aio_pika": mock_mod}):
            messages = []
            async for msg in carrier.consume("tasks"):
                messages.append(msg)

        assert len(messages) == 1
        assert messages[0].who == "sender1"
        assert messages[0].content == b"raw content bytes"

    @pytest.mark.anyio
    async def test_consume_sets_ack_nack(self):
        """Consumed messages have ack/nack bound."""
        (
            mock_mod,
            mock_conn,
            mock_channel,
            mock_exchange,
        ) = _make_mock_aio_pika()

        with patch.dict("sys.modules", {"aio_pika": mock_mod}):
            carrier = RabbitMQPubSubCarrier()

        payload = {
            "metadata": {
                "who": "sender1",
                "what": "report",
            },
            "content": base64.b64encode(b"data").decode("utf-8"),
        }
        fake_msg = self._make_fake_amqp_msg(
            body=json.dumps(payload).encode("utf-8"),
        )

        mock_queue = AsyncMock()
        mock_queue_iter = AsyncMock()
        mock_queue_iter.__aenter__ = AsyncMock(
            return_value=self._async_iter([fake_msg])
        )
        mock_queue_iter.__aexit__ = AsyncMock(return_value=False)
        mock_queue.iterator = MagicMock(return_value=mock_queue_iter)
        mock_channel.declare_queue = AsyncMock(return_value=mock_queue)

        carrier._connection = mock_conn
        carrier._channel = mock_channel
        carrier._exchange = mock_exchange

        with patch.dict("sys.modules", {"aio_pika": mock_mod}):
            async for msg in carrier.consume("tasks"):
                # ack/nack should be set
                assert msg._ack_fn is not None
                assert msg._nack_fn is not None

                # Calling ack delegates to AMQP message
                await msg.ack()
                fake_msg.ack.assert_awaited_once()

                # Calling nack delegates to AMQP message
                await msg.nack(requeue=False)
                fake_msg.nack.assert_awaited_once_with(requeue=False)

    @pytest.mark.anyio
    async def test_consume_auto_starts_if_needed(self):
        """consume() calls start() if not connected."""
        (
            mock_mod,
            mock_conn,
            mock_channel,
            mock_exchange,
        ) = _make_mock_aio_pika()

        with patch.dict("sys.modules", {"aio_pika": mock_mod}):
            carrier = RabbitMQPubSubCarrier()

        payload = {
            "metadata": {
                "who": "sender1",
                "what": "report",
            },
            "content": base64.b64encode(b"data").decode("utf-8"),
        }
        fake_msg = self._make_fake_amqp_msg(
            body=json.dumps(payload).encode("utf-8"),
        )

        mock_queue = AsyncMock()
        mock_queue_iter = AsyncMock()
        mock_queue_iter.__aenter__ = AsyncMock(
            return_value=self._async_iter([fake_msg])
        )
        mock_queue_iter.__aexit__ = AsyncMock(return_value=False)
        mock_queue.iterator = MagicMock(return_value=mock_queue_iter)
        mock_channel.declare_queue = AsyncMock(return_value=mock_queue)

        # carrier._connection is None, so consume()
        # should call start()
        with patch.dict("sys.modules", {"aio_pika": mock_mod}):
            async for _ in carrier.consume("tasks"):
                pass

        # Verify connect_robust was called (via start())
        mock_mod.connect_robust.assert_awaited_once()


# =============================================================================
# RabbitMQPubSubCarrier — start/stop lifecycle
# =============================================================================


class TestRabbitMQLifecycle:
    """Test RabbitMQPubSubCarrier start/stop lifecycle."""

    @pytest.mark.anyio
    async def test_start_creates_connection(self):
        """start() creates connection, channel, and exchange."""
        (
            mock_mod,
            mock_conn,
            mock_channel,
            mock_exchange,
        ) = _make_mock_aio_pika()

        with patch.dict("sys.modules", {"aio_pika": mock_mod}):
            carrier = RabbitMQPubSubCarrier(
                url="amqp://localhost/",
                prefetch_count=20,
            )
            await carrier.start()

        assert carrier._connection is mock_conn
        assert carrier._channel is mock_channel
        mock_mod.connect_robust.assert_awaited_once_with(
            "amqp://localhost/", timeout=30
        )
        mock_channel.set_qos.assert_awaited_once_with(prefetch_count=20)

    @pytest.mark.anyio
    async def test_start_declares_named_exchange(self):
        """start() declares exchange when name is non-empty."""
        (
            mock_mod,
            mock_conn,
            mock_channel,
            mock_exchange,
        ) = _make_mock_aio_pika()

        with patch.dict("sys.modules", {"aio_pika": mock_mod}):
            carrier = RabbitMQPubSubCarrier(
                exchange="my-exchange",
                exchange_type="topic",
            )
            await carrier.start()

        mock_channel.declare_exchange.assert_awaited_once()

    @pytest.mark.anyio
    async def test_start_uses_default_exchange(self):
        """start() uses default exchange when name is empty."""
        (
            mock_mod,
            mock_conn,
            mock_channel,
            mock_exchange,
        ) = _make_mock_aio_pika()

        with patch.dict("sys.modules", {"aio_pika": mock_mod}):
            carrier = RabbitMQPubSubCarrier(exchange="")
            await carrier.start()

        mock_channel.declare_exchange.assert_not_awaited()
        assert carrier._exchange is mock_channel.default_exchange

    @pytest.mark.anyio
    async def test_stop_closes_connection(self):
        """stop() closes connection and resets state."""
        (
            mock_mod,
            mock_conn,
            mock_channel,
            mock_exchange,
        ) = _make_mock_aio_pika()

        with patch.dict("sys.modules", {"aio_pika": mock_mod}):
            carrier = RabbitMQPubSubCarrier()

        carrier._connection = mock_conn
        carrier._channel = mock_channel
        carrier._exchange = mock_exchange

        await carrier.stop()

        assert carrier._connection is None
        assert carrier._channel is None
        assert carrier._exchange is None
        mock_conn.close.assert_awaited_once()

    @pytest.mark.anyio
    async def test_stop_noop_when_not_started(self):
        """stop() is a no-op when connection is None."""
        with patch.dict("sys.modules", {"aio_pika": MagicMock()}):
            carrier = RabbitMQPubSubCarrier()

        await carrier.stop()  # Should not raise

    @pytest.mark.anyio
    async def test_start_idempotent(self):
        """Calling start() twice does not create second connection."""
        (
            mock_mod,
            mock_conn,
            mock_channel,
            mock_exchange,
        ) = _make_mock_aio_pika()

        with patch.dict("sys.modules", {"aio_pika": mock_mod}):
            carrier = RabbitMQPubSubCarrier()
            await carrier.start()
            await carrier.start()  # Second call

        mock_mod.connect_robust.assert_awaited_once()


# =============================================================================
# RabbitMQPubSubCarrier — import guard
# =============================================================================


class TestRabbitMQImportGuard:
    """Test that RabbitMQPubSubCarrier gives clear error."""

    def test_missing_aio_pika_raises(self):
        """ImportError with install instructions."""
        with patch.dict("sys.modules", {"aio_pika": None}):
            with pytest.raises(
                ImportError,
                match="uv add rpsd-transport",
            ):
                RabbitMQPubSubCarrier()

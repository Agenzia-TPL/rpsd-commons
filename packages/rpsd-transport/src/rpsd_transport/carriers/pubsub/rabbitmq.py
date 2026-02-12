"""
RabbitMQ carrier implementation for rpsd-transport.

Requires the 'rabbitmq' optional dependency:
    uv add rpsd-transport[rabbitmq]
"""

import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from rpsd_transport.carriers.base import CarrierOptions
from rpsd_transport.carriers.pubsub.base import PubSubCarrier
from rpsd_transport.models import TransportMessage

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class RabbitMQCarrierOptions(CarrierOptions):
    """RabbitMQ-specific send options.

    Attributes:
        metadata_use_inline: If True, metadata is embedded in
            JSON payload. If False, metadata goes in AMQP
            message headers.
        routing_key: Routing key for exchange publishing.
            If None, the recipient argument is used as the
            routing key.
        priority: Message priority (0-255). None for default.
    """

    routing_key: str | None = None
    priority: int | None = None


class RabbitMQPubSubCarrier(PubSubCarrier):
    """RabbitMQ-based carrier for PubSub transport.

    Uses aio-pika for async AMQP 0.9.1 producer and consumer.
    Manages connection, channel, and exchange internally.
    Auto-declares exchanges and queues on startup/consume.

    Example - Publishing:
        ```python
        carrier = RabbitMQPubSubCarrier(
            url="amqp://guest:guest@localhost/"
        )
        await carrier.start()
        carrier.send_slimfast(
            recipient="my-queue",
            who="sender",
            what="data",
            content=b"hello",
        )
        await carrier.stop()
        ```

    Example - Consuming:
        ```python
        carrier = RabbitMQPubSubCarrier(
            url="amqp://guest:guest@localhost/"
        )
        async for message in carrier.consume("my-queue"):
            await process(message)
            await message.ack()
        ```
    """

    def __init__(
        self,
        url: str = "amqp://guest:guest@localhost/",
        exchange: str = "",
        exchange_type: str = "direct",
        queue_durable: bool = True,
        prefetch_count: int = 10,
    ):
        """Initialize RabbitMQ carrier.

        Args:
            url: AMQP connection URL.
            exchange: Exchange name. Empty string uses the
                default exchange.
            exchange_type: Exchange type (direct, fanout,
                topic, headers).
            queue_durable: Whether declared queues are durable.
            prefetch_count: QoS prefetch count for consumers.
        """
        try:
            import aio_pika  # noqa: F401
        except ImportError:
            raise ImportError(
                "RabbitMQPubSubCarrier requires aio-pika. "
                "Install with: uv add rpsd-transport[rabbitmq]"
            ) from None

        self.url = url
        self.exchange_name = exchange
        self.exchange_type = exchange_type
        self.queue_durable = queue_durable
        self.prefetch_count = prefetch_count
        self._connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._channel: aio_pika.abc.AbstractChannel | None = None
        self._exchange: aio_pika.abc.AbstractExchange | None = None

    async def start(self) -> None:
        """Start the RabbitMQ connection and channel.

        Opens a robust connection, creates a channel with QoS,
        and declares the exchange (if non-default). Must be
        called before send_slimfast/send_fatheavy.
        """
        import aio_pika

        if self._connection is not None:
            return

        self._connection = await aio_pika.connect_robust(self.url)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=self.prefetch_count)

        if self.exchange_name:
            self._exchange = await self._channel.declare_exchange(
                self.exchange_name,
                aio_pika.ExchangeType(self.exchange_type),
                durable=True,
            )
        else:
            self._exchange = self._channel.default_exchange

    async def stop(self) -> None:
        """Stop the RabbitMQ connection."""
        if self._connection is not None:
            await self._connection.close()
            self._connection = None
            self._channel = None
            self._exchange = None

    def send_slimfast(
        self,
        recipient: str,
        who: str,
        what: str,
        content: bytes,
        content_type: str = "application/octet-stream",
        filename: str | None = None,
        custom_metadata: dict[str, Any] | None = None,
        options: RabbitMQCarrierOptions | None = None,
    ) -> dict:
        """Publish a slim/fast message to RabbitMQ.

        Note: This method is sync in the BaseCarrier interface
        but RabbitMQ publishing is async. Use
        send_slimfast_async() for native async.

        Args:
            recipient: Routing key (or queue name for default
                exchange).
            who: Entity identifier.
            what: Content type/category.
            content: Data to send.
            content_type: MIME type of the data.
            filename: Optional original filename.
            custom_metadata: Optional additional metadata.
            options: RabbitMQ-specific options.

        Returns:
            dict: Send result with status and routing info.

        Raises:
            RuntimeError: If connection not started.
        """
        import asyncio

        loop = asyncio.get_event_loop()
        if loop.is_running():
            raise RuntimeError(
                "Cannot call sync send_slimfast from an async "
                "context. Use send_slimfast_async() instead."
            )
        return loop.run_until_complete(
            self.send_slimfast_async(
                recipient=recipient,
                who=who,
                what=what,
                content=content,
                content_type=content_type,
                filename=filename,
                custom_metadata=custom_metadata,
                options=options,
            )
        )

    async def send_slimfast_async(
        self,
        recipient: str,
        who: str,
        what: str,
        content: bytes,
        content_type: str = "application/octet-stream",
        filename: str | None = None,
        custom_metadata: dict[str, Any] | None = None,
        options: RabbitMQCarrierOptions | None = None,
    ) -> dict:
        """Publish a slim/fast message to RabbitMQ (async).

        Args:
            recipient: Routing key (or queue name for default
                exchange).
            who: Entity identifier.
            what: Content type/category.
            content: Data to send.
            content_type: MIME type of the data.
            filename: Optional original filename.
            custom_metadata: Optional additional metadata.
            options: RabbitMQ-specific options.

        Returns:
            dict: Send result with status and routing info.

        Raises:
            RuntimeError: If connection not started.
        """
        import aio_pika

        if options is None:
            options = RabbitMQCarrierOptions()

        if self._exchange is None:
            raise RuntimeError(
                "Connection not started. Call await carrier.start() first."
            )

        routing_key = options.routing_key or recipient

        if options.metadata_use_inline:
            body = self._build_inline_payload(
                who=who,
                what=what,
                content=content,
                content_type=content_type,
                filename=filename,
                custom_metadata=custom_metadata,
            )
            headers: dict[str, Any] | None = None
        else:
            body = content
            headers: dict[str, Any] | None = self._build_outline_headers(
                who=who,
                what=what,
                content_type=content_type,
                filename=filename,
            )

        message = aio_pika.Message(
            body=body,
            headers=headers,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            priority=options.priority,
        )

        await self._exchange.publish(message, routing_key=routing_key)

        logger.info(
            "Published slim/fast message to %s: who=%s, what=%s, exchange=%s",
            routing_key,
            who,
            what,
            self.exchange_name or "(default)",
        )

        return {
            "status": "published",
            "exchange": self.exchange_name or "(default)",
            "routing_key": routing_key,
        }

    def send_fatheavy(
        self,
        recipient: str,
        who: str,
        what: str,
        content: bytes | None,
        content_type: str = "application/octet-stream",
        filename: str | None = None,
        custom_metadata: dict[str, Any] | None = None,
        options: RabbitMQCarrierOptions | None = None,
        where: str | None = None,
        expose_ttl: int = 3600,
    ) -> dict:
        """Publish a fat/heavy message to RabbitMQ.

        Note: This method is sync in the BaseCarrier interface
        but RabbitMQ publishing is async. Use
        send_fatheavy_async() for native async.

        Args:
            recipient: Routing key (or queue name for default
                exchange).
            who: Entity identifier.
            what: Content type/category.
            content: New data to save or None.
            content_type: MIME type of the data.
            filename: Optional original filename.
            custom_metadata: Optional additional metadata.
            options: RabbitMQ-specific options.
            where: URL where content is available.
            expose_ttl: Time-to-live for exposed URL.

        Returns:
            dict: Send result with status and routing info.

        Raises:
            ValueError: If neither content nor where provided.
            RuntimeError: If connection not started.
        """
        import asyncio

        loop = asyncio.get_event_loop()
        if loop.is_running():
            raise RuntimeError(
                "Cannot call sync send_fatheavy from an async "
                "context. Use send_fatheavy_async() instead."
            )
        return loop.run_until_complete(
            self.send_fatheavy_async(
                recipient=recipient,
                who=who,
                what=what,
                content=content,
                content_type=content_type,
                filename=filename,
                custom_metadata=custom_metadata,
                options=options,
                where=where,
                expose_ttl=expose_ttl,
            )
        )

    async def send_fatheavy_async(
        self,
        recipient: str,
        who: str,
        what: str,
        content: bytes | None,
        content_type: str = "application/octet-stream",
        filename: str | None = None,
        custom_metadata: dict[str, Any] | None = None,
        options: RabbitMQCarrierOptions | None = None,
        where: str | None = None,
        expose_ttl: int = 3600,
    ) -> dict:
        """Publish a fat/heavy message to RabbitMQ (async).

        Args:
            recipient: Routing key (or queue name for default
                exchange).
            who: Entity identifier.
            what: Content type/category.
            content: New data to save or None.
            content_type: MIME type of the data.
            filename: Optional original filename.
            custom_metadata: Optional additional metadata.
            options: RabbitMQ-specific options.
            where: URL where content is available.
            expose_ttl: Time-to-live for exposed URL.

        Returns:
            dict: Send result with status and routing info.

        Raises:
            ValueError: If neither content nor where provided.
            NotImplementedError: If content provided without
                where.
            RuntimeError: If connection not started.
        """
        import aio_pika

        if options is None:
            options = RabbitMQCarrierOptions()

        if self._exchange is None:
            raise RuntimeError(
                "Connection not started. Call await carrier.start() first."
            )

        if content is None and where is None:
            raise ValueError("Must provide either 'content' or 'where'")

        if content is not None and where is None:
            raise NotImplementedError(
                "Saving content and generating 'where' URL "
                "not yet implemented. Please provide 'where' "
                "directly."
            )

        routing_key = options.routing_key or recipient

        if options.metadata_use_inline:
            body = self._build_inline_payload(
                who=who,
                what=what,
                content=b"",
                content_type=content_type,
                filename=filename,
                where=where,
                custom_metadata=custom_metadata,
            )
            headers: dict[str, Any] | None = None
        else:
            body = b""
            headers: dict[str, Any] | None = self._build_outline_headers(
                who=who,
                what=what,
                content_type=content_type,
                filename=filename,
                where=where,
            )

        message = aio_pika.Message(
            body=body,
            headers=headers,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            priority=options.priority,
        )

        await self._exchange.publish(message, routing_key=routing_key)

        logger.info(
            "Published fat/heavy message to %s: who=%s, what=%s, where=%s, exchange=%s",
            routing_key,
            who,
            what,
            where,
            self.exchange_name or "(default)",
        )

        return {
            "status": "published",
            "exchange": self.exchange_name or "(default)",
            "routing_key": routing_key,
        }

    async def consume(self, topic: str) -> AsyncIterator[TransportMessage]:
        """Consume messages from a RabbitMQ queue.

        Creates a robust connection (if not already started),
        declares the queue, binds to exchange (if non-default),
        and yields parsed TransportMessage instances with
        ack/nack support.

        Args:
            topic: Queue name to consume from.

        Yields:
            TransportMessage: Parsed messages with ack/nack
                bound to the underlying AMQP message.
        """
        import aio_pika

        # Ensure connection is established
        if self._connection is None:
            await self.start()

        assert self._channel is not None

        # Declare queue (idempotent)
        queue = await self._channel.declare_queue(topic, durable=self.queue_durable)

        # Bind to exchange if using a named exchange
        if self.exchange_name and self._exchange is not None:
            await queue.bind(self._exchange, routing_key=topic)

        async with queue.iterator() as queue_iter:
            async for amqp_msg in queue_iter:
                amqp_msg: aio_pika.abc.AbstractIncomingMessage

                # Convert AMQP headers to dict[str, str]
                headers = None
                if amqp_msg.headers:
                    headers = {str(k): str(v) for k, v in amqp_msg.headers.items()}

                message = self.receive(amqp_msg.body, headers)

                # Bind ack/nack from the AMQP message
                async def _ack(
                    _msg: aio_pika.abc.AbstractIncomingMessage = amqp_msg,
                ) -> None:
                    await _msg.ack()

                async def _nack(
                    requeue: bool = False,
                    _msg: aio_pika.abc.AbstractIncomingMessage = amqp_msg,
                ) -> None:
                    await _msg.nack(requeue=requeue)

                message._ack_fn = _ack
                message._nack_fn = _nack
                yield message

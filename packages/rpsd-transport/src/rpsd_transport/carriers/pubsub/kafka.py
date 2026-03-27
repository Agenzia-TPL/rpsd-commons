# SPDX-License-Identifier: BSD-3-Clause
# Copyright (C) 2026 AGENZIA TPL BACINO CITTA' METROPOLITANA MILANO,
# MONZA E BRIANZA, LODI, PAVIA
"""
Kafka carrier implementation for rpsd-transport.

Requires the 'kafka' optional dependency:
    uv add rpsd-transport[kafka]
"""

import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from rpsd_transport.carriers.base import CarrierOptions
from rpsd_transport.carriers.pubsub.base import PubSubCarrier
from rpsd_transport.models import TransportMessage

if TYPE_CHECKING:
    from aiokafka import AIOKafkaProducer

logger = logging.getLogger(__name__)


class KafkaCarrierOptions(CarrierOptions):
    """Kafka-specific send options.

    Attributes:
        metadata_use_inline: If True, metadata is embedded in
            JSON payload. If False, metadata goes in Kafka
            message headers.
        partition: Target partition number. None for automatic
            partitioning.
        key: Message key for partition assignment. Encoded as
            UTF-8 bytes.
    """

    partition: int | None = None
    key: str | None = None


class KafkaPubSubCarrier(PubSubCarrier):
    """Kafka-based carrier for PubSub transport.

    Uses aiokafka for async Kafka producer and consumer.
    Manages both producer and consumer connections internally.

    Example - Publishing:
        ```python
        carrier = KafkaPubSubCarrier(
            bootstrap_servers="localhost:9092"
        )
        await carrier.start()
        carrier.send_slimfast(
            recipient="my-topic",
            who="sender",
            what="data",
            content=b"hello",
        )
        await carrier.stop()
        ```

    Example - Consuming:
        ```python
        carrier = KafkaPubSubCarrier(
            bootstrap_servers="localhost:9092",
            group_id="my-group",
        )
        async for message in carrier.consume("my-topic"):
            print(message.who, message.what)
        ```
    """

    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        group_id: str | None = None,
        client_id: str | None = None,
        timeout: int = 30,
    ):
        """Initialize Kafka carrier.

        Args:
            bootstrap_servers: Comma-separated list of Kafka
                broker addresses.
            group_id: Consumer group ID. Required for consuming.
            client_id: Optional client identifier for Kafka.
            timeout: Timeout in seconds for broker requests.
                Converted to milliseconds for aiokafka.
        """
        try:
            import aiokafka  # noqa: F401
        except ImportError:
            raise ImportError(
                "KafkaPubSubCarrier requires aiokafka. "
                "Install with: uv add rpsd-transport[kafka]"
            ) from None

        self.bootstrap_servers = bootstrap_servers
        self.group_id = group_id
        self.client_id = client_id
        self.timeout = timeout
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        """Start the Kafka producer.

        Must be called before send_slimfast/send_fatheavy.
        """
        from aiokafka import AIOKafkaProducer

        if self._producer is None:
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                client_id=self.client_id,
                request_timeout_ms=self.timeout * 1000,
            )
            await self._producer.start()

    async def stop(self) -> None:
        """Stop the Kafka producer."""
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None

    def send_slimfast(
        self,
        recipient: str,
        who: str,
        what: str,
        content: bytes,
        content_type: str = "application/octet-stream",
        filename: str | None = None,
        custom_metadata: dict[str, Any] | None = None,
        options: KafkaCarrierOptions | None = None,
    ) -> dict:
        """Publish a slim/fast message to a Kafka topic.

        Note: This method is sync in the BaseCarrier interface
        but Kafka publishing is async. Use send_slimfast_async()
        for native async, or call this from an event loop.

        Args:
            recipient: Kafka topic name
            who: Entity identifier
            what: Content type/category
            content: Data to send
            content_type: MIME type of the data
            filename: Optional original filename
            custom_metadata: Optional additional metadata
            options: Kafka-specific options (partition, key)

        Returns:
            dict: Send result with topic and partition info

        Raises:
            RuntimeError: If producer not started
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
        options: KafkaCarrierOptions | None = None,
    ) -> dict:
        """Publish a slim/fast message to a Kafka topic (async).

        Args:
            recipient: Kafka topic name
            who: Entity identifier
            what: Content type/category
            content: Data to send
            content_type: MIME type of the data
            filename: Optional original filename
            custom_metadata: Optional additional metadata
            options: Kafka-specific options (partition, key)

        Returns:
            dict: Send result with topic, partition, offset

        Raises:
            RuntimeError: If producer not started
        """
        if options is None:
            options = KafkaCarrierOptions()

        if self._producer is None:
            raise RuntimeError(
                "Producer not started. Call await carrier.start() first."
            )

        if options.metadata_use_inline:
            value = self._build_inline_payload(
                who=who,
                what=what,
                content=content,
                content_type=content_type,
                filename=filename,
                custom_metadata=custom_metadata,
            )
            kafka_headers = None
        else:
            value = content
            kafka_headers = [
                (k, v.encode("utf-8"))
                for k, v in self._build_outline_headers(
                    who=who,
                    what=what,
                    content_type=content_type,
                    filename=filename,
                ).items()
            ]

        key = options.key.encode("utf-8") if options.key else None

        result = await self._producer.send_and_wait(
            topic=recipient,
            value=value,
            key=key,
            partition=options.partition,
            headers=kafka_headers,
        )

        logger.info(
            "Published slim/fast message to %s: who=%s, "
            "what=%s, partition=%d, offset=%d",
            recipient,
            who,
            what,
            result.partition,
            result.offset,
        )

        return {
            "status": "published",
            "topic": result.topic,
            "partition": result.partition,
            "offset": result.offset,
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
        options: KafkaCarrierOptions | None = None,
        where: str | None = None,
        expose_ttl: int = 3600,
    ) -> dict:
        """Publish a fat/heavy message to a Kafka topic.

        Note: This method is sync in the BaseCarrier interface
        but Kafka publishing is async. Use send_fatheavy_async()
        for native async.

        Args:
            recipient: Kafka topic name
            who: Entity identifier
            what: Content type/category
            content: New data to save or None
            content_type: MIME type of the data
            filename: Optional original filename
            custom_metadata: Optional additional metadata
            options: Kafka-specific options (partition, key)
            where: URL where content is available
            expose_ttl: Time-to-live for exposed URL

        Returns:
            dict: Send result with topic and partition info

        Raises:
            ValueError: If neither content nor where provided
            RuntimeError: If producer not started
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
        options: KafkaCarrierOptions | None = None,
        where: str | None = None,
        expose_ttl: int = 3600,
    ) -> dict:
        """Publish a fat/heavy message to a Kafka topic (async).

        Args:
            recipient: Kafka topic name
            who: Entity identifier
            what: Content type/category
            content: New data to save or None
            content_type: MIME type of the data
            filename: Optional original filename
            custom_metadata: Optional additional metadata
            options: Kafka-specific options (partition, key)
            where: URL where content is available
            expose_ttl: Time-to-live for exposed URL

        Returns:
            dict: Send result with topic, partition, offset

        Raises:
            ValueError: If neither content nor where provided
            NotImplementedError: If content provided without where
            RuntimeError: If producer not started
        """
        if options is None:
            options = KafkaCarrierOptions()

        if self._producer is None:
            raise RuntimeError(
                "Producer not started. Call await carrier.start() first."
            )

        if content is None and where is None:
            raise ValueError("Must provide either 'content' or 'where'")

        if content is not None and where is None:
            raise NotImplementedError(
                "Saving content and generating 'where' URL "
                "not yet implemented. Please provide 'where' "
                "directly."
            )

        if options.metadata_use_inline:
            value = self._build_inline_payload(
                who=who,
                what=what,
                content=b"",
                content_type=content_type,
                filename=filename,
                where=where,
                custom_metadata=custom_metadata,
            )
            kafka_headers = None
        else:
            value = b""
            kafka_headers = [
                (k, v.encode("utf-8"))
                for k, v in self._build_outline_headers(
                    who=who,
                    what=what,
                    content_type=content_type,
                    filename=filename,
                    where=where,
                ).items()
            ]

        key = options.key.encode("utf-8") if options.key else None

        result = await self._producer.send_and_wait(
            topic=recipient,
            value=value,
            key=key,
            partition=options.partition,
            headers=kafka_headers,
        )

        logger.info(
            "Published fat/heavy message to %s: who=%s, "
            "what=%s, where=%s, partition=%d, offset=%d",
            recipient,
            who,
            what,
            where,
            result.partition,
            result.offset,
        )

        return {
            "status": "published",
            "topic": result.topic,
            "partition": result.partition,
            "offset": result.offset,
        }

    async def consume(self, topic: str) -> AsyncIterator[TransportMessage]:
        """Consume messages from a Kafka topic.

        Creates and manages an aiokafka consumer internally.
        Yields parsed TransportMessage instances with ack/nack
        support via manual offset commit.

        Args:
            topic: Kafka topic to consume from

        Yields:
            TransportMessage: Parsed messages with ack/nack set

        Raises:
            RuntimeError: If group_id was not set
        """
        from aiokafka import AIOKafkaConsumer, TopicPartition

        if self.group_id is None:
            raise RuntimeError(
                "group_id is required for consuming. Set it "
                "in the KafkaPubSubCarrier constructor."
            )

        consumer = AIOKafkaConsumer(
            topic,
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.group_id,
            client_id=(self.client_id if self.client_id else "aiokafka-consumer"),
            enable_auto_commit=False,
            request_timeout_ms=self.timeout * 1000,
        )

        await consumer.start()
        try:
            async for msg in consumer:
                # Convert Kafka headers to dict
                headers = None
                if msg.headers:
                    headers = {k: v.decode("utf-8") for k, v in msg.headers}

                # Kafka message value is bytes (or None for tombstones)
                if msg.value is None:
                    continue  # Skip tombstone messages

                message = self.receive(msg.value, headers)

                # Bind ack/nack for manual offset management
                tp = TopicPartition(msg.topic, msg.partition)
                offset = msg.offset

                async def _ack(
                    _tp=tp,
                    _offset=offset,
                ) -> None:
                    await consumer.commit({_tp: _offset + 1})

                async def _nack(
                    requeue: bool = False,
                    _tp=tp,
                    _offset=offset,
                ) -> None:
                    if requeue:
                        consumer.seek(_tp, _offset)

                message._ack_fn = _ack
                message._nack_fn = _nack
                yield message
        finally:
            await consumer.stop()

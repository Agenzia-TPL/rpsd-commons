"""
Abstract base class for PubSub transport carriers.

PubSub carriers implement message transport via event brokers
(Kafka, Redis, RabbitMQ, etc.). They share a common receive
contract distinct from HTTP carriers.
"""

import base64
import json
import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from rpsd_transport.carriers.base import BaseCarrier
from rpsd_transport.models import (
    MessageMetadata,
    TransportMessage,
)

logger = logging.getLogger(__name__)


class PubSubCarrier(BaseCarrier, ABC):
    """Abstract base class for PubSub transport carriers.

    PubSub carriers implement transport via event brokers. They
    share sending semantics with all carriers (send_slimfast,
    send_fatheavy) but define their own receive mechanism suited
    to broker consumers.

    Primary API:
    - send_slimfast / send_fatheavy: Publish messages to a topic
    - consume(topic): Async iterator that manages the broker
      consumer lifecycle and yields TransportMessage instances

    Low-level API:
    - receive(raw_message, headers): Sync parser for advanced
      use when the caller manages their own broker consumer
    """

    @abstractmethod
    async def consume(self, topic: str) -> AsyncIterator[TransportMessage]:
        """Consume messages from a topic as an async iterator.

        Manages the broker consumer lifecycle internally. Each
        yielded message has already been parsed into a
        TransportMessage and the received() hook has been called.

        Args:
            topic: Topic/channel to consume from

        Yields:
            TransportMessage: Parsed messages from the broker

        Example:
            ```python
            carrier = KafkaPubSubCarrier(
                bootstrap_servers="localhost:9092"
            )
            async for message in carrier.consume("my-topic"):
                process(message)
            ```
        """
        raise NotImplementedError
        yield  # pragma: no cover

    @abstractmethod
    async def start(self) -> None:
        """Start the PubSub carrier connection.

        Initializes connections to the message broker (producer,
        consumer, channels, etc.). Must be called before sending
        or consuming messages.

        Implementations should be idempotent (safe to call
        multiple times).

        Raises:
            ConnectionError: If unable to connect to broker
        """
        ...  # pragma: no cover

    @abstractmethod
    async def stop(self) -> None:
        """Stop the PubSub carrier connection.

        Cleanly closes connections to the message broker.
        Should be called when done with the carrier, typically
        in a finally block or async context manager cleanup.

        Implementations should be idempotent (safe to call
        multiple times, safe to call without start).
        """
        ...  # pragma: no cover

    def receive(
        self,
        raw_message: bytes,
        headers: dict[str, str] | None = None,
    ) -> TransportMessage:
        """Parse a raw broker message into a TransportMessage.

        This is a sync method (no I/O, just parsing). Use it for
        advanced scenarios where you manage your own broker
        consumer and want to parse messages manually.

        For typical use, prefer consume() which manages the
        consumer lifecycle.

        Supports both inline and outline metadata:
        - Inline: raw_message is JSON with metadata + content
        - Outline: metadata in headers dict, raw_message is
          content bytes

        Calls the received() hook after successful parsing.

        Args:
            raw_message: Raw bytes from the broker
            headers: Optional message headers from the broker.
                If present and raw_message is not inline JSON,
                metadata is extracted from headers.

        Returns:
            TransportMessage: Parsed message

        Raises:
            InvalidJsonError: If inline JSON is malformed
            ValueError: If required metadata is missing
        """
        message = self._parse_message(raw_message, headers)

        # Log received message
        if message.is_fatheavy:
            logger.info(
                "Received heavy message: who=%s, what=%s, where=%s",
                message.who,
                message.what,
                message.where,
            )
        else:
            content_size = len(message.content) if message.content else 0
            logger.info(
                "Received fast message: who=%s, what=%s, size=%d bytes",
                message.who,
                message.what,
                content_size,
            )

        # Call hook for extensibility
        self.received(message)

        return message

    def _parse_message(
        self,
        raw_message: bytes,
        headers: dict[str, str] | None = None,
    ) -> TransportMessage:
        """Parse raw broker message into TransportMessage.

        Tries inline JSON first, falls back to outline (headers).
        """
        # Try inline JSON first
        inline_message = self._try_parse_inline(raw_message)
        if inline_message is not None:
            return inline_message

        # Fall back to outline: metadata from headers, content
        # from raw_message
        return self._parse_outline(raw_message, headers)

    def _try_parse_inline(self, raw_message: bytes) -> TransportMessage | None:
        """Try to parse raw_message as inline JSON.

        Returns None if the message is not valid inline JSON.
        """
        try:
            parsed = json.loads(raw_message)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

        if not isinstance(parsed, dict):
            return None

        metadata_dict = parsed.get("metadata")
        if not isinstance(metadata_dict, dict):
            return None

        # Check required fields
        if "who" not in metadata_dict or "what" not in metadata_dict:
            return None

        metadata = MessageMetadata.model_validate(metadata_dict)

        # Decode content for slim/fast messages
        content = None
        raw_content = parsed.get("content")
        if metadata.is_slimfast and raw_content:
            content = base64.b64decode(raw_content)
        elif metadata.is_slimfast and not raw_content:
            raise ValueError("Fast message requires content")

        return TransportMessage(metadata=metadata, content=content)

    def _parse_outline(
        self,
        raw_message: bytes,
        headers: dict[str, str] | None = None,
    ) -> TransportMessage:
        """Parse outline message: metadata from headers, content
        from raw_message.
        """
        if not headers:
            raise ValueError(
                "Message is not inline JSON and no headers "
                "provided for outline metadata"
            )

        who = headers.get("rpsd-who") or headers.get("who")
        what = headers.get("rpsd-what") or headers.get("what")
        where = headers.get("rpsd-where") or headers.get("where")
        content_type = (
            headers.get("rpsd-content-type")
            or headers.get("content-type")
            or "application/octet-stream"
        )
        filename = headers.get("rpsd-filename") or headers.get("filename")

        if not who or not what:
            raise ValueError("Outline message requires 'who' and 'what' in headers")

        metadata = MessageMetadata(
            who=who,
            what=what,
            where=where,
            content_type=content_type,
            filename=filename,
        )

        # For heavy messages, content is at the 'where' URL
        if metadata.is_fatheavy:
            return TransportMessage(metadata=metadata, content=None)

        return TransportMessage(metadata=metadata, content=raw_message)

    @staticmethod
    def _build_inline_payload(
        who: str,
        what: str,
        content: bytes,
        content_type: str,
        filename: str | None = None,
        where: str | None = None,
        custom_metadata: dict[str, Any] | None = None,
    ) -> bytes:
        """Build inline JSON payload for publishing.

        Returns JSON bytes ready to send to the broker.
        """
        metadata: dict = {
            "who": who,
            "what": what,
            "content_type": content_type,
        }
        if filename:
            metadata["filename"] = filename
        if where:
            metadata["where"] = where
        if custom_metadata:
            metadata["custom_metadata"] = custom_metadata

        payload: dict = {"metadata": metadata}

        if where:
            payload["content"] = None
        else:
            payload["content"] = base64.b64encode(content).decode("utf-8")

        return json.dumps(payload).encode("utf-8")

    @staticmethod
    def _build_outline_headers(
        who: str,
        what: str,
        content_type: str,
        filename: str | None = None,
        where: str | None = None,
    ) -> dict[str, str]:
        """Build outline headers dict for publishing.

        Returns headers dict for broker message headers.

        Note: custom_metadata is not supported in outline mode.
        Use inline mode (JSON body) if you need custom_metadata.
        """
        headers: dict[str, str] = {
            "rpsd-who": who,
            "rpsd-what": what,
            "rpsd-content-type": content_type,
        }
        if filename:
            headers["rpsd-filename"] = filename
        if where:
            headers["rpsd-where"] = where
        return headers
